"""Transcript import helpers for Tria (Stage 1).

Pure functions only, no Streamlit, so they can be unit-tested directly.
The app imports these; the judge engine itself stays in streamlit_app.py
and transcript turns are scored through the exact same run_evaluation
function as a single pasted reply.

NOTE: the deployed app inlines these functions in streamlit_app.py
(Streamlit Cloud raised ImportError on the sibling import even with this
file present at the repo root and byte-identical). This file is kept for
unit tests only. Edit streamlit_app.py, not this file.
"""

HISTORY_CHARS = 2000

# Demo governor: a synchronous Streamlit run cannot bound an unbounded
# transcript (N agent turns x 3 sequential judge calls, plus Gemini rate
# limits, plus no partial-result persistence if the session drops). Cap
# transcript scoring at the first 5 agent turns and say so in the UI;
# longer transcripts are scored by splitting the file or via batch CSV.
DEMO_AGENT_TURN_CAP = 5


def apply_demo_cap(inputs, cap=DEMO_AGENT_TURN_CAP):
    """Cap a transcript run at the first `cap` agent-turn inputs.

    Returns (capped_inputs, was_capped, total_inputs). The verdict covers
    only the capped turns; the caller must disclose that when capped.
    """
    return inputs[:cap], len(inputs) > cap, len(inputs)


def _turn_text(content):
    """Extract plain text from a turn's content: a string, a list of
    OpenAI-style text parts, or a list of plain strings."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for piece in content:
            if isinstance(piece, dict):
                text = piece.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(piece, str):
                parts.append(piece)
        return "\n".join(parts)
    return ""


def _normalize_role(role):
    role = str(role or "").strip().lower()
    if role in ("user", "customer", "human"):
        return "customer"
    if role in ("assistant", "agent", "ai", "bot"):
        return "agent"
    return None


def parse_transcript(data):
    """Parse an uploaded conversation into ordered turns.

    Accepts a bare list of turns, or an object with a turns, messages, or
    conversation list. Each turn needs a role (user/customer/assistant/
    agent and common variants) and content (a string, or OpenAI-style
    text parts). Turns with other roles (system, tool) are skipped, and
    empty turns are dropped. Returns (turns, error) where turns is a list
    of {"role": "customer"|"agent", "text": str} in conversation order.
    """
    if isinstance(data, dict):
        items = None
        for key in ("turns", "messages", "conversation"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
        if items is None:
            return None, (
                "No turns, messages, or conversation list found in this file."
            )
    elif isinstance(data, list):
        items = data
    else:
        return None, (
            "This file is not a conversation: expected a list of turns, or "
            "an object with turns, messages, or conversation."
        )
    turns = []
    for item in items:
        if not isinstance(item, dict):
            continue
        role = _normalize_role(item.get("role"))
        if role is None:
            continue
        text = _turn_text(item.get("content", item.get("text", item.get("message", ""))))
        if text.strip():
            turns.append({"role": role, "text": text})
    if not any(t["role"] == "agent" for t in turns):
        return None, "No agent turns found in this conversation."
    return turns, None


def build_turn_inputs(turns):
    """Build one scoring input per agent turn.

    Each agent turn is judged against the preceding customer message, with
    earlier turns supplied as context so cross-turn failures (a leak from
    history, a handoff that drops context) stay detectable. Returns a list
    of {"index", "customer_message", "agent_text", "scenario_input"} where
    index is the 1-based position in the full transcript.
    """
    inputs = []
    for i, turn in enumerate(turns):
        if turn["role"] != "agent":
            continue
        prior = turns[:i]
        customer_message = ""
        for earlier in reversed(prior):
            if earlier["role"] == "customer":
                customer_message = earlier["text"]
                break
        history = "\n".join(
            f"{t['role']}: {t['text']}" for t in prior
        )
        if len(history) > HISTORY_CHARS:
            history = "[earlier turns omitted]\n" + history[-HISTORY_CHARS:]
        if customer_message and history:
            scenario_input = (
                f"Customer message: {customer_message}\n"
                f"Conversation so far:\n{history}"
            )
        elif history:
            scenario_input = f"Conversation so far:\n{history}"
        else:
            scenario_input = "(conversation opened by the agent)"
        inputs.append({
            "index": i + 1,
            "customer_message": customer_message,
            "agent_text": turn["text"],
            "scenario_input": scenario_input,
        })
    return inputs


def summarize_transcript(per_turn, severity, overall_decision):
    """Roll per-turn results into one conversation verdict.

    per_turn is a list of {"turn": int, "results": [...]} in run_evaluation
    shape. If any turn has an ERROR lens, the conversation is INCOMPLETE.
    Otherwise the worst turn (the first turn with any FAIL, else the turn
    with the lowest minimum lens score) feeds the same release-decision
    function as a single run, with the severity the user selected for
    this conversation type.
    """
    lens_names = []
    for entry in per_turn:
        for result in entry["results"]:
            if result["name"] not in lens_names:
                lens_names.append(result["name"])
    per_lens_fails = {name: 0 for name in lens_names}
    passed_all = 0
    for entry in per_turn:
        statuses = [r["status"] for r in entry["results"]]
        if statuses and all(s == "PASS" for s in statuses):
            passed_all += 1
        for result in entry["results"]:
            if result["status"] == "FAIL":
                per_lens_fails[result["name"]] += 1
    if any(r["status"] == "ERROR" for entry in per_turn for r in entry["results"]):
        return {
            "turns_total": len(per_turn),
            "passed_all": passed_all,
            "per_lens_fails": per_lens_fails,
            "worst_turn": None,
            "verdict": "INCOMPLETE",
            "action": (
                "At least one turn could not be judged. Re-run before "
                "making a release decision."
            ),
        }
    failed = [e for e in per_turn if any(r["status"] == "FAIL" for r in e["results"])]
    if failed:
        worst = failed[0]
    else:
        def min_score(entry):
            scores = [r["score"] for r in entry["results"] if r["score"] is not None]
            return min(scores) if scores else 1.0
        worst = min(per_turn, key=min_score)
    verdict, action = overall_decision(worst["results"], severity)
    return {
        "turns_total": len(per_turn),
        "passed_all": passed_all,
        "per_lens_fails": per_lens_fails,
        "worst_turn": worst["turn"],
        "verdict": verdict,
        "action": action,
    }


def resolve_share_link(params, scenarios_by_id):
    """Validate share-link parameters (?scenario=<id>&response=<text>).

    params maps names to values (a single value, or a one-item list, both
    accepted). The scenario id is the authority: its bank category is
    used even if a category parameter disagrees. Returns a dict with
    category, scenario_id, response, preload (True when a response was
    supplied), and error (None when valid).
    """
    def first(value):
        if isinstance(value, list):
            return value[0] if value else ""
        return value if value is not None else ""

    scenario_id = str(first(params.get("scenario", ""))).strip()
    if not scenario_id:
        return {"category": "", "scenario_id": "", "response": "",
                "preload": False, "error": "No scenario in this link."}
    scenario = scenarios_by_id.get(scenario_id)
    if scenario is None:
        return {"category": "", "scenario_id": "", "response": "",
                "preload": False,
                "error": f"Scenario '{scenario_id}' is not in the bank."}
    response = str(first(params.get("response", "")))
    return {"category": scenario["category"], "scenario_id": scenario_id,
            "response": response, "preload": bool(response), "error": None}
