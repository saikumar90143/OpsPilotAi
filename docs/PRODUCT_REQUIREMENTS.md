# OpsPilot AI — Product Requirements (MVP)

## Product summary

OpsPilot AI is an enterprise incident investigation and workflow automation platform for software engineering and IT operations teams. It connects monitoring signals, application logs, source-control activity, engineering knowledge, and ticketing/chat tools so teams can investigate incidents faster and execute approved follow-up actions.

## Primary users

- On-call software engineers
- Site Reliability Engineers (SREs)
- Platform engineering teams
- IT operations leads

## Initial customer problem

During a production incident, evidence is scattered across monitoring tools, logs, GitHub, team documentation, Slack, and issue trackers. Engineers spend time collecting context before they can decide what to do.

## MVP user stories

1. As an engineer, I can see a prioritized list of incidents.
2. As an engineer, I can create an incident manually or through an inbound monitoring webhook.
3. As an engineer, I can inspect incident details and update its status.
4. As an engineer, I can ask an AI copilot to investigate using approved read-only tools.
5. As an engineer, I can review evidence and approve a proposed Jira or Slack action.
6. As an administrator, I can connect integrations and see an audit trail of actions.

## Non-goals for the first release

- Automatically deploying code or modifying production infrastructure.
- Autonomous remediation without human approval.
- Replacing a company's monitoring, ticketing, or source-control systems.
- Claiming definitive root cause when evidence only supports a hypothesis.

## Success metrics to measure in a pilot

- Median time from alert receipt to useful investigation summary.
- Percentage of AI statements supported by retrieved evidence.
- Incident severity classification precision/recall.
- Integration event processing success rate.
- Percentage of proposed actions approved by engineers.
- Cost per investigation and agent execution latency.

Do not publish fabricated performance numbers. Establish a baseline, run a repeatable evaluation set, and report measured results.
