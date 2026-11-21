# Dependency Pinning & Update Policy

## 1. Version Constraints
- **Backend (`backend/requirements.txt`, `requirements-dev.txt`):** Bounded major/minor ranges (`>=X.Y,<Z.0`) to receive patch/security fixes while preventing breaking major upgrades.
- **Frontend (`frontend/package-lock.json`):** Exact lockfile pinning via `npm ci` in CI and Docker builds.

## 2. Vulnerability Scanning
- **Python:** `pip-audit -r backend/requirements.txt` runs in GitHub Actions (`.github/workflows/ci.yml`).
- **Node.js:** `npm audit --audit-level=high` runs in GitHub Actions.
- **Secrets:** `gitleaks/gitleaks-action@v2` scans commits and pull requests.

## 3. Update Cadence
- Review security advisories weekly; apply patch updates immediately via PR and re-run the full backend + frontend + offline AI eval suite.
- Major version upgrades require a dedicated PR and ADR if API contracts or DB drivers change.
