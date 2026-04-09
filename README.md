# All-Green Fraud Detection

Behavioral fraud detection for social-engineering ("all-green") attacks — the kind where
the transaction *looks* perfectly legitimate on paper because the real customer is on
their own device, passed 2FA, and is being coached by a scammer on the phone.

We don't try to catch this in the transaction data alone (that's what the existing
tools already do, and they lose). We catch it by watching **how** the customer is
behaving during the session — mouse dynamics, typing cadence, pauses, scroll depth,
confirmation-page dwell time — and comparing it to their own 90-day baseline.

## Status

**Phase 1: Foundation** — scaffolding, infra, DB schema, API skeleton, CI.
Nothing scores anything yet. See `docs/ROADMAP.md` (TODO) for phases 2-6.

## Quick start (dev)

```bash
cp .env.example .env
# edit POSTGRES_PASSWORD and API_SECRET_KEY at minimum

docker compose up -d postgres redis kafka zookeeper
docker compose up -d api
```

Then:
- API: http://localhost:8000/docs
- MLflow: http://localhost:5000 (once ML phase is in)
- Frontend: http://localhost:3000 (phase 5)

Run the DB migrations the first time:

```bash
docker compose run --rm api alembic upgrade head
```

## Repo layout

```
backend/   FastAPI app, feature extractors, model wrappers, friction engine
ml/        Model training code + notebooks (LSTM, XGBoost)
frontend/  React analyst dashboard (phase 5)
sdk/       Tiny JS snippet the bank injects into their web frontend
infra/     Docker, k8s, terraform
tests/     unit / integration / ml
```

## Running tests

```bash
pytest tests/unit -v
```

Integration and ML tests need the docker stack running — see `tests/README.md` (TODO).

## Design notes

A few things worth knowing before you touch the code:

- **The behavioral signal is our edge.** The XGBoost context model is a sanity check;
  the LSTM on session biometrics is where the actual value comes from.
- **We never hard-block without human-in-the-loop.** Cooling timers and callback
  holds, never an outright "transaction rejected" page. False positives on a $50k
  wire cost more than the fraud would have.
- **Raw mouse events are ephemeral.** We keep features, not raw coordinates, past
  the session window. GDPR/CCPA reasons.
- **SHAP on every prediction.** Regulators will ask.

More rationale in the original blueprint doc (`docs/blueprint.md`, also TODO to copy
over).
