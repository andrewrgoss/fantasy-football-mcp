"""Optional FantasyPros API client and response normalization.

FantasyPros is an explicitly opt-in supplemental source.  The client never makes
a request without ``FANTASYPROS_API_KEY`` and does not persist API responses.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Mapping, Optional

import aiohttp


DEFAULT_BASE_URL = "https://api.fantasypros.com/public/v2/json"


class FantasyProsConfigurationError(ValueError):
    """Raised when FantasyPros has been requested without an API key."""


class FantasyProsAPIError(RuntimeError):
    """Raised when FantasyPros returns an unsuccessful response."""


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and abs(parsed) != float("inf") else None


def _rows(payload: Any) -> List[Mapping[str, Any]]:
    """Extract player-like objects from common JSON envelope shapes."""

    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    for key in ("players", "data", "results", "rankings", "projections"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, Mapping)]
        if isinstance(value, Mapping):
            return [row for row in value.values() if isinstance(row, Mapping)]
    return [payload]


def _first(row: Mapping[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def normalize_player_signals(payload: Any) -> Dict[str, Dict[str, Any]]:
    """Normalize FantasyPros ranking/projection rows keyed by player name."""

    signals: Dict[str, Dict[str, Any]] = {}
    for row in _rows(payload):
        name = _first(row, ("player_name", "name", "full_name"))
        if not name:
            continue
        projection = _number(
            _first(
                row,
                (
                    "projected_points",
                    "fantasy_points",
                    "proj_points",
                    "fpts_ppr",
                    "fpts",
                    "points",
                ),
            )
        )
        signals[str(name).strip().casefold()] = {
            "name": str(name).strip(),
            "team": str(_first(row, ("player_team_id", "team", "team_abbr")) or "").strip(),
            "position": str(_first(row, ("position", "pos")) or "").strip().upper(),
            "projected_points": projection,
            "rank": _number(_first(row, ("rank_ecr", "rank", "ecr", "overall_rank"))),
            "adp": _number(_first(row, ("adp", "average_draft_position"))),
            "tier": _number(_first(row, ("tier", "tier_number"))),
        }
    return signals


class FantasyProsClient:
    """Small async client for the official FantasyPros public API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = (api_key or os.getenv("FANTASYPROS_API_KEY", "")).strip()
        self.base_url = (base_url or os.getenv("FANTASYPROS_API_BASE_URL", DEFAULT_BASE_URL)).rstrip(
            "/"
        )
        self.timeout_seconds = timeout_seconds

    def _require_key(self) -> str:
        if not self.api_key:
            raise FantasyProsConfigurationError(
                "FantasyPros is opt-in. Set FANTASYPROS_API_KEY before enabling it."
            )
        return self.api_key

    async def get_json(self, endpoint: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        api_key = self._require_key()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "fantasy-football-mcp/1.0",
            "x-api-key": api_key,
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            try:
                async with session.get(url, params=dict(params or {})) as response:
                    body = await response.text()
                    if response.status >= 400:
                        raise FantasyProsAPIError(
                            f"FantasyPros returned HTTP {response.status}: {body[:300]}"
                        )
                    try:
                        return await response.json(content_type=None)
                    except (TypeError, ValueError) as exc:
                        raise FantasyProsAPIError("FantasyPros returned invalid JSON") from exc
            except aiohttp.ClientError as exc:
                raise FantasyProsAPIError(f"FantasyPros request failed: {exc}") from exc

    async def get_projections(
        self,
        season: int,
        *,
        scoring: str = "PPR",
        position: Optional[str] = None,
    ) -> Any:
        params: Dict[str, Any] = {"scoring": scoring}
        if position and position.upper() != "ALL":
            params["position"] = position.upper()
        return await self.get_json(f"/nfl/{int(season)}/projections", params)

    async def get_consensus_rankings(
        self,
        season: int,
        *,
        scoring: str = "PPR",
        position: Optional[str] = None,
    ) -> Any:
        params: Dict[str, Any] = {"scoring": scoring}
        if position and position.upper() != "ALL":
            params["position"] = position.upper()
        return await self.get_json(f"/nfl/{int(season)}/consensus-rankings", params)


__all__ = [
    "DEFAULT_BASE_URL",
    "FantasyProsAPIError",
    "FantasyProsClient",
    "FantasyProsConfigurationError",
    "normalize_player_signals",
]
