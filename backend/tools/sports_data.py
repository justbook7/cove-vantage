"""
Sports data tool for Cove.

Integrates with sports APIs to fetch scores, odds, statistics, and schedules.
Primarily used for CFB 25 workspace.

Features:
- Live scores and game results
- Betting odds and lines
- Team and player statistics
- Schedule information
"""

from typing import Dict, Any, Optional
from datetime import datetime
import os
from .base import BaseTool, ToolResult, ToolError


class SportsDataTool(BaseTool):
    """Fetch sports data including scores, odds, and statistics."""

    def __init__(self):
        """Initialize sports data tool."""
        super().__init__()
        self.name = "sports_data"
        # API keys from environment
        self.odds_api_key = os.getenv("ODDS_API_KEY")
        self.espn_enabled = True  # ESPN API is free, no key needed

    async def execute(
        self,
        sport: str = "americanfootball_ncaaf",
        data_type: str = "scores",
        teams: Optional[str] = None,
        date: Optional[str] = None
    ) -> ToolResult:
        """
        Fetch sports data.

        Args:
            sport: Sport identifier (americanfootball_ncaaf, americanfootball_nfl, etc.)
            data_type: Type of data ("scores", "odds", "stats", "schedule")
            teams: Team name or abbreviation (optional)
            date: Date in YYYY-MM-DD format (optional, defaults to today)

        Returns:
            ToolResult with sports data
        """
        if not sport:
            raise ToolError("Sport parameter is required")

        # Validate data_type
        valid_types = ["scores", "odds", "stats", "schedule"]
        if data_type not in valid_types:
            raise ToolError(f"Invalid data_type. Must be one of: {', '.join(valid_types)}")

        try:
            if data_type == "odds" and self.odds_api_key:
                # Use The Odds API for betting lines
                result = await self._fetch_odds(sport, teams)
            elif data_type in ["scores", "schedule", "stats"]:
                # Use ESPN API for scores/schedules/stats
                result = await self._fetch_espn_data(sport, data_type, teams, date)
            else:
                # Fallback to mock data if no API keys
                result = await self._fetch_mock_data(sport, data_type, teams, date)

            return ToolResult(
                success=True,
                data=result,
                metadata={
                    "sport": sport,
                    "data_type": data_type,
                    "source": result.get("source", "mock")
                }
            )

        except Exception as e:
            raise ToolError(f"Sports data fetch failed: {str(e)}")

    async def _fetch_odds(self, sport: str, teams: Optional[str] = None) -> Dict[str, Any]:
        """Fetch betting odds from The Odds API."""
        import httpx

        # Map sport identifiers
        sport_key = self._map_sport_to_odds_api(sport)

        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
        params = {
            "apiKey": self.odds_api_key,
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Filter by teams if specified
            if teams:
                teams_lower = teams.lower()
                data = [
                    game for game in data
                    if teams_lower in game.get("home_team", "").lower()
                    or teams_lower in game.get("away_team", "").lower()
                ]

            return {
                "source": "theoddsapi",
                "games": data[:10],  # Limit to 10 games
                "count": len(data)
            }

    async def _fetch_espn_data(
        self,
        sport: str,
        data_type: str,
        teams: Optional[str] = None,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch data from ESPN API."""
        import httpx

        # Map sport to ESPN league
        league = self._map_sport_to_espn(sport)

        if data_type == "scores":
            # Fetch scoreboard
            url = f"https://site.api.espn.com/apis/site/v2/sports/football/{league}/scoreboard"
            params = {}
            if date:
                # ESPN expects format like YYYYMMDD
                params["dates"] = date.replace("-", "")

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                events = data.get("events", [])

                # Filter by teams if specified
                if teams:
                    teams_lower = teams.lower()
                    events = [
                        event for event in events
                        if any(
                            teams_lower in comp.get("team", {}).get("displayName", "").lower()
                            for comp in event.get("competitions", [{}])[0].get("competitors", [])
                        )
                    ]

                # Format results
                formatted = []
                for event in events[:10]:  # Limit to 10 games
                    competition = event.get("competitions", [{}])[0]
                    competitors = competition.get("competitors", [])

                    game = {
                        "name": event.get("name", ""),
                        "date": event.get("date", ""),
                        "status": competition.get("status", {}).get("type", {}).get("description", ""),
                        "venue": competition.get("venue", {}).get("fullName", "")
                    }

                    # Add team info
                    for comp in competitors:
                        home_away = "home" if comp.get("homeAway") == "home" else "away"
                        game[f"{home_away}_team"] = comp.get("team", {}).get("displayName", "")
                        game[f"{home_away}_score"] = comp.get("score", "")

                    formatted.append(game)

                return {
                    "source": "espn",
                    "sport": league,
                    "games": formatted,
                    "count": len(formatted)
                }

        elif data_type == "schedule":
            # Similar to scores but upcoming games
            url = f"https://site.api.espn.com/apis/site/v2/sports/football/{league}/scoreboard"

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                # Filter for upcoming games only
                events = [
                    e for e in data.get("events", [])
                    if e.get("status", {}).get("type", {}).get("state", "") == "pre"
                ]

                formatted = []
                for event in events[:10]:
                    formatted.append({
                        "name": event.get("name", ""),
                        "date": event.get("date", ""),
                        "venue": event.get("competitions", [{}])[0].get("venue", {}).get("fullName", "")
                    })

                return {
                    "source": "espn",
                    "sport": league,
                    "upcoming_games": formatted,
                    "count": len(formatted)
                }

        else:  # stats
            return await self._fetch_mock_data(sport, data_type, teams, date)

    async def _fetch_mock_data(
        self,
        sport: str,
        data_type: str,
        teams: Optional[str] = None,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Return mock data when APIs are unavailable.

        This is useful for development and testing.
        """
        if data_type == "scores":
            return {
                "source": "mock",
                "games": [
                    {
                        "name": "Alabama vs Georgia",
                        "date": datetime.now().isoformat(),
                        "status": "Final",
                        "home_team": "Georgia",
                        "home_score": "24",
                        "away_team": "Alabama",
                        "away_score": "21",
                        "venue": "Sanford Stadium"
                    },
                    {
                        "name": "Ohio State vs Michigan",
                        "date": datetime.now().isoformat(),
                        "status": "Final",
                        "home_team": "Michigan",
                        "home_score": "30",
                        "away_team": "Ohio State",
                        "away_score": "27",
                        "venue": "Michigan Stadium"
                    }
                ],
                "count": 2,
                "note": "Mock data - configure API keys for live data"
            }

        elif data_type == "odds":
            return {
                "source": "mock",
                "games": [
                    {
                        "home_team": "Georgia",
                        "away_team": "Alabama",
                        "commence_time": datetime.now().isoformat(),
                        "bookmakers": [
                            {
                                "key": "draftkings",
                                "markets": [
                                    {
                                        "key": "spreads",
                                        "outcomes": [
                                            {"name": "Georgia", "price": -110, "point": -3.5},
                                            {"name": "Alabama", "price": -110, "point": 3.5}
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "count": 1,
                "note": "Mock data - configure ODDS_API_KEY for live odds"
            }

        elif data_type == "schedule":
            return {
                "source": "mock",
                "upcoming_games": [
                    {
                        "name": "Texas vs Oklahoma",
                        "date": datetime.now().isoformat(),
                        "venue": "Cotton Bowl"
                    }
                ],
                "count": 1,
                "note": "Mock data - API integration active for real schedules"
            }

        else:  # stats
            return {
                "source": "mock",
                "stats": {
                    "team": teams or "Team Name",
                    "wins": 10,
                    "losses": 2,
                    "points_per_game": 35.5,
                    "points_allowed": 18.2
                },
                "note": "Mock data - stats API integration coming soon"
            }

    def _map_sport_to_odds_api(self, sport: str) -> str:
        """Map internal sport IDs to The Odds API keys."""
        mapping = {
            "americanfootball_ncaaf": "americanfootball_ncaaf",
            "americanfootball_nfl": "americanfootball_nfl",
            "basketball_ncaab": "basketball_ncaab",
            "basketball_nba": "basketball_nba",
            "baseball_mlb": "baseball_mlb"
        }
        return mapping.get(sport, sport)

    def _map_sport_to_espn(self, sport: str) -> str:
        """Map internal sport IDs to ESPN league codes."""
        mapping = {
            "americanfootball_ncaaf": "college-football",
            "americanfootball_nfl": "nfl",
            "basketball_ncaab": "mens-college-basketball",
            "basketball_nba": "nba",
            "baseball_mlb": "mlb"
        }
        return mapping.get(sport, "college-football")

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get JSON schema for sports data parameters."""
        return {
            "type": "object",
            "properties": {
                "sport": {
                    "type": "string",
                    "description": "Sport identifier (americanfootball_ncaaf, americanfootball_nfl, basketball_nba, etc.)",
                    "default": "americanfootball_ncaaf",
                    "enum": [
                        "americanfootball_ncaaf",
                        "americanfootball_nfl",
                        "basketball_ncaab",
                        "basketball_nba",
                        "baseball_mlb"
                    ]
                },
                "data_type": {
                    "type": "string",
                    "description": "Type of data to fetch",
                    "default": "scores",
                    "enum": ["scores", "odds", "stats", "schedule"]
                },
                "teams": {
                    "type": "string",
                    "description": "Team name to filter results (optional)"
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (optional, defaults to today)"
                }
            },
            "required": ["sport"]
        }

    def get_description(self) -> str:
        """Get human-readable description."""
        return (
            "Fetches sports data including live scores, betting odds, team statistics, and schedules. "
            "Supports CFB, NFL, NBA, NCAA Basketball, and MLB. "
            "Use for: checking game scores, getting betting lines, viewing schedules, analyzing team performance."
        )
