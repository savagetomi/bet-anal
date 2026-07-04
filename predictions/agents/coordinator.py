"""
Coordinator Agent
------------------
The single entry point that views.py calls. Orchestrates data-gathering,
analysis, and prediction in sequence.

Prediction caching strategy: PERMANENT
  - Once a Prediction row exists for a fixture, it is ALWAYS reused.
  - Predictions are generated once daily at midnight by a scheduled job
    (see predictions/tasks.py).
  - force_refresh=True is the only way to override this - reserved for
    genuine data changes (key injury, lineup announcement, etc).
  - Users hitting the read endpoints always get the pre-computed result
    from the midnight run - they never trigger LLM calls directly.
"""
from django.utils import timezone

from ..models import Fixtures, Prediction
from .data_gatherer import fetch_and_store_fixtures, get_provider_for
from .analyst import analyze_fixture, build_analysis_payload
from .predictor import predict_fixture


def get_predictions_for_sport(
    sport: str,
    date_from=None,
    date_to=None,
    force_refresh: bool = False
) -> list[dict]:
    """
    Full pipeline for all upcoming fixtures of one sport.
    Called by the midnight scheduled job, not by user-facing endpoints.
    Returns a list of result dicts (predictions + any per-fixture errors).
    """
    fixtures = fetch_and_store_fixtures(sport, date_from, date_to)
    stats_provider = get_provider_for(sport, prefer="api-sports")
    results = []

    for fixture in fixtures:
        # Permanent cache: if ANY prediction exists for this fixture,
        # return it immediately unless force_refresh=True.
        if not force_refresh:
            existing = _get_existing_prediction(fixture)
            if existing:
                results.append(_build_result(fixture, existing))
                continue

        result = _run_pipeline_for_fixture(fixture, stats_provider, sport)
        results.append(result)

    return results


def get_prediction_for_single_fixture(
    fixture_id: str,
    force_refresh: bool = False
) -> dict:
    """
    Returns the prediction for one specific fixture.
    If no prediction exists yet (midnight job hasn't run), raises
    RuntimeError so the view can return a meaningful 404-style response.
    """
    fixture = Fixtures.objects.get(id=fixture_id)

    if not force_refresh:
        existing = _get_existing_prediction(fixture)
        if existing:
            return _build_result(fixture, existing)

    # No existing prediction and force_refresh=False means the midnight
    # job hasn't run yet for this fixture. Don't generate on demand -
    # tell the caller to try again after midnight.
    if not force_refresh:
        raise RuntimeError(
            f"No prediction available yet for {fixture}. "
            f"Predictions are generated daily at midnight."
        )

    # force_refresh=True: re-run the pipeline regardless of existing predictions
    stats_provider = get_provider_for(fixture.sport, prefer="api-sports")
    result = _run_pipeline_for_fixture(fixture, stats_provider, fixture.sport)

    if "error" in result:
        raise RuntimeError(result["error"])

    return result


def _get_existing_prediction(fixture: Fixtures):
    """
    Returns the most recent Prediction for this fixture if one exists,
    otherwise None. No time window - any existing prediction is valid.
    """
    return fixture.predictions.order_by('-created_at').first()


def _run_pipeline_for_fixture(fixture: Fixtures, stats_provider, sport: str) -> dict:
    """
    Runs the full data-gather -> analyze -> predict pipeline for one fixture.
    Returns a result dict - either a full prediction or an error entry.
    Never raises: all exceptions are caught and recorded in the result dict
    so a single fixture failure doesn't kill a batch run.
    """
    # Step 1: fetch team stats (data-gatherer)
    try:
        home_stats = stats_provider.get_team_stats(fixture.home_team, sport)
        away_stats = stats_provider.get_team_stats(fixture.away_team, sport)
    except Exception as e:
        return _build_error(fixture, f"Could not fetch team stats: {e}")

    # Step 2: compute form signals (analyst)
    try:
        home_form, away_form = analyze_fixture(fixture, home_stats, away_stats)
        analysis_payload = build_analysis_payload(fixture, home_form, away_form)
    except Exception as e:
        return _build_error(fixture, f"Analysis failed: {e}")

    # Step 3: generate prediction (predictor / LLM call)
    try:
        prediction = predict_fixture(fixture, analysis_payload)
    except ValueError as e:
        return _build_error(fixture, f"Prediction validation failed: {e}")
    except Exception as e:
        return _build_error(fixture, f"Prediction failed: {e}")

    return _build_result(fixture, prediction)


def _build_result(fixture: Fixtures, prediction: Prediction) -> dict:
    return {
        "fixture_id": str(fixture.id),
        "sport": fixture.sport,
        "home_team": fixture.home_team,
        "away_team": fixture.away_team,
        "league": fixture.league,
        "kickoff_time": fixture.kickoff_time.isoformat(),
        "prediction": {
            "id": str(prediction.id),
            "outcomes": prediction.outcomes,
            "confidence": float(prediction.confidence),
            "reasoning": prediction.reasoning,
            "key_factors": getattr(prediction, '_key_factors', []),
            "model_used": prediction.model_used,
            "created_at": prediction.created_at.isoformat(),
        },
    }


def _build_error(fixture: Fixtures, message: str) -> dict:
    return {
        "fixture_id": str(fixture.id),
        "sport": fixture.sport,
        "home_team": fixture.home_team,
        "away_team": fixture.away_team,
        "league": fixture.league,
        "kickoff_time": fixture.kickoff_time.isoformat(),
        "error": message,
    }