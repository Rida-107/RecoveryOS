# RecoveryOS — AI Revenue Recovery Agent

Top-3-focused Razorpay Buildathon project.

## Current MVP

RecoveryOS ingests failed payment events and produces a transparent recovery recommendation using:
- recovery-probability scoring
- failure diagnosis
- expected recovery value
- bounded policy/guardrails
- recommended recovery action
- audit event

The current MVP deliberately uses a transparent heuristic so the product is runnable without an external AI key. The next phase replaces the heuristic with a trained, calibrated ML model and adds an LLM diagnosis/agent layer.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

API docs: http://127.0.0.1:8000/docs

## API examples

- `GET /health`
- `GET /dashboard`
- `GET /payments`
- `POST /recover` with `{"payment_id":"pay_00001"}`

## Roadmap

1. Labeled synthetic recovery dataset
2. ML recovery model + held-out evaluation
3. Intervention uplift / expected-value ranking
4. LLM failure diagnosis and customer-context reasoning
5. Tool-calling recovery agent
6. Policy engine + idempotency + verification
7. React merchant dashboard
8. Failure injection tests
9. Batch benchmark vs baseline
10. Demo + 5-minute pitch
