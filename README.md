# AI Cloud Cost Optimizer

Initial hackathon slice: a FastAPI backend serving resources from an in-memory cloud simulator. Recommendation decisions and audit logs are persisted in SQLite. No real cloud credentials or cloud operations are used.

## Run the backend

From the project root:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

## Test the APIs

- Health check: `GET http://127.0.0.1:8000/`
- Simulated resources: `GET http://127.0.0.1:8000/resources`
- Historical metrics: `GET http://127.0.0.1:8000/metrics`
- Utilization analysis: `GET http://127.0.0.1:8000/analysis`
- AI summary: `GET http://127.0.0.1:8000/agent/summary`
- Recommendations: `GET http://127.0.0.1:8000/recommendations`
- Approve recommendation: `POST http://127.0.0.1:8000/recommendations/{id}/approve`
- Reject recommendation: `POST http://127.0.0.1:8000/recommendations/{id}/reject`
- Execute approved recommendation: `POST http://127.0.0.1:8000/recommendations/{id}/execute`
- Audit logs: `GET http://127.0.0.1:8000/audit-logs`
- Interactive API documentation: `http://127.0.0.1:8000/docs`

The `/resources` endpoint returns eight deterministic simulated virtual machines. Their data is held in memory and resets when the server restarts.

The `/metrics` endpoint returns seven days of simulated CPU and RAM utilization. The `/analysis` endpoint calculates average utilization, flags underutilized VMs, and estimates potential savings at 30% of monthly cost. These are estimates only; no optimization action is performed yet.

Resource analysis also considers disk utilization, network utilization, request rate, error rate, average latency, criticality, and idle hours per day. The dashboard displays idle hours as `Idle Xh/day`. A resource is only treated as an optimization candidate when its CPU/RAM usage and activity are low, it has at least eight idle hours per day, its reliability signals are safe, and it is not high criticality.

The `/agent/summary` endpoint uses a safe local fallback by default. To connect an optional OpenAI-compatible service, set `LLM_API_URL`, `LLM_API_KEY`, and optionally `LLM_MODEL` as environment variables. Keys are never stored in source code, and the agent only analyzes data; it cannot execute simulator actions.

## Run backend tests

From the `backend` directory:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

The tests use a temporary SQLite database and cover discovery, analysis, approval gating, simulated execution, and audit persistence.

## Run the Angular dashboard

In a second terminal, from the project root:

```powershell
cd frontend
npm start
```

Open `http://localhost:4200`. Start the FastAPI backend first so the dashboard can load simulated resources and recommendations.

## Test with Postman

Import [AI-Cloud-Cost-Optimizer.postman_collection.json](postman/AI-Cloud-Cost-Optimizer.postman_collection.json) into Postman. The collection uses `http://127.0.0.1:8000` by default and runs the local-only workflow from health check through audit logs. Set `recommendationId` to a pending recommendation before running the approval request.

The `/recommendations` endpoint creates recommendations for underutilized VMs. In demo mode, each recommendation has a 3-minute approval window. If nobody approves or rejects before the deadline, the background monitor automatically approves the recommendation, runs the same safety checks, downsizes eligible simulated resources, and records the action in `/audit-logs`. Decisions and audit logs are persisted in `backend/costopti.db` and survive server restarts. The simulated VM state itself resets when the server restarts.

To use the intended 24-hour behavior, set `COSTOPTI_APPROVAL_WAIT_MINUTES=1440` before starting FastAPI. The default is `3` minutes for hackathon testing.

The execute endpoint performs a simulated resize only after approval. Production changes are blocked by policy. Non-production actions run a health check; failed checks restore the original simulated VM state. All executed actions are available through `/audit-logs`.
