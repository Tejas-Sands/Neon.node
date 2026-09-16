---
title: AI Video Generator
emoji: 🎥
colorFrom: indigo
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
---

# Remotion Video Generator Space

This is a self-contained video generation hub using Remotion, Python FastAPI, Llama 3.1, and SDXL.

## Running Locally

To run this space locally, install the Python and Node dependencies and launch the server:

```bash
# Install Python deps
pip install -r requirements.txt

# Install Node deps
npm install

# Run FastAPI
uvicorn main:app --host 0.0.0.0 --port 7860
```
# Neon.node

## Audience growth

The automated content pipeline now prefers stories useful to developers and
hands-on AI builders, with a shared source-grounded hook → proof → payoff brief.
See the [30-day growth plan](docs/GROWTH_PLAN.md) and the
[saved baseline](docs/GROWTH_BASELINE.md) for positioning and review criteria.

Review the local ledger without making API calls or posting:

```bash
python3 growth_report.py --days 30
python3 growth_report.py --days 30 --json
python3 -m unittest test_growth_strategy test_growth_report
```

The strategy is on by default in this code (`builders-v1`). Set the process
environment variable `GROWTH_STRATEGY=off` to restore the earlier content policy.
Existing publishing, captions, cadence, and runtime experiments are unchanged.
Deployment is required before hosted jobs use local changes. A GitHub repository
Variable alone is not enough for rollback unless the workflow exports it; this
change does not edit the protected workflow.
