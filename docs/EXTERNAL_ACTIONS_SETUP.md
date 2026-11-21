# External Action Connectors — Real Setup Guide (Jira & Slack)

By default, OpsPilot AI uses deterministic **Demo / Mock** adapters for Jira and Slack so all workflows and tests run safely without external credentials.

## 1. Jira Cloud (`mode="live"`)
- **Required Scope:** `write:jira-work` (narrowly scoped to project issue creation; no admin or delete scopes).
- **Setup:**
  1. Create an Atlassian OAuth 2.0 (3LO) app or scoped API token with `write:jira-work`.
  2. In **Settings → External Action Connectors**, select **Jira**, **Live Mode**, enter your `https://<domain>.atlassian.net` base URL, allowlisted project keys (e.g. `OPS, ENG`), and token.
  3. Click **Test Connection** to verify `/rest/api/3/myself` and scope diagnostics.

## 2. Slack (`mode="live"`)
- **Required Bot Token Scope:** `chat:write` only (no `channels:read`, `users:read`, or admin scopes needed).
- **Setup:**
  1. Create a Slack App in your workspace, add Bot Token Scope `chat:write`, install to workspace, and invite the bot to the target channel(s).
  2. In **Settings → External Action Connectors**, select **Slack**, **Live Mode**, enter allowlisted channel IDs (e.g. `C01OPS`), and paste the bot token (`xoxb-...`).
  3. Click **Test Connection** to verify `auth.test`.
