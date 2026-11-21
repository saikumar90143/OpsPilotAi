# OpsPilot AI — 5–7 Minute Live Demo Script

**Mode:** 100% deterministic local demo (synthetic logs, synthetic runbooks, mock GitHub, mock AI copilot, mock Jira/Slack). No paid API keys or external accounts required.

---

## Step 0: Start & Seed (Before Demo)
```bash
docker compose --profile demo up --build -d
docker compose exec api python -m app.bootstrap
```
Open `http://localhost:3000/login` and sign in as `admin@acme.local` (or `owner@acme.local`).

---

## 1. Inject Simulated Alert (1 min)
1. Go to **Settings → Alertmanager Integrations**, create a **Simulator Mode** integration, and click **Run Simulator Alert** (or run `python scripts/simulate_incident.py`).
2. Open **Ingestion & Events** (`/events`) to show the persisted `inbound_events` receipt, correlation ID, and `SIMULATED` badge.

## 2. Inspect Incident & Evidence (1.5 min)
1. Open **Incidents** (`/incidents`) and click the newly created `checkout-api` incident.
2. Open **Evidence & KB** (`/evidence`), click **Load Synthetic Demo Logs** and **Load Synthetic Runbooks** (if not yet loaded), and show:
   - Redacted secrets/PII (`[REDACTED_SECRET]`, `[REDACTED_PII]`) in `application_logs`.
   - Hybrid KB search with `SYNTHETIC` badges, scores, and the **Untrusted Reference Data** trust-boundary banner.
3. On the incident page, click **Correlate GitHub Evidence (Read-Only)** (with mock connector configured in `/settings`) to attach `DEMO/MOCK` commit/PR correlation hypotheses.

## 3. Run Read-Only AI Investigation (1.5 min)
1. In the **AI Investigation Copilot (Read-Only)** panel on the incident page, point out the honest `MOCK / DETERMINISTIC` badge and daily tenant quota.
2. Click **Start Read-Only Investigation**.
3. Walk through the **Approved Tool Activity** trace (`get_incident_history`, `search_service_logs`, `correlate_github_evidence`, `search_knowledge_base`), **Observed Facts** with `[EV-*]` citations, **Possible Causes** with confidence badges, and submit **Human Feedback** (`helpful`).

## 4. Human-Gated External Action (1.5 min)
1. In **Settings → External Action Connectors**, add a **Demo / Mock** Jira connector (`OPS, ENG`) and Slack connector (`C01OPS`) and click **Test Connection**.
2. On the incident page (or `/actions`), propose a Jira issue (`OPS`) or Slack message (`C01OPS`).
3. Point out the exact destination, JSON payload preview, `DEMO / MOCK` badge, and `PROPOSED` status.
4. Approve (as a second authorized user when separation of duties is active) and click **Execute** to receive `MOCK-OPS-*` without touching any external account.

## 5. Audit & Observability (1 min)
1. Show the incident **Timeline** and **Audit History** recording every proposal, approval, and execution.
2. Open `http://127.0.0.1:8000/metrics` (and Grafana at `http://127.0.0.1:3001` if `--profile observability` is running) to show low-cardinality HTTP, queue, TTA/TTR, and AI metrics.
