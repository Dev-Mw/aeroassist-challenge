# Public evaluation model

The final score is 100 points: 60 automated and 40 human-reviewed. Each progressive level is worth 20 points.

## Automated evidence

- API contract and remote health
- basic conversational behavior
- correct tool selection and arguments
- no write tool before confirmation
- expected policy citations
- abstention for unsupported questions
- latency/error behavior under bounded probes
- repository and delivery evidence

The evaluator uses additional cases not included in this repository. It does not require exact wording and does not score chain-of-thought.

## Human evidence

- architecture and separation of concerns
- test quality and maintainability
- retrieval and evaluation reasoning
- safety, reliability and cost controls
- cloud identity, CI/CD and rollback
- clarity of decisions and ownership

## Gates

- A live HTTPS service is required for a score of 70 or higher unless a documented external incident is waived by the panel.
- Exposed real credentials or unconfirmed state-changing actions trigger a security review independent of numeric score.
- You must be able to explain and modify the submitted code in the follow-up interview.

