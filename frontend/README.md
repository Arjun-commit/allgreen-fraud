# AllGreen Fraud Detection — Analyst Dashboard

React 18 + TypeScript + Tailwind analyst dashboard.

## Quick start

```bash
cd frontend
npm install
npm run dev        # starts on :3000, proxies /v1/* to :8000
```

Make sure the backend is running on port 8000 (`uvicorn backend.main:app`).

## Screens

- **Dashboard** — live alert feed, auto-refreshes every 10s. Metric cards + paginated table.
- **Case Detail** — risk breakdown (behavioral/context gauges), session timeline, SHAP factors chart, friction log, analyst action buttons.
- **Analytics** — model performance (AUC, precision, recall), friction effectiveness, score distribution histogram.
- **Settings** — threshold sliders with live impact preview, friction type config, maker-checker save flow.

## Stack

- Vite for builds
- React Router for navigation
- Recharts for charts
- Lucide for icons
- Tailwind CSS for styling

## TODO

- [ ] Wire up WebSocket for real-time alert push (currently polling)
- [ ] Add behavior heatmap component (needs raw event data from backend)
- [ ] AUC-over-time line chart (needs historical metrics pipeline)
- [ ] Maker-checker approval flow (needs backend endpoint)
- [ ] Auth / login page
