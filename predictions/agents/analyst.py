"""
Analyst Agent
--------------
Pure computation, no LLM call. Takes raw fixture/team data and derives the
signals a human analyst would look at: recent form, scoring trends, head-to-
head record, injury impact.

Keeping this deterministic (plain Python/Decimal math) matters for a
betting product specifically - these numbers must be reproducible and
auditable. The LLM's job (Predictor agent) is reasoning over these
signals, not computing them.
"""
from decimal import Decimal
from collections import Counter

from ..models import Fixtures, TeamForm


def _form_record(results: str) -> dict:
    """
    results: a string like "WWLDW" (most recent last, per most providers'
    convention). Returns counts of wins/draws/losses.
    """
    counts = Counter(results.upper())
    return {
        "wins": counts.get("W", 0),
        "draws": counts.get("D", 0),
        "losses": counts.get("L", 0),
    }


def _safe_avg(values: list) -> Decimal | None:
    nums = [Decimal(str(v)) for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 2)


def _extract_goal_avg(value):
    """
    API-Sports sometimes returns {"home": x, "away": y, "total": z} dicts
    rather than flat lists for goal averages - normalize defensively rather
    than assuming one shape.
    """
    if isinstance(value, dict):
        return value.get("total") or value.get("home") or value.get("away")
    if isinstance(value, list):
        return _safe_avg(value)
    return value


def analyze_fixture(fixture: Fixtures, home_stats: dict, away_stats: dict) -> tuple[TeamForm, TeamForm]:
    """
    Entry point the Coordinator agent calls after data-gathering.

    home_stats / away_stats: dicts shaped like the data-gatherer's
    get_team_stats() output:
        {
            "recent_results": "WWLDW",
            "goals_for": {...} or [...],
            "goals_against": {...} or [...],
            "injuries": [...]
        }

    Returns (home_form, away_form) TeamForm instances, persisted via
    update_or_create - this OVERWRITES any existing TeamForm row for this
    fixture+team rather than creating a new one each run, since we only
    ever want the LATEST computed form, not a history of every recomputation.
    """
    home_record = _form_record(home_stats.get("recent_results", ""))
    away_record = _form_record(away_stats.get("recent_results", ""))

    home_form, _ = TeamForm.objects.update_or_create(
        fixture=fixture,
        team_name=fixture.home_team,
        is_home_team=True,
        defaults={
            "wins_last_5": home_record["wins"],
            "draws_last_5": home_record["draws"],
            "losses_last_5": home_record["losses"],
            "goals_for_avg": _extract_goal_avg(home_stats.get("goals_for", {})),
            "goals_against_avg": _extract_goal_avg(home_stats.get("goals_against", {})),
            "injuries": home_stats.get("injuries", []),
            "head_to_head_summary": _head_to_head_summary(fixture.home_team, fixture.away_team),
        },
    )

    away_form, _ = TeamForm.objects.update_or_create(
        fixture=fixture,
        team_name=fixture.away_team,
        is_home_team=False,
        defaults={
            "wins_last_5": away_record["wins"],
            "draws_last_5": away_record["draws"],
            "losses_last_5": away_record["losses"],
            "goals_for_avg": _extract_goal_avg(away_stats.get("goals_for", {})),
            "goals_against_avg": _extract_goal_avg(away_stats.get("goals_against", {})),
            "injuries": away_stats.get("injuries", []),
            "head_to_head_summary": _head_to_head_summary(fixture.away_team, fixture.home_team),
        },
    )

    return home_form, away_form


def _head_to_head_summary(team_a: str, team_b: str) -> dict:
    """
    Looks at past Fixtures rows between these two teams in our own DB
    (built up over time as we ingest more fixtures) to compute h2h record.
    Returns empty dict if we don't have history yet - that's a real and
    expected state early on, not an error.
    """
    past_fixtures = Fixtures.objects.filter(
        status='finished',
        home_team__in=[team_a, team_b],
        away_team__in=[team_a, team_b],
    ).order_by('-kickoff_time')[:10]

    if not past_fixtures:
        return {}

    team_a_wins = 0
    team_b_wins = 0
    draws = 0

    for f in past_fixtures:
        if f.home_score is None or f.away_score is None:
            continue
        if f.home_score == f.away_score:
            draws += 1
        elif (f.home_team == team_a and f.home_score > f.away_score) or \
             (f.away_team == team_a and f.away_score > f.home_score):
            team_a_wins += 1
        else:
            team_b_wins += 1

    return {
        "matches_considered": len(past_fixtures),
        f"{team_a}_wins": team_a_wins,
        f"{team_b}_wins": team_b_wins,
        "draws": draws,
    }


def build_analysis_payload(fixture: Fixtures, home_form: TeamForm, away_form: TeamForm) -> dict:
    """
    Packages the computed signals into the clean, structured payload that
    gets handed to the Predictor agent's LLM prompt. The LLM never sees raw
    API responses - only this distilled summary.
    """
    latest_odds = fixture.odds.order_by('-captured_at').first()

    return {
        "fixture": {
            "sport": fixture.sport,
            "home_team": fixture.home_team,
            "away_team": fixture.away_team,
            "league": fixture.league,
            "kickoff_time": fixture.kickoff_time.isoformat(),
        },
        "home_form": {
            "record_last_5": f"{home_form.wins_last_5}W-{home_form.draws_last_5}D-{home_form.losses_last_5}L",
            "goals_for_avg": float(home_form.goals_for_avg) if home_form.goals_for_avg else None,
            "goals_against_avg": float(home_form.goals_against_avg) if home_form.goals_against_avg else None,
            "injuries": home_form.injuries,
        },
        "away_form": {
            "record_last_5": f"{away_form.wins_last_5}W-{away_form.draws_last_5}D-{away_form.losses_last_5}L",
            "goals_for_avg": float(away_form.goals_for_avg) if away_form.goals_for_avg else None,
            "goals_against_avg": float(away_form.goals_against_avg) if away_form.goals_against_avg else None,
            "injuries": away_form.injuries,
        },
        "head_to_head": home_form.head_to_head_summary,
        "market_odds": {
            "bookmaker": latest_odds.bookmaker,
            "home_odds": float(latest_odds.home_odds) if latest_odds.home_odds else None,
            "draw_odds": float(latest_odds.draw_odds) if latest_odds.draw_odds else None,
            "away_odds": float(latest_odds.away_odds) if latest_odds.away_odds else None,
        } if latest_odds else None,
    }