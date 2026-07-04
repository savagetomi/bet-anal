"""
Predictor Agent
----------------
The ONLY agent in the pipeline that calls an LLM. It receives the Analyst's
clean, structured signal payload (never raw API data) and produces:

  - A single coherent read of the match, expressed across multiple bet
    market formats inside `outcomes`
  - One overall confidence score
  - A plain-language explanation of the reasoning

Key design decisions:
  - The LLM only fills in `pick` per market. `was_correct` is always null
    at prediction time - only the Prediction.grade() method fills that in
    later, once the match resolves.
  - The prompt forces the LLM to reason ONLY from the structured stats
    given, not from its training knowledge about specific teams (which
    may be outdated or wrong).
  - JSON output is enforced at the prompt level, with defensive parsing
    as a fallback.
"""
import os
import json
import anthropic

from ..models import Fixtures, Prediction

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are a sports prediction engine for a betting research platform.
You will receive structured match statistics: recent form, scoring averages,
head-to-head history, injuries, and current bookmaker odds.

Your job is to reason over these signals and produce predictions for multiple
bet market formats. IMPORTANT RULES:

1. Base your reasoning ONLY on the statistics provided. Do NOT rely on
   general knowledge about these teams - the data given is more current
   and reliable than your training data.

2. If data for a specific field is null or missing, say so in your
   reasoning. Never invent statistics.

3. `was_correct` must ALWAYS be null - you are predicting, not grading.

4. Each market has STRICTLY defined valid pick values:

   1x2:
     - "home_win", "away_win", or "draw"

   double_chance:
     - "home_or_draw", "away_or_draw", or "home_or_away"

   correct_score:
     - A string in the format "X-Y" e.g. "2-1", "0-0", "1-3"
     - Home score first, away score second

   btts (both teams to score):
     - "yes" or "no"

   handicap:
     - An object: {"line": <number>, "side": "home" or "away"}
     - Example: {"line": -1.5, "side": "home"} means home team
       must win by more than 1.5 goals

5. `confidence` is a single number 0-100 representing your overall
   certainty in this read of the match. Be honest:
     - 50-60: very uncertain, close match, thin data
     - 61-74: moderate confidence, some clear signals
     - 75-84: good confidence, multiple signals agree
     - 85+: only when data is overwhelming and consistent

6. `reasoning` must be 2-4 sentences citing SPECIFIC numbers from the
   input (e.g. "Arsenal's 4W-0D-1L record..." not "the home team has
   been performing well...").

Respond ONLY with valid JSON matching this exact shape, nothing else,
no markdown fences, no preamble:

{
  "outcomes": {
    "1x2": {"pick": "<home_win|away_win|draw>", "was_correct": null},
    "double_chance": {"pick": "<home_or_draw|away_or_draw|home_or_away>", "was_correct": null},
    "correct_score": {"pick": "<X-Y>", "was_correct": null},
    "btts": {"pick": "<yes|no>", "was_correct": null},
    "handicap": {"pick": {"line": <number>, "side": "<home|away>"}, "was_correct": null}
  },
  "confidence": <number 0-100>,
  "reasoning": "<2-4 sentences citing specific stats>",
  "key_factors": ["<factor 1>", "<factor 2>", "<factor 3>"]
}"""


VALID_PICKS = {
    "1x2": {"home_win", "away_win", "draw"},
    "double_chance": {"home_or_draw", "away_or_draw", "home_or_away"},
    "btts": {"yes", "no"},
}


def _validate_outcomes(outcomes: dict, fixture: Fixtures) -> list[str]:
    """
    Validates the LLM's picks against known valid values per market.
    Returns a list of validation errors - empty list means all good.
    This is a safety net, not a replacement for a well-written prompt.
    """
    errors = []

    for market, valid_values in VALID_PICKS.items():
        if market not in outcomes:
            errors.append(f"Missing market: {market}")
            continue
        pick = outcomes[market].get("pick")
        if pick not in valid_values:
            errors.append(f"Invalid pick for {market}: '{pick}'. Must be one of {valid_values}")

    # correct_score: must be "X-Y" format
    if "correct_score" in outcomes:
        pick = outcomes["correct_score"].get("pick", "")
        parts = str(pick).split("-")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            errors.append(f"Invalid correct_score pick: '{pick}'. Must be format 'X-Y' e.g. '2-1'")

    # handicap: must be a dict with line (number) and side (home|away)
    if "handicap" in outcomes:
        pick = outcomes["handicap"].get("pick", {})
        if not isinstance(pick, dict):
            errors.append(f"Invalid handicap pick: must be an object with 'line' and 'side'")
        else:
            if "line" not in pick:
                errors.append("Handicap pick missing 'line' field")
            if pick.get("side") not in ("home", "away"):
                errors.append(f"Handicap 'side' must be 'home' or 'away', got: {pick.get('side')}")

    # was_correct must be null on every market
    for market, entry in outcomes.items():
        if entry.get("was_correct") is not None:
            errors.append(f"Market '{market}' has was_correct set to non-null - must be null at prediction time")

    return errors


def _parse_response(raw_text: str) -> dict:
    """
    Defensively parses the LLM's JSON response.
    Strips markdown fences if the model adds them despite prompt instructions -
    this happens more often than you'd expect, even with explicit "no fences"
    instructions, so the defensive strip is always worth having.
    """
    # Strip markdown fences if present
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop the opening fence (```json or ```) and closing fence (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Predictor agent returned invalid JSON.\n"
            f"Raw response: {raw_text[:500]}\n"
            f"Parse error: {e}"
        ) from e


def predict_fixture(fixture: Fixtures, analysis_payload: dict) -> Prediction:
    """
    Entry point the Coordinator agent calls after analysis is complete.

    Takes a Fixtures instance and the Analyst's structured payload,
    calls the LLM, validates the response, and persists + returns a
    Prediction instance.

    Raises ValueError if the LLM returns invalid JSON or invalid picks -
    the Coordinator catches these and records them as errors without
    killing the whole batch.
    """
    user_message = (
        f"Predict the following {analysis_payload['fixture']['sport']} match:\n\n"
        f"{json.dumps(analysis_payload, indent=2)}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text
    parsed = _parse_response(raw_text)

    # Validate the outcomes block before persisting anything
    outcomes = parsed.get("outcomes", {})
    validation_errors = _validate_outcomes(outcomes, fixture)
    if validation_errors:
        raise ValueError(
            f"Predictor agent returned invalid picks for {fixture}:\n"
            + "\n".join(f"  - {e}" for e in validation_errors)
        )

    # Confidence sanity check
    confidence = parsed.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 100):
        raise ValueError(
            f"Predictor agent returned invalid confidence: '{confidence}'. "
            f"Must be a number between 0 and 100."
        )

    prediction = Prediction.objects.create(
        fixture=fixture,
        outcomes=outcomes,
        confidence=confidence,
        reasoning=parsed.get("reasoning", ""),
        model_used="claude-sonnet-4-6",
    )

    # key_factors isn't a model field - stash on the instance so the
    # Coordinator can include it in the API response without a migration.
    # If you later want key_factors persisted long-term, add a JSONField
    # to Prediction and save it here instead.
    prediction._key_factors = parsed.get("key_factors", [])

    return prediction