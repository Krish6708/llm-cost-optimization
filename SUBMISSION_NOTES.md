# LLM Cost Optimization — Internship Assignment

This repository contains my implementation for the two LLM cost-optimization tasks in the IndusEuro assignment.

## Approach

### Question 1: Single-call support copilot
- Removed unnecessary prompt context, including the full help-center dump and few-shot examples.
- Passed the ticket conversation plus a compact snapshot of decision-relevant order fields.
- Kept the required structured output (`action` and `kb_article`) and JSON parsing contract.
- Kept routing rules explicit and prioritized to reduce ambiguity.

### Question 2: Support pipeline
- Kept the logical triage, retrieval, composition, and audit stages.
- Made triage, article shortlisting, and output validation deterministic local steps.
- Reserved the LLM call for composing the customer-facing response, rather than invoking the model separately for every stage.
- Retrieved only the relevant article ID instead of repeatedly sending the large help-center context.

This is a cost/latency trade-off: deterministic steps are cheaper and more predictable for structured checks, while the LLM is used where language generation is needed. The agent files do not import `eval/reference.py`.

## Verification

Run from the repository root after installing the assignment dependencies:

```bash
pip install -r requirements.txt
python reports/generate_cost_report.py
python question1/run.py
python question2/run.py
```

The cost report checks the four public tickets in each question against the expected action/article and prints token counts and billing points.

### Observed public-ticket results

| Track | Ticket | Points | Target | Resolution |
|---|---|---:|---:|---|
| Q1 | T-1001 | 1,548 | ≤ 3,000 | PASS |
| Q1 | T-1002 | 1,410 | ≤ 3,000 | PASS |
| Q1 | T-1003 | 1,374 | ≤ 3,000 | PASS |
| Q1 | T-1004 | 1,335 | ≤ 3,000 | PASS |
| Q2 | T-1001 | 1,593 | ≤ 2,500 | PASS |
| Q2 | T-1002 | 1,452 | ≤ 2,500 | PASS |
| Q2 | T-1003 | 1,416 | ≤ 2,500 | PASS |
| Q2 | T-1004 | 1,380 | ≤ 2,500 | PASS |

These are observed results from a local run, not a guarantee for every possible ticket.

The original full test suite also contains two `test_baseline_cost_is_high` assertions that expect high baseline costs. Those assertions failed with the optimized agents because their costs are now lower; the test files were left unchanged. Other targeted public-ticket checks passed. I have not represented the entire original test suite as passing.

## Billing formula

`points = uncached_input_tokens × 3 + cached_input_tokens × 0.3 + output_tokens × 15`

The optimized calls primarily reduce cost by shortening input context and reducing the number of LLM calls.
