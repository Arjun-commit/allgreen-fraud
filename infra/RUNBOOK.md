# AllGreen Fraud Detection — Production Deployment Runbook

## Prerequisites

- Kubernetes cluster (1.28+) with nginx ingress controller
- `kubectl` configured for the target cluster
- Docker registry accessible from the cluster
- Secrets created (see below)
- Model artifacts built and stored in a PVC or object storage

## 1. Build & Push Images

```bash
# Backend
docker build -f infra/docker/Dockerfile.backend -t allgreen-fraud/backend:$(git rev-parse --short HEAD) .
docker push allgreen-fraud/backend:$(git rev-parse --short HEAD)

# Frontend
cd frontend && npm ci && npm run build
docker build -f infra/docker/Dockerfile.frontend -t allgreen-fraud/frontend:$(git rev-parse --short HEAD) .
docker push allgreen-fraud/frontend:$(git rev-parse --short HEAD)
```

## 2. Create Secrets

```bash
kubectl create secret generic allgreen-secrets \
  --from-literal=postgres-url='postgresql+psycopg://allgreen:CHANGEME@postgres:5432/allgreen' \
  --from-literal=redis-url='redis://redis:6379/0' \
  --from-literal=api-secret-key='GENERATE_A_REAL_SECRET_KEY_HERE'
```

## 3. Train & Upload Model Artifacts

```bash
# Train models locally or in a CI job
python -m ml.lstm.train
python -m ml.xgboost.train

# Create PVC and copy artifacts
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: allgreen-model-artifacts
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
EOF

# Copy artifacts into the PVC (use a temp pod or init container)
kubectl cp ml/lstm/artifacts/model.pt allgreen-model-loader:/app/ml/lstm/artifacts/model.pt
kubectl cp ml/xgboost/artifacts/model.json allgreen-model-loader:/app/ml/xgboost/artifacts/model.json
```

## 4. Deploy Infrastructure

```bash
# Kafka (or use managed MSK/Confluent Cloud and skip this)
kubectl apply -f infra/k8s/kafka-deployment.yaml

# Wait for Kafka to be ready
kubectl rollout status statefulset/kafka --timeout=300s
```

## 5. Run Database Migrations

```bash
kubectl run --rm -it migrations \
  --image=allgreen-fraud/backend:latest \
  --env="POSTGRES_URL=..." \
  -- alembic upgrade head
```

## 6. Deploy Backend

```bash
# Update the image tag in the deployment
kubectl set image deployment/allgreen-backend \
  backend=allgreen-fraud/backend:$(git rev-parse --short HEAD)

# Or apply the full manifest
kubectl apply -f infra/k8s/backend-deployment.yaml

# Wait for rollout
kubectl rollout status deployment/allgreen-backend --timeout=120s
```

## 7. Deploy Ingress

```bash
kubectl apply -f infra/k8s/ingress.yaml
```

## 8. Verify

```bash
# Health check
curl https://fraud-api.allgreen.internal/health

# Smoke test — score an empty session
curl -X POST https://fraud-api.allgreen.internal/v1/score \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
  -d '{"session_id":"smoke-test","transaction":{"amount":42,"transfer_type":"domestic"}}'

# Check metrics are flowing
curl https://fraud-api.allgreen.internal/metrics | head -20

# Check Grafana dashboard
open https://fraud-dashboard.allgreen.internal:3001
```

## 9. Post-Deploy Checklist

- [ ] Health endpoint returns 200
- [ ] Score endpoint returns valid response
- [ ] Grafana dashboards show data
- [ ] Prometheus targets are healthy
- [ ] Kafka topics created (scores.final, friction.decisions, etc.)
- [ ] Rate limiting is active (test with rapid requests)
- [ ] Error rate < 0.1% on Grafana

## Rollback

```bash
# Quick rollback to previous revision
kubectl rollout undo deployment/allgreen-backend

# Or pin to a specific revision
kubectl rollout undo deployment/allgreen-backend --to-revision=N
```

## Scaling

The HPA auto-scales 3→10 replicas based on CPU utilization (70%) and
request latency. For load tests, you can temporarily increase the max:

```bash
kubectl patch hpa allgreen-backend-hpa -p '{"spec":{"maxReplicas":20}}'
```

## Model Updates

To deploy updated model artifacts without restarting the backend:

1. Upload new model files to the PVC
2. Hit the (future) `/v1/admin/reload-models` endpoint
3. Or restart pods: `kubectl rollout restart deployment/allgreen-backend`

Monitor the `allgreen_model_auc` gauge in Grafana to verify the new
model's performance doesn't regress.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| 500 on /score | `kubectl logs -l component=backend` — likely model loading or DB connection |
| High latency | Check `allgreen_scoring_pipeline_duration_seconds` in Grafana — isolate LSTM vs XGBoost |
| 429 errors | Rate limiter is working. Increase limits if legitimate traffic spike. |
| Empty /cases | Postgres might be unreachable — backend falls back to demo data |
| Kafka lag | Check consumer group lag: `kafka-consumer-groups.sh --describe --group allgreen` |
