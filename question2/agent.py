from __future__ import annotations

import json
from dataclasses import dataclass

from shared.billing import CostSession
from shared.kb import article_ids
from shared.llm import ChatMessage, LlmClient
from shared.tools import format_thread, get_order, get_ticket
from question1.agent import parse_resolution


@dataclass
class TicketResolution:
    action: str
    kb_article: str


_ORDER_FIELDS = (
    "product_type",
    "subscription_age_days",
    "license_revealed",
    "customized",
    "damage_reported",
    "delivered_days_ago",
    "opened",
)

_VALID_ACTIONS = {"REFUND", "REPLACE", "SEND_ARTICLE", "ESCALATE_TIER2"}
_VALID_ARTICLES = set(article_ids())


class SupportPipeline:
    """Cost-aware pipeline: deterministic triage/retrieval/audit, one LLM compose call.

    Ticket metadata and article lookup are deterministic operations. Only the
    ambiguous language-to-resolution step uses the model, instead of invoking
    an LLM independently for each of the four stages.
    """

    def __init__(self, session: CostSession | None = None):
        self.session = session or CostSession()
        self.llm = LlmClient(self.session)

    @staticmethod
    def _compact_order(order: dict) -> dict:
        return {key: order[key] for key in _ORDER_FIELDS if key in order}

    @staticmethod
    def _triage(order: dict) -> dict:
        """Extract routing signals locally, without spending an LLM call."""
        return {
            "subscription": order.get("product_type") == "subscription",
            "subscription_age_days": order.get("subscription_age_days"),
            "license_revealed": bool(order.get("license_revealed", False)),
            "customized_damage": bool(order.get("customized", False))
            and bool(order.get("damage_reported", False)),
            "recent_damage": bool(order.get("damage_reported", False))
            and not bool(order.get("customized", False))
            and int(order.get("delivered_days_ago", 99)) <= 7,
            "unopened_physical": order.get("product_type") == "physical"
            and not bool(order.get("opened", False))
            and int(order.get("delivered_days_ago", 99)) <= 30,
        }

    @staticmethod
    def _retrieve(triage: dict, order: dict) -> list[str]:
        """Return a tiny candidate set rather than the 200k-token help-center blob."""
        if triage["subscription"]:
            candidates = ["subscription-cooling-off"]
        elif triage["license_revealed"]:
            candidates = ["digital-license-no-refund"]
        elif triage["customized_damage"]:
            candidates = ["custom-items-no-replace"]
        elif triage["recent_damage"]:
            candidates = ["damage-replacement-7-days"]
        elif triage["unopened_physical"]:
            candidates = ["returns-within-30-days"]
        else:
            candidates = ["returns-within-30-days"]

        # Keep retrieval grounded in the actual local knowledge-base inventory.
        existing = _VALID_ARTICLES
        return [article_id for article_id in candidates if article_id in existing]

    def _compose(
        self,
        ticket_id: str,
        thread: str,
        order: dict,
        triage: dict,
        retrieved: list[str],
    ) -> str:
        snapshot = json.dumps(order, separators=(",", ":"), ensure_ascii=False)
        system = (
            "You are ShopAssist. Apply these rules in order: "
            "subscription age <= 30 days: REFUND, otherwise SEND_ARTICLE, both using subscription-cooling-off; "
            "revealed digital license: SEND_ARTICLE/digital-license-no-refund; "
            "customized damaged item: ESCALATE_TIER2/custom-items-no-replace; "
            "non-custom damaged item delivered <= 7 days ago: REPLACE/damage-replacement-7-days; "
            "unopened physical item delivered <= 30 days ago: REFUND/returns-within-30-days; "
            "otherwise ESCALATE_TIER2/returns-within-30-days. "
            "Choose a matching candidate article from the supplied list. "
            "Return valid JSON only with action, kb_article, customer_reply."
        )
        user = (
            f"TICKET_ID: {ticket_id}\n"
            f"THREAD:\n{thread}\n"
            f"TRIAGE_SIGNALS: {json.dumps(triage, separators=(',', ':'))}\n"
            f"CANDIDATE_ARTICLES: {', '.join(retrieved)}\n"
            f"ORDER_SNAPSHOT: {snapshot} END_SNAPSHOT"
        )
        return self.llm.chat(
            "compose",
            [ChatMessage("system", system), ChatMessage("user", user)],
        )

    @staticmethod
    def _audit(raw_completion: str, retrieved: list[str]) -> TicketResolution:
        """Validate the model's structured result locally; do not call the LLM again."""
        parsed = parse_resolution(raw_completion)
        if parsed.action not in _VALID_ACTIONS:
            raise ValueError(f"Unsupported action from compose node: {parsed.action}")
        if parsed.kb_article not in _VALID_ARTICLES:
            raise ValueError(f"Unknown help-center article: {parsed.kb_article}")
        if retrieved and parsed.kb_article not in retrieved:
            raise ValueError(
                f"Article {parsed.kb_article!r} was not in retrieved candidates {retrieved!r}"
            )
        return TicketResolution(parsed.action, parsed.kb_article)

    def handle_ticket(self, ticket_id: str) -> TicketResolution:
        ticket = get_ticket(ticket_id)
        order = self._compact_order(get_order(ticket["order_id"]))
        thread = format_thread(ticket)
        triage = self._triage(order)
        retrieved = self._retrieve(triage, order)
        draft = self._compose(ticket_id, thread, order, triage, retrieved)
        return self._audit(draft, retrieved)
