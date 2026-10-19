# ADR 0006 — Paste an agenda: an LLM that suggests, an API that writes

- **Status:** accepted, 2026-10-19
- **Context of:** Lab 6. Architecture in [`docs/architecture.md`](../architecture.md), spec in
  `PROJECT.md` §12 "Agenda parser".

## Context

Agendas do not arrive as forms. They arrive as an email, a chat message or a few lines of notes,
often in Ukrainian with English names in between. Lanora lets a task carry an agenda (topics with
owners and minutes, a start, a length, action items); typing all of that by hand is the reason
people do not.

The feature: paste the text, let an LLM turn it into the agenda form, let the person check it and
press Save. The constraints:

- **No NAT.** The API runs in a VPC without one (Lab 4: $0 when idle). A NAT gateway is ≈ $33 a
  month, a Bedrock interface endpoint ≈ $7.30 a month per AZ.
- **Cost per call.** Every parse is paid for in tokens, so the endpoint must be authenticated and
  capped, and every call must say what it cost.
- **Text from outside.** Pasted text was written by someone else. It may contain instructions
  ("ignore your instructions…"); it is data, never commands.
- **Answers can be wrong with a 200.** The model can invent a date or an owner that is not in the
  text. A person must see and confirm every value before it is stored.
- **This account.** Bedrock's Claude 5.x models (the lab's Opus 5.5 and Haiku 5.5) answer "not
  available for this account" on both APIs, even with their Marketplace agreements accepted. The
  Claude 4.x models are reachable through the Converse API once the account's Anthropic use-case
  form is on file.

## Decision

1. **A separate parser function outside the VPC.** `peach-agenda-parser` (the API's image, its own
   handler, `infra/ai.yml`) receives `{text, today, tz}` and returns a `ParsedAgenda`. It needs
   only Bedrock and the user pool's public keys, both on the internet, and never the database —
   so it sits outside the VPC like the report mailer in Lab 5: no NAT, no endpoint, $0 when nobody
   parses.
2. **The model never writes.** The parser only suggests. The site shows the suggestion as the
   normal agenda form, marks every field the model filled ("suggested") until the person changes
   it, and saves through the existing `POST`/`PATCH /api/v1/items`, with their validation and
   ownership checks. The save also carries the suggestion (`ai_suggestion`, JSONB next to the
   agenda) with the model and the prompt version: every correction is free feedback.
3. **A schema, not prose.** The model answers by calling one tool, `record_agenda`, whose input
   schema is the pydantic `ParsedAgenda`. The result is validated; an invalid answer goes back to
   the model once with its validation error, then the parse fails with `422`. No topics means "no
   agenda" (`422 no_agenda`), not an empty form.
4. **The prompt.** Today's weekday, date and UTC offset (in the user's time zone, sent by the
   browser) so "Monday" and "by Friday" resolve correctly; the text inside `<pasted_text>`; the
   system prompt says it is data, to copy names as written, and to leave unknown fields empty.
   Version `agenda-v1`.
5. **Model: Claude Haiku 4.5 through the Converse API, today.** `PARSER_API` / `PARSER_MODEL`
   are configuration. The code holds both paths behind one `parse_agenda`: `converse`
   (bedrock-runtime, provider-neutral, tool choice can be forced) and `messages` (the Anthropic
   Messages API on bedrock-mantle, the only route to Claude 5.x, no forced tool on Opus 5.5). When
   the account gets Opus 5.5, `PARSER_API=messages PARSER_MODEL=anthropic.claude-opus-5-5 make
   deploy-ai` switches it, with no code change. Haiku 4.5 is also the cheap end: a parse is a
   fraction of a cent (measured in [`docs/lab6.md`](../lab6.md)).
6. **Guard rails for money.** The function URL is public but the handler requires a Cognito ID
   token (`401` otherwise), refuses more than 10,000 characters with `413` before calling the
   model, and logs one JSON line per parse: user, API, model, prompt version, input and output
   tokens, latency, cost in dollars. A $5 monthly AWS Budget for the whole account emails on
   actual and forecast spend.

## Alternatives considered

| Alternative | Why it lost |
|---|---|
| **Call Bedrock from the API, through a VPC interface endpoint** | One function instead of two, and the API could check the agenda against the database. But ≈ $7.30 a month per AZ (two subnets: ≈ $14.60) for an endpoint that serves a few parses a day, breaking "$0 when idle", and it puts a slow, paid, 2–8 s call into the API's request path and its 512 MB function. The parser needs no data, so nothing is gained by putting it next to the data. |
| **The Claude API directly (api.anthropic.com) instead of Bedrock** | Newest models first and no AWS gating, which would have avoided this account's model problem. But it needs an API key stored as a secret and rotated, a second vendor bill outside AWS Budgets, and traffic and logs outside CloudTrail. With Bedrock the function's IAM role is the only credential. |
| **A plain regular-expression parser** | Free, instant, deterministic. But the input is free text in two languages: `1) нові тарифи Pro — Олена, 15 хв` and `- Q4 roadmap status — Maria (20 min)` and "Iryna, please send the ad numbers by end of week" are three different grammars, relative dates need a calendar, and every new phrasing is a new rule. It would also fail silently in the opposite way: missing topics rather than inventing them. Worth keeping as a fallback idea for the most rigid formats only. |
| **Let the model save (a `save_agenda` tool)** | Saves one click, and makes the model the writer: a wrong date or an injected owner goes straight into the database, and the API's validation becomes the only check. The click is the point. |

## Consequences

- **Cost per parse:** with Haiku 4.5, ≈ 1,600 input tokens (the tool schema is most of it) and
  ≈ 250–450 output tokens: ≈ **$0.003**, measured per input in `docs/lab6.md`. Opus 5.5 at the
  lab's prices would be ≈ $0.01. Twenty organisations × 30 agendas a week ≈ 2,600 parses a
  month ≈ **$8 a month** on Haiku 4.5: about one VPC endpoint, which this design does not need.
- **What is logged:** one JSON line per parse (`agenda_parsed` / `agenda_parse_failed`) in
  `/aws/lambda/peach-agenda-parser`, 14 days. The pasted text and the parsed agenda are never
  logged; the suggestion is kept only in the user's own row (`items.ai_suggestion`).
- **When Bedrock is down or throttling:** the dialog says the parser is busy or unavailable and
  offers "Type it by hand"; the agenda form works without the parser, and everything else in
  Lanora (board, list, dashboard, sign-in, weekly report) does not touch Bedrock at all. A build
  without `PARSER_URL` simply has no paste box.
- **Quality is measurable:** `ai_suggestion` vs `agenda` per saved task gives a per-field
  correction rate for each `prompt_version` and model.
- **Prompt injection is contained, not prevented:** the model may obey injected text, but it
  only fills a form that the person reviews; it has no tools that read or write anything; its
  output is validated and rendered as plain text; the save path is the same validated endpoint.
- **Accepted risks:** the role allows `bedrock:InvokeModel` and `bedrock-mantle:CreateInference`
  on `*` (to narrow to the configured model and its inference profile); the public URL limits text
  length but not request rate per user (Cognito sign-ups are free, so a determined abuser can still
  spend the budget — the next step is a per-user daily cap and reserved concurrency on the function).
