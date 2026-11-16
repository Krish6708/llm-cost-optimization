# LLM Cost Optimization — ShopAssist

Implementation of the IndusEuro LLM Cost Optimization internship assignment, covering a single-call support agent (Q1) and a cost-aware support pipeline (Q2).

## Approach

### Question 1 — Single-call agent
- Reduced prompt size by removing unnecessary examples and the full help-center context.
- Included the ticket conversation and only decision-relevant order fields.
- Preserved the required structured JSON output.

### Question 2 — Cost-aware pipeline
- Used deterministic local logic for triage, article shortlisting, and output validation.
- Reserved the LLM call for composing the customer-facing response.
- Restricted article selection to relevant candidates rather than repeatedly sending the full help-center context.

## Observed cost results

The following results were measured locally on the four public tickets for each question.

| Track | Ticket | Cost points | Target |
|---|---|---:|---:|
| Q1 | T-1001 | 1,548 | ≤ 3,000 |
| Q1 | T-1002 | 1,410 | ≤ 3,000 |
| Q1 | T-1003 | 1,374 | ≤ 3,000 |
| Q1 | T-1004 | 1,335 | ≤ 3,000 |
| Q2 | T-1001 | 1,593 | ≤ 2,500 |
| Q2 | T-1002 | 1,452 | ≤ 2,500 |
| Q2 | T-1003 | 1,416 | ≤ 2,500 |
| Q2 | T-1004 | 1,380 | ≤ 2,500 |

All eight cases matched the expected action and knowledge-base article and stayed within their cost targets in this local run. These results do not guarantee performance on every possible ticket.

## Setup and execution

From the repository root:

```bash
pip install -r requirements.txt
python reports/generate_cost_report.py
python question1/run.py
python question2/run.py
```

Run the original tests with:

```bash
pytest -q
```

**Test note:** Two original `test_baseline_cost_is_high` assertions fail because they expect high baseline costs. The test files were not modified. See `SUBMISSION_NOTES.md` for details.

## Billing formula

```text
points = uncached_input_tokens × 3
       + cached_input_tokens × 0.3
       + output_tokens × 15
```

The optimization focuses on reducing unnecessary prompt context and model calls while preserving the expected ticket-resolution outputs.
