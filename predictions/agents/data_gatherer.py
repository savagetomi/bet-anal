"""
Data-Gatherer Agent
--------------------
Pure I/O. No LLM calls here - this agent's only job is to fetch fixtures,
odds, and team stats from external providers and normalize them into our
internal models, regardless of which sport or provider is used.

Provider abstraction means swapping The Odds API for SportRadar later only
means writing a new class that implements `BaseSportsDataProvider` -
nothing else in the pipeline changes.
"""
import os
import requests
from abc import ABC, abstractmethod
from datetime import datetime
from django.utils import timezone

from ..models import Fixtures, Oddsnapshot, Sports


class BaseSportsDataProvider(ABC):
    """All providers must normalize their response into this shape."""

    @abstractmethod
    def get_fixtures(self, sport: str, date_from=None, date_to=None) -> list[dict]:
        """
        Returns a list of dicts shaped like:
        {
            "provider_fixture_id": str,
            "home_team": str,
            "away_team": str,
            "league": str,
            "kickoff_time": datetime,
            "status": str,
        }
        """
        raise NotImplementedError

    @abstractmethod
    def get_odds(self, provider_fixture_id: str, sport: str) -> list[dict]:
        """
        Returns a list of dicts shaped like:
        {
            "bookmaker": str,
            "home_odds": float | None,
            "draw_odds": float | None,
            "away_odds": float | None,
        }
        """
        raise NotImplementedError

    @abstractmethod
    def get_team_stats(self, team_name: str, sport: str, last_n: int = 5) -> dict:
        """
        Returns recent results, e.g.:
        {
            "recent_results": "WWLDW",
            "goals_for": [...] or {...},
            "goals_against": [...] or {...},
            "injuries": [...],
        }
        """
        raise NotImplementedError


class OddsAPIProvider(BaseSportsDataProvider):
    """
    Wraps The Odds API (https://the-odds-api.com).
    Good for live odds across football, basketball, tennis with one API key.
    Does NOT supply team stats - paired with APISportsProvider for that.
    """
    BASE_URL = "https://api.the-odds-api.com/v4"

    SPORT_KEY_MAP = {
        Sports.FOOTBALL: "soccer_epl",       # NOTE: one league only - expand per league as needed
        Sports.BASKETBALL: "basketball_nba",
        Sports.TENNIS: "tennis_atp_aus_open_singles",  # tennis keys are tournament-specific
    }

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ODDS_API_KEY")
        if not self.api_key:
            raise ValueError("ODDS_API_KEY is not set in environment variables.")

    def get_fixtures(self, sport: str, date_from=None, date_to=None) -> list[dict]:
        sport_key = self.SPORT_KEY_MAP.get(sport)
        if not sport_key:
            return []

        resp = requests.get(
            f"{self.BASE_URL}/sports/{sport_key}/odds",
            params={"apiKey": self.api_key, "regions": "uk,eu", "markets": "h2h"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        fixtures = []
        for event in data:
            fixtures.append({
                "provider_fixture_id": event["id"],
                "home_team": event["home_team"],
                "away_team": event["away_team"],
                "league": event.get("sport_title", sport),
                "kickoff_time": datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00")),
                "status": "scheduled",
            })
        return fixtures

    def get_odds(self, provider_fixture_id: str, sport: str) -> list[dict]:
        sport_key = self.SPORT_KEY_MAP.get(sport)
        resp = requests.get(
            f"{self.BASE_URL}/sports/{sport_key}/odds",
            params={"apiKey": self.api_key, "regions": "uk,eu", "markets": "h2h"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        event = next((e for e in data if e["id"] == provider_fixture_id), None)
        if not event:
            return []

        odds_list = []
        for bookmaker in event.get("bookmakers", []):
            h2h_market = next((m for m in bookmaker["markets"] if m["key"] == "h2h"), None)
            if not h2h_market:
                continue
            outcomes = {o["name"]: o["price"] for o in h2h_market["outcomes"]}
            odds_list.append({
                "bookmaker": bookmaker["title"],
                "home_odds": outcomes.get(event["home_team"]),
                "draw_odds": outcomes.get("Draw"),
                "away_odds": outcomes.get(event["away_team"]),
            })
        return odds_list

    def get_team_stats(self, team_name: str, sport: str, last_n: int = 5) -> dict:
        raise NotImplementedError(
            "OddsAPIProvider doesn't supply team stats. Use APISportsProvider for this."
        )


class APISportsProvider(BaseSportsDataProvider):
    """
    Wraps the api-sports.io family: API-Football, API-Basketball, API-Tennis.
    Same auth header and response shape across all three - just a different host.
    """
    HOST_MAP = {
        Sports.FOOTBALL: "v3.football.api-sports.io",
        Sports.BASKETBALL: "v1.basketball.api-sports.io",
        Sports.TENNIS: "v1.tennis.api-sports.io",
    }

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("API_SPORTS_KEY")
        if not self.api_key:
            raise ValueError("API_SPORTS_KEY is not set in environment variables.")

    def _headers(self, sport: str) -> dict:
        return {
            "x-rapidapi-host": self.HOST_MAP[sport],
            "x-rapidapi-key": self.api_key,
        }

    def get_fixtures(self, sport: str, date_from=None, date_to=None) -> list[dict]:
        host = self.HOST_MAP.get(sport)
        if not host:
            return []

        params = {}
        if date_from:
            params["from"] = date_from.strftime("%Y-%m-%d")
        if date_to:
            params["to"] = date_to.strftime("%Y-%m-%d")

        resp = requests.get(
            f"https://{host}/fixtures",
            headers=self._headers(sport),
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        fixtures = []
        for item in data.get("response", []):
            fixture_info = item.get("fixture", item)  # shape varies slightly by sub-API
            teams = item.get("teams", {})
            fixtures.append({
                "provider_fixture_id": str(fixture_info.get("id")),
                "home_team": teams.get("home", {}).get("name", "Unknown"),
                "away_team": teams.get("away", {}).get("name", "Unknown"),
                "league": item.get("league", {}).get("name", sport),
                "kickoff_time": datetime.fromisoformat(fixture_info["date"]) if fixture_info.get("date") else timezone.now(),
                "status": fixture_info.get("status", {}).get("short", "scheduled"),
            })
        return fixtures

    def get_odds(self, provider_fixture_id: str, sport: str) -> list[dict]:
        host = self.HOST_MAP.get(sport)
        resp = requests.get(
            f"https://{host}/odds",
            headers=self._headers(sport),
            params={"fixture": provider_fixture_id},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        odds_list = []
        for item in data.get("response", []):
            for bookmaker in item.get("bookmakers", []):
                bets = bookmaker.get("bets", [])
                match_winner_bet = next((b for b in bets if b.get("name") in ("Match Winner", "Home/Away")), None)
                if not match_winner_bet:
                    continue
                values = {v["value"]: float(v["odd"]) for v in match_winner_bet.get("values", [])}
                odds_list.append({
                    "bookmaker": bookmaker.get("name"),
                    "home_odds": values.get("Home"),
                    "draw_odds": values.get("Draw"),
                    "away_odds": values.get("Away"),
                })
        return odds_list

    def get_team_stats(self, team_name: str, sport: str, last_n: int = 5) -> dict:
        host = self.HOST_MAP.get(sport)
        # NOTE: simplified - real usage needs team_name -> team_id resolution
        # first (a separate /teams search call), cached so you're not
        # re-resolving the same team's ID on every pipeline run.
        resp = requests.get(
            f"https://{host}/teams/statistics",
            headers=self._headers(sport),
            params={"team": team_name, "last": last_n},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("response", {})

        return {
            "recent_results": data.get("form", ""),
            "goals_for": data.get("goals", {}).get("for", {}).get("average", {}),
            "goals_against": data.get("goals", {}).get("against", {}).get("average", {}),
            "injuries": data.get("injuries", []),
        }


def get_provider_for(sport: str, prefer: str = "api-sports") -> BaseSportsDataProvider:
    """Factory - pick the right provider. Swap this if you add a new vendor."""
    if prefer == "odds-api":
        return OddsAPIProvider()
    return APISportsProvider()


def fetch_and_store_fixtures(sport: str, date_from=None, date_to=None) -> list[Fixtures]:
    """
    Entry point the Coordinator agent calls.
    Fetches fixtures + odds, upserts them into the DB, returns Fixtures objects.
    
    
    Uses update_or_create() keyed on (provider, provider_fixture_id) - this
    relies directly on the unique_together constraint set on Fixtures.Meta,
    so re-running this never creates duplicate rows for the same fixture.
    """
    stats_provider = get_provider_for(sport, prefer="api-sports")
    odds_provider = get_provider_for(sport, prefer="odds-api")

    raw_fixtures = stats_provider.get_fixtures(sport, date_from, date_to)
    stored_fixtures = []

    for raw in raw_fixtures:
        fixture, _created = Fixtures.objects.update_or_create(
            provider="api-sports",
            provider_fixture_id=raw["provider_fixture_id"],
            defaults={
                "sport": sport,
                "home_team": raw["home_team"],
                "away_team": raw["away_team"],
                "league": raw.get("league"),
                "kickoff_time": raw["kickoff_time"],
                "status": raw.get("status", "scheduled"),
                "raw_data": raw,
            },
        )
        stored_fixtures.append(fixture)

        try:
            odds = odds_provider.get_odds(raw["provider_fixture_id"], sport)
            for o in odds:
                Oddsnapshot.objects.create(
                    fixture=fixture,
                    bookmaker=o["bookmaker"],
                    home_odds=o.get("home_odds"),
                    draw_odds=o.get("draw_odds"),
                    away_odds=o.get("away_odds"),
                )
        except Exception:
            # Odds provider might use a different fixture ID scheme than
            # api-sports - don't let an odds failure block fixture storage.
            # TODO: log this properly once logging is set up.
            pass

    return stored_fixtures