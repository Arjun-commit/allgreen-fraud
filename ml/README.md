# ml/

Training code + notebooks for the two models.

- `lstm/` — PyTorch behavioral anomaly detector (phase 3)
- `xgboost/` — transaction context classifier (phase 3)
- `shared/` — preprocessing + feature-name constants shared between training and serving
- `notebooks/` — exploratory work; not part of CI

Artifacts (`*.pt`, `*.json`) are gitignored. Models are versioned in MLflow;
the serving containers pull from the registry at start.
