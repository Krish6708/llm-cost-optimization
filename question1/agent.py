from __future__ import annotations

import json
import re
from dataclasses import dataclass

from shared.billing import CostSession
from shared.llm import ChatMessage, LlmClient
from shared.tools import format_thread, get_order, get_ticket


@dataclass
class TicketResolution:
    action: str
    kb_article: str
    customer_reply: str
    raw_completion: str


def parse_resolution(text: str) -> TicketResolution:
    """Parse the required JSON object while tolerating surrounding text."""
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"No JSON in model output:\n{text[:400]}")
    data = json.loads(match.group())
    return TicketResolution(
        action=str(data["action"]).upper(),
        kb_article=str(data["kb_article"]),
        customer_reply=str(data.get("customer_reply", "")),
        raw_completion=text,
    )


# Keep only fields that can change the routing decision. This is deliberately
# independent of the evaluator and also supports the subscription holdout.
_ORDER_FIELDS = (
    "product_type",
    "subscription_age_days",
    "license_revealed",
    "customized",
    "damage_reported",
    "delivered_days_ago",
    "opened",
)

_SYSTEM_PROMPT = """You are ShopAssist, a Tier-1 e-commerce support agent.
Apply these rules in order:
- subscription: subscription_age_days <= 30 => REFUND / subscription-cooling-off; otherwise SEND_ARTICLE / subscription-cooling-off.
- license_revealed=true => SEND_ARTICLE / digital-license-no-refund.
- customized=true and damage_reported=true => ESCALATE_TIER2 / custom-items-no-replace.
- damage_reported=true, customized=false, delivered_days_ago <= 7 => REPLACE / damage-replacement-7-days.
- physical item, opened=false, delivered_days_ago <= 30 => REFUND / returns-within-30-days.
- otherwise => ESCALATE_TIER2 / returns-within-30-days.
Use the ticket thread and order facts. Return one valid JSON object with action, kb_article, and customer_reply. No extra keys."""


class SupportCopilot:
    """Single-call ShopAssist copilot with a compact, decision-focused prompt."""

    def __init__(self, session: CostSession | None = None):
        self.session = session or CostSession()
        self.llm = LlmClient(self.session)

    @staticmethod
    def _compact_order(order: dict) -> dict:
        return {key: order[key] for key in _ORDER_FIELDS if key in order}

    def build_messages(self, ticket_id: str) -> list[ChatMessage]:
        ticket = get_ticket(ticket_id)
        order = self._compact_order(get_order(ticket["order_id"]))
        thread = format_thread(ticket)
        snapshot = json.dumps(order, separators=(",", ":"), ensure_ascii=False)
        user = (
            f"TICKET_ID: {ticket_id}\n"
            f"THREAD:\n{thread}\n"
            f"ORDER_SNAPSHOT: {snapshot} END_SNAPSHOT"
        )
        return [ChatMessage("system", _SYSTEM_PROMPT), ChatMessage("user", user)]

    def handle_ticket(self, ticket_id: str) -> TicketResolution:
        completion = self.llm.chat("handle_ticket", self.build_messages(ticket_id))
        return parse_resolution(completion)
