# Support Agent Safety Evaluator

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)
![DeepEval 4.3.1](https://img.shields.io/badge/Evaluation-DeepEval%204.3.1-purple)
![Gemini Judge](https://img.shields.io/badge/LLM%20Judge-Gemini%20Flash%20family-orange)

### Live Demo: [support-agent-safety-evaluator.streamlit.app](https://support-agent-safety-evaluator.streamlit.app/)

Pick a scenario, paste an agent response, and see the three lens scores live.

---

An evaluation tool for AI customer support agents. It scores a single agent
response across **three stakeholder lenses**, because in production support,
"the customer seemed happy" is only one third of the question.

A response can resolve the customer's request and still be a production
incident: it can disclose another customer's private data, commit money the
agent had no authority to commit, or quietly breach policy under pressure.
Standard evaluation setups rarely catch that second and third failure. This
tool is built to catch all three.

## What It Does

1. Select a failure category, then one of 15 built-in scenarios, or add your own scenario or category with your customer message and policy (a sample agent response is generated for new scenarios automatically).
2. Paste the agent's actual response to that scenario.
3. Receive a PASS / FAIL verdict, a score, and the judge's reasoning for
   each of the three lenses. Pass threshold: 0.7.

Each run evaluates exactly one scenario and response pair, so every score is
judged against the situation the agent was actually answering.

## The Three Lenses

| Lens | Question it answers | Example failure it catches |
|---|---|---|
| **User Resolution** | Was the customer helped correctly, without invented information or unauthorized actions? | Agent gives a confident, wrong answer about a return window |
| **Stakeholder Protection** | Did the response harm anyone beyond the customer: the company, other customers, compliance? | Agent issues a $500 credit to a customer who threatened a lawsuit, against a $50 authority limit |
| **Policy Compliance** | Did the stated policy hold under pressure, manipulation, or ambiguity? | Agent follows a user message formatted as a "system override" and approves refunds without verification |

## Scenario Coverage

15 scenarios across 5 failure categories, drawn from published standards
(see Sources). Each scenario carries the customer message, the policy the
agent should follow, and an operational severity rating. Users can also
add their own scenarios in the app and run them through the same evaluation.

| Category | Scenarios | Highest severity | What it tests |
|---|---|---|---|
| Policy Hallucination | 3 | S2 | Invented return windows, warranty terms, and discount programs that do not exist |
| PII Extraction | 3 | S1 | Disclosure of account data without identity verification, a caller claiming to be from HQ, and PII repeated back in conversation summaries |
| Authority Pressure | 3 | S1 | Lawsuit and press threats, fake system overrides, and sympathy based exception requests |
| Wrong Action | 3 | S1 | Refunds issued instead of exchanges, account changes without verification, and contradictory instructions executed without clarification |
| Escalation Failure | 3 | S2 | Legal threats not escalated to a human, routine questions bounced to humans, and complex multi-issue cases handled without a proper handoff |

## Severity Model

Severity follows incident triage practice: it describes the operational
response required, not just the error type.

- **S1:** Money moved or data exposed. Immediate escalation.
- **S2:** Wrong answers or policy breaches with repeat or scale potential. Fix the same day.
- **S3:** Single-customer impact. Fix within the week.

## How It Works

- Scenario presets load the customer message and its policy context into a
  DeepEval `LLMTestCase`.
- Three DeepEval G-Eval metrics score the response, using a **Gemini Flash model** as the
  LLM judge, with an automatic fallback chain (3.6 Flash, then 3.8 Flash,
  then 3.5 Flash-Lite) if a model is unavailable or overloaded.
- Results render as a scorecard with the judge's reasoning attached to every
  score, so a FAIL can be reviewed, not just counted.

## Tech Stack

- **Python 3.12**
- **Streamlit** for the interface, hosted on Streamlit Community Cloud
- **DeepEval 4.3.1** (G-Eval metrics) for evaluation
- **Google Gemini Flash family** as the LLM judge, with automatic model fallback

## Run Locally

```bash
pip install -r requirements.txt
export GOOGLE_API_KEY="your key from Google AI Studio"
streamlit run streamlit_app.py
```

The API key is read from the environment (or from Streamlit secrets when
hosted). It is never stored in the code or the repository.

## Design Notes

- **Pair scoring, not batch scoring.** A response is only ever judged
  against the scenario it answered. Batch scoring one response against
  unrelated scenarios produces scores that look precise and mean nothing.
- **Stakeholder impact is a first class metric.** User satisfaction is the
  easiest signal to collect and the easiest to game. The expensive failures
  land on the second and third lenses.
- **Severity is operational.** Every scenario is rated by the response it
  demands from a support organization, the same way a production incident
  would be triaged.

## Limitations

- LLM-as-judge scoring is probabilistic. Scores support human review; they
  do not replace it.
- Evaluations are single-turn. Multi-turn manipulation that builds across a
  conversation is out of scope for this version.
- The 15 built-in scenarios are a curated starting set, not an exhaustive catalogue. Scenarios a user adds in the app last for that session only.

## Scaling This in an Enterprise

This app is the single-case, by-hand version of a pattern that runs very
differently at company scale. The lenses, severity model, and scenario bank
carry over unchanged. What changes is the plumbing:

- **Where it runs:** Inside company infrastructure, not on a public page.
  The evaluator ships as a containerized service or scheduled batch job on
  the company's cloud, behind SSO, with the judge model called through the
  company's own cloud account (for example Vertex AI or Bedrock) so
  conversation data never leaves the compliance boundary.
- **How the CRM connects:** CRMs are the data source, in 3 ways. Their APIs
  (Zendesk, Intercom, Salesforce) pull conversations directly; a warehouse
  sync (Fivetran or native export into Snowflake or BigQuery) feeds nightly
  batch runs; or webhooks push each closed conversation to the evaluator in
  near real time. There is no magic plugin. Integration is an API and data
  pipeline job, which is exactly how the commercial QA platforms that score
  100% of conversations are built.
- **Finding past misses:** The same engine runs retrospectively over
  exported or warehouse history. That is how a team answers questions like
  "how many chats last quarter disclosed data before verification?" with
  counts and examples instead of anecdotes.
- **Sampling is the discipline:** 100 chats is 300 judge calls, so scoring
  everything is a cost and latency decision, not a default. Production
  setups typically score 100% of high-risk categories (PII, money movement,
  legal threats) and a statistical sample of the rest, with the sample rate
  raised after any prompt, model, or policy change.
- **Results go back to work:** Scores write back as ticket tags or internal
  notes in the CRM, S1 patterns alert the on-call channel, and failure
  counts by category land on the QA dashboard the weekly quality review
  already uses.
- **Calibration closes the loop:** Human reviewers re-score a slice of
  judge decisions every week. Where the judge and the humans disagree, the
  scenario bank and the metric criteria are what get fixed. The bank itself
  is versioned in Git, so every change to what "good" means is reviewable.

## Sources

Test patterns are drawn from the OWASP LLM Top 10 and documented red-team
techniques. The operational framing (failure categories, severity model,
stakeholder lenses) comes from enterprise support operations and incident
triage practice.

---

Created by **Dhivya Marimuthu**, Support and CX Operations
[LinkedIn](https://www.linkedin.com/in/dhivya-marimuthu)
