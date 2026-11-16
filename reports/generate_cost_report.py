
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.reference import TICKET_EXPECTATIONS
from question1.agent import SupportCopilot
from question2.agent import SupportPipeline
from shared.billing import CostSession

PUBLIC = ["T-1001", "T-1002", "T-1003", "T-1004"]


def check_ticket(question, ticket_id, target):
    session = CostSession()

    if question == "Q1":
        agent = SupportCopilot(session=session)
    else:
        agent = SupportPipeline(session=session)

    result = agent.handle_ticket(ticket_id)
    expected = TICKET_EXPECTATIONS[ticket_id]

    cost = session.total_points()
    correct = (
        result.action == expected.action
        and result.kb_article == expected.kb_article
    )
    within_budget = cost <= target

    print(f"\n{question} / {ticket_id}")
    print(f"  Action: {result.action} (expected: {expected.action})")
    print(f"  Article: {result.kb_article} (expected: {expected.kb_article})")
    print(f"  Total cost: {cost:,} points (target: <= {target:,})")
    print(f"  Correct resolution: {'PASS' if correct else 'FAIL'}")
    print(f"  Cost target: {'PASS' if within_budget else 'FAIL'}")

    for index, call in enumerate(session.calls, start=1):
        print(
            f"  Call {index}: {call.label}, "
            f"{call.input_tokens} input tokens, "
            f"{call.output_tokens} output tokens, "
            f"{call.points():,} points"
        )

    return correct, within_budget


def main():
    all_passed = True

    for question, target in (("Q1", 3000), ("Q2", 2500)):
        print(f"\n{'=' * 12} {question} {'=' * 12}")

        for ticket_id in PUBLIC:
            correct, within_budget = check_ticket(
                question, ticket_id, target
            )
            all_passed = all_passed and correct and within_budget

    print("\n" + "=" * 30)
    print(
        "OVERALL:",
        "PASS" if all_passed else "FAIL — inspect the cases above",
    )


if __name__ == "__main__":
    main()
