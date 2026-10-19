# Lanora — containers (C4, level 2)

Every box is something that runs or stores data; every arrow is a call, with the protocol on it.
Lab 6 added the agenda parser and Amazon Bedrock, and two paths that must not be confused:
**parse** (browser → parser → Bedrock), which only suggests, and **save** (browser → API → RDS),
which is the only one that writes. The decision is recorded in
[ADR 0006](adr/0006-llm-agenda-parsing.md).

```mermaid
flowchart TB
    user(["<b>Person</b><br/>signed-in Lanora user"])

    subgraph aws["AWS, us-east-1"]
        site["<b>Web app</b><br/>Next.js static export<br/>S3 + CloudFront · app.mylanora.world"]
        cognito["<b>Cognito user pool</b><br/>managed login, password + Google<br/>issues ID tokens"]
        api["<b>API</b><br/>FastAPI on Lambda, in the VPC<br/>CloudFront + function URL · api.mylanora.world"]
        db[("<b>RDS PostgreSQL</b><br/>users, items<br/>items.agenda, items.ai_suggestion")]
        parser["<b>Agenda parser</b> · Lab 6<br/>Lambda, outside the VPC, function URL<br/>validates the model's answer, writes nothing"]
        bedrock["<b>Amazon Bedrock</b><br/>Claude (Converse API today;<br/>Messages API for Claude 5.x)"]
        reports["<b>Weekly report</b> · Lab 5<br/>Scheduler → SQS → builder → S3 → mailer → SES"]
        logs["<b>CloudWatch Logs</b><br/>one JSON line per parse:<br/>model, prompt version, tokens, latency, cost"]
    end

    user -->|"HTTPS"| site
    site -->|"sign in · OIDC"| cognito
    site ==>|"<b>1 · parse</b><br/>POST text + today + tz, ID token<br/>HTTPS / JSON"| parser
    parser ==>|"<b>1 · parse</b><br/>Converse, tool record_agenda<br/>IAM role, no keys"| bedrock
    parser -->|"JWKS"| cognito
    parser -.->|"log line"| logs
    site ==>|"<b>2 · save</b><br/>POST / PATCH /api/v1/items<br/>agenda + ai_suggestion, ID token"| api
    api ==>|"<b>2 · save</b><br/>SQL"| db
    reports -->|"SQL, read-only"| db

    classDef new fill:#e8f0fe,stroke:#3b6fd8,color:#1b2b4b
    class parser,bedrock new
```

| Container | Runs | Talks to | Why it is where it is |
|---|---|---|---|
| Web app | S3 + CloudFront | Cognito, API, parser | static files, no server |
| API | Lambda in the VPC | RDS | the only writer; validates every agenda it saves |
| Agenda parser | Lambda outside the VPC | Bedrock, Cognito JWKS | needs the internet, never the database: no NAT, no endpoint, $0 when idle |
| Amazon Bedrock | AWS-managed | — | Claude behind IAM; the bill is the AWS bill |
| RDS PostgreSQL | `db.t4g.micro` | — | the agenda and the parser's suggestion side by side in `items` |
