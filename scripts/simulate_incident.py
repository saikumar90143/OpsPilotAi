"""Synthetic incident simulation script (local dev/demo only; never uses real secrets).

Usage (from repository root, with backend running on http://localhost:8000):
    python scripts/simulate_incident.py --email admin@acme.local --password <DEMO_PASSWORD>
"""

import argparse
import json
import urllib.request


def _req(url: str, *, method: str = "GET", body: dict | None = None, headers: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8")), resp.headers


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a synthetic OpsPilot incident workflow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    urllib.request.install_opener(opener)

    _, login_data, headers = _req(
        f"{args.base_url}/api/v1/auth/login",
        method="POST",
        body={"email": args.email, "password": args.password},
    )
    csrf = ""
    for cookie in headers.get_all("Set-Cookie") or []:
        if "opspilot_csrf=" in cookie:
            csrf = cookie.split("opspilot_csrf=", 1)[1].split(";", 1)[0]
    auth_headers = {"X-CSRF-Token": csrf}

    _req(f"{args.base_url}/api/v1/evidence/logs/load-fixtures", method="POST", headers=auth_headers)
    _req(f"{args.base_url}/api/v1/evidence/kb/load-fixtures", method="POST", headers=auth_headers)
    _, inc, _ = _req(
        f"{args.base_url}/api/v1/incidents",
        method="POST",
        headers=auth_headers,
        body={
            "title": "[SYNTHETIC] Checkout DB pool exhaustion simulation",
            "description": "Simulated incident for observability and copilot verification.",
            "service": "checkout-api",
            "environment": "production",
            "severity": "high",
        },
    )
    _, inv, _ = _req(
        f"{args.base_url}/api/v1/incidents/{inc['id']}/investigations",
        method="POST",
        headers=auth_headers,
        body={"window_hours": 24},
    )
    print(f"Simulated incident #{inc['id']} -> investigation #{inv['id']} ({inv['status']})")
    print(f"Login user: {login_data.get('user', {}).get('email', args.email)}")


if __name__ == "__main__":
    main()
