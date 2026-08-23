"""League-agnostic, offline auction-draft preparation utilities.

The module deliberately has no Yahoo or Reddit dependency.  It turns a private
league profile and exported player data into deterministic projections, market
summaries, auction values, and keeper surplus calculations.  A caller can then
combine those results with live Yahoo or Reddit data once those integrations are
available.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = PROJECT_ROOT / "config" / "league_profile.local.json"
FLEX_POSITIONS = ("RB", "WR", "TE")
INACTIVE_STATUSES = frozenset({"IR", "OUT", "O"})
OFFENSIVE_SKILL_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})


class AuctionPrepError(ValueError):
    """Raised when a league profile or auction input cannot be validated."""


def _number(value: Any, default: float = 0.0) -> float:
    """Coerce a CSV/JSON value into a finite float."""

    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else default
    text = str(value).strip().replace(",", "")
    if not text:
        return default
    try:
        parsed = float(text.replace("$", ""))
    except ValueError:
        return default
    return parsed if math.isfinite(parsed) else default


def parse_currency(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Parse values such as ``$64 ``, ``1,250``, or a numeric value."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    text = str(value).strip().replace("$", "").replace(",", "")
    try:
        parsed = float(text)
    except ValueError:
        return default
    return parsed if math.isfinite(parsed) else default


def normalize_position(value: Any) -> str:
    """Normalize common Yahoo and fantasy-football position spellings."""

    text = (
        str(value or "")
        .strip()
        .upper()
        .replace("D/ST", "DEF")
        .replace("DST", "DEF")
        .replace(",", "/")
        .replace(" ", "")
    )
    return text or "UNKNOWN"


def _normalized_key(value: Any) -> str:
    """Return a stable player-name key across source naming conventions.

    Yahoo and third-party exports commonly add suffixes such as ``III`` or
    ``Sr.`` and Yahoo occasionally appends ``DNR`` to a player name.  Those
    markers are not identity-bearing for source joins and otherwise create
    duplicate players with broken market/history matches.
    """

    text = str(value or "").upper().strip()
    text = re.sub(r"DNR$", "", text)
    tokens = re.findall(r"[A-Z0-9]+", text)
    while tokens and tokens[-1] in {"JR", "SR", "II", "III", "IV", "V", "VI"}:
        tokens.pop()
    key = "".join(tokens)
    # Known source-specific nickname/full-name collision in current football
    # exports.  Keep this table small and explicit rather than guessing at
    # arbitrary first-name abbreviations.
    return {
        "KENWALKER": "KENNETHWALKER",
        "KENNYGAINWELL": "KENNETHGAINWELL",
        "CHIGOKONKWO": "CHIGOZIEMOKONKWO",
    }.get(key, key)


def _row_value(row: Mapping[str, Any], *names: str) -> Any:
    normalized = {_normalized_key(key): value for key, value in row.items()}
    for name in names:
        if _normalized_key(name) in normalized:
            return normalized[_normalized_key(name)]
    return None


_TEAM_ALIASES = {
    "JAC": "JAX",
    "LA": "LAR",
    "STL": "LAR",
    "SD": "LAC",
    "OAK": "LV",
    "WAS": "WAS",
}


def normalize_team_code(value: Any) -> str:
    """Normalize common NFL team-code variants for context joins."""

    code = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    return _TEAM_ALIASES.get(code, code)


def load_team_environment_json(path: str) -> Dict[str, Dict[str, float]]:
    """Load optional team context from a local JSON export.

    The file is intentionally caller-supplied so the public repository does
    not embed a stale betting line or private league-specific input.  The
    accepted shape is either ``{"teams": {"PHI": {...}}}`` or a bare team
    mapping.  Each team may provide ``offensive_line_rank`` (1 is best) and
    ``vegas_win_total``.
    """

    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise AuctionPrepError("Team environment JSON must be an object")
    raw_teams = payload.get("teams", payload)
    if not isinstance(raw_teams, Mapping):
        raise AuctionPrepError("Team environment JSON must contain a 'teams' object")
    teams: Dict[str, Dict[str, float]] = {}
    for raw_team, raw_context in raw_teams.items():
        if not isinstance(raw_context, Mapping):
            continue
        team = normalize_team_code(raw_team)
        if not team:
            continue
        context: Dict[str, float] = {}
        oline_rank = parse_currency(
            raw_context.get("offensive_line_rank", raw_context.get("oline_rank"))
        )
        win_total = parse_currency(
            raw_context.get("vegas_win_total", raw_context.get("win_total"))
        )
        if oline_rank is not None and 1.0 <= oline_rank <= 32.0:
            context["offensive_line_rank"] = oline_rank
        if win_total is not None and 0.0 <= win_total <= 20.0:
            context["vegas_win_total"] = win_total
        if context:
            teams[team] = context
    return teams


def _team_environment_record(
    team_environment: Optional[Mapping[str, Mapping[str, Any]]],
    team: str,
) -> Mapping[str, Any]:
    if not team_environment:
        return {}
    return team_environment.get(normalize_team_code(team), {})


@dataclass(frozen=True)
class RosterRequirements:
    """Starting, bench, and injured-reserve requirements for one league."""

    starters: Dict[str, int]
    bench: int = 0
    injured_reserve: int = 0

    @property
    def starting_slots(self) -> int:
        return sum(self.starters.values())

    @property
    def draft_slots(self) -> int:
        """Roster spots normally filled in the auction (IR is not included)."""

        return self.starting_slots + self.bench

    def demand_by_position(self, teams: int) -> Dict[str, int]:
        """Return fixed positional demand before flex slots are allocated."""

        return {position: count * teams for position, count in self.starters.items()}


@dataclass(frozen=True)
class LeagueProfile:
    """Validated league inputs used by offline auction calculations."""

    season: int
    platform: str
    league_id: str
    league_name: Optional[str]
    teams: int
    auction_budget: float
    scoring_type: str
    roster: RosterRequirements
    scoring: Dict[str, Any] = field(default_factory=dict)
    management: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LeagueProfile":
        if not isinstance(payload, Mapping):
            raise AuctionPrepError("League profile must be a JSON object")

        league = payload.get("league", {})
        roster_payload = payload.get("roster", {})
        if not isinstance(league, Mapping) or not isinstance(roster_payload, Mapping):
            raise AuctionPrepError("League profile must contain 'league' and 'roster' objects")

        starters_raw = roster_payload.get("starters", {})
        if not isinstance(starters_raw, Mapping) or not starters_raw:
            raise AuctionPrepError("League profile must define at least one starting slot")
        starters: Dict[str, int] = {}
        for raw_position, raw_count in starters_raw.items():
            position = normalize_position(raw_position)
            count = int(_number(raw_count, -1))
            if count < 0:
                raise AuctionPrepError(f"Starter count for {position} cannot be negative")
            if count:
                starters[position] = count

        season = int(_number(payload.get("season"), 0))
        teams = int(_number(league.get("teams"), 0))
        budget = _number(league.get("auction_budget"), 0)
        if season <= 0:
            raise AuctionPrepError("League profile season must be positive")
        if teams < 2:
            raise AuctionPrepError("League profile must contain at least two teams")
        if budget <= 0:
            raise AuctionPrepError("League auction budget must be positive")

        bench = int(_number(roster_payload.get("bench"), 0))
        injured_reserve = int(_number(roster_payload.get("injured_reserve"), 0))
        if bench < 0 or injured_reserve < 0:
            raise AuctionPrepError("Bench and injured-reserve counts cannot be negative")
        scoring_raw = payload.get("scoring", {})
        management_raw = payload.get("league_management", {})
        if not isinstance(scoring_raw, Mapping) or not isinstance(management_raw, Mapping):
            raise AuctionPrepError("Scoring and league-management settings must be objects")

        return cls(
            season=season,
            platform=str(payload.get("platform", "")).strip() or "Unknown",
            league_id=str(league.get("id", "")).strip(),
            league_name=(str(league["name"]).strip() if league.get("name") else None),
            teams=teams,
            auction_budget=budget,
            scoring_type=str(league.get("scoring_type", "")).strip() or "Unknown",
            roster=RosterRequirements(
                starters=starters,
                bench=bench,
                injured_reserve=injured_reserve,
            ),
            scoring=dict(scoring_raw),
            management=dict(management_raw),
        )

    def summary(self, include_identity: bool = False) -> Dict[str, Any]:
        """Return a safe, serializable profile summary.

        Identity fields are omitted by default so callers can safely use the
        summary in logs or shared analysis contexts.
        """

        summary: Dict[str, Any] = {
            "season": self.season,
            "platform": self.platform,
            "teams": self.teams,
            "auction_budget": self.auction_budget,
            "scoring_type": self.scoring_type,
            "starters": dict(self.roster.starters),
            "bench": self.roster.bench,
            "injured_reserve": self.roster.injured_reserve,
            "starting_slots": self.roster.starting_slots,
            "draft_slots": self.roster.draft_slots,
            "reception_points": _scoring_value(self.scoring, "reception", 0.0),
        }
        if include_identity:
            summary["league_id"] = self.league_id
            summary["league_name"] = self.league_name
        return summary


def load_league_profile(path: Optional[str] = None) -> LeagueProfile:
    """Load and validate a local profile without exposing its contents in logs.

    The path can be supplied explicitly or through ``FANTASY_LEAGUE_PROFILE``.
    Otherwise the conventional ignored file ``config/league_profile.local.json``
    is used.
    """

    configured_path = path or os.getenv("FANTASY_LEAGUE_PROFILE")
    profile_path = Path(configured_path) if configured_path else DEFAULT_PROFILE_PATH
    if not profile_path.is_absolute():
        profile_path = PROJECT_ROOT / profile_path
    if not profile_path.exists():
        display_path = (
            str(profile_path.relative_to(PROJECT_ROOT))
            if profile_path.is_relative_to(PROJECT_ROOT)
            else str(profile_path)
        )
        raise FileNotFoundError(
            "No local league profile found. Copy .env.example or create "
            f"{display_path} before using auction tools."
        )
    try:
        with profile_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise AuctionPrepError(f"League profile is not valid JSON: {exc}") from exc
    return LeagueProfile.from_dict(payload)


@dataclass(frozen=True)
class PlayerProjection:
    """A normalized player projection suitable for auction calculations."""

    name: str
    position: str
    team: str
    projected_points: float
    stats: Dict[str, float] = field(default_factory=dict)
    source: str = "unknown"
    fantasypros_points: Optional[float] = None
    fantasypros_rank: Optional[float] = None
    fantasypros_adp: Optional[float] = None
    ffa_points: Optional[float] = None
    ffa_adp: Optional[float] = None
    ffa_rank: Optional[float] = None
    ffa_auction: Optional[float] = None
    ffa_custom_projection: Optional[float] = None
    ffa_popularity: Optional[float] = None
    ffa_sos: Optional[float] = None
    status: str = ""


@dataclass(frozen=True)
class AuctionMarketRecord:
    """A normalized current or historical market-price row."""

    name: str
    position: str
    team: str
    league_value: Optional[float] = None
    projected_value: Optional[float] = None
    average_cost: Optional[float] = None
    previous_owner: Optional[str] = None


@dataclass(frozen=True)
class HistoricalAuctionRecord:
    """A single player purchase from an auction draft export."""

    season: int
    name: str
    position: str
    team: str
    salary: float
    owner: Optional[str] = None


@dataclass(frozen=True)
class SentimentSignal:
    """A bounded sentiment input supplied by an approved external integration."""

    score: float = 0.0
    confidence: float = 0.0
    engagement: float = 0.0

    def bounded(self) -> "SentimentSignal":
        return SentimentSignal(
            score=max(-1.0, min(1.0, self.score)),
            confidence=max(0.0, min(1.0, self.confidence)),
            engagement=max(0.0, self.engagement),
        )


@dataclass(frozen=True)
class AuctionValue:
    """Projected price and context for one player."""

    name: str
    position: str
    team: str
    projected_points: float
    replacement_points: float
    vorp: float
    baseline_value: float
    market_value: Optional[float]
    historical_value: Optional[float]
    fantasypros_points: Optional[float]
    fantasypros_rank: Optional[float]
    fantasypros_adp: Optional[float]
    sentiment_score: Optional[float]
    sentiment_adjustment: Optional[float]
    suggested_value: float
    confidence: str
    # ``historical_value`` is intentionally position-slot based.  It is the
    # historical average salary for this player's current projected position
    # rank (for example, RB13), not the salary previously paid for this name.
    historical_position_rank: Optional[int] = None
    historical_position_spend_share: Optional[float] = None
    ffa_points: Optional[float] = None
    ffa_adp: Optional[float] = None
    ffa_rank: Optional[float] = None
    ffa_auction: Optional[float] = None
    ffa_custom_projection: Optional[float] = None
    ffa_popularity: Optional[float] = None
    ffa_sos: Optional[float] = None
    sos_adjustment: Optional[float] = None
    offensive_line_rank: Optional[float] = None
    vegas_win_total: Optional[float] = None
    offensive_line_adjustment: Optional[float] = None
    team_environment_adjustment: Optional[float] = None
    status: str = ""
    sentiment_confidence: Optional[float] = None
    sentiment_engagement: Optional[float] = None
    sentiment_coverage: str = "unavailable"

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            "name": self.name,
            "position": self.position,
            "team": self.team,
            "projected_points": round(self.projected_points, 2),
            "replacement_points": round(self.replacement_points, 2),
            "vorp": round(self.vorp, 2),
            "baseline_value": round(self.baseline_value, 2),
            "market_value": round(self.market_value, 2) if self.market_value is not None else None,
            "historical_value": (
                round(self.historical_value, 2) if self.historical_value is not None else None
            ),
            "historical_position_rank": self.historical_position_rank,
            "historical_position_spend_share": (
                round(self.historical_position_spend_share, 4)
                if self.historical_position_spend_share is not None
                else None
            ),
            "fantasypros_points": (
                round(self.fantasypros_points, 2) if self.fantasypros_points is not None else None
            ),
            "fantasypros_rank": (
                round(self.fantasypros_rank, 2) if self.fantasypros_rank is not None else None
            ),
            "fantasypros_adp": (
                round(self.fantasypros_adp, 2) if self.fantasypros_adp is not None else None
            ),
            "ffa_points": round(self.ffa_points, 2) if self.ffa_points is not None else None,
            "ffa_adp": round(self.ffa_adp, 2) if self.ffa_adp is not None else None,
            "ffa_rank": round(self.ffa_rank, 2) if self.ffa_rank is not None else None,
            "ffa_auction": (
                round(self.ffa_auction, 2) if self.ffa_auction is not None else None
            ),
            "ffa_custom_projection": (
                round(self.ffa_custom_projection, 2)
                if self.ffa_custom_projection is not None
                else None
            ),
            "status": self.status,
            "suggested_value": round(self.suggested_value, 2),
            "data_confidence": self.confidence,
        }
        if self.ffa_popularity is not None:
            payload["ffa_popularity"] = round(self.ffa_popularity, 3)
        if self.ffa_sos is not None:
            payload["ffa_sos"] = round(self.ffa_sos, 2)
        if self.sos_adjustment is not None:
            payload["sos_adjustment"] = round(self.sos_adjustment, 2)
        if self.offensive_line_rank is not None:
            payload["offensive_line_rank"] = round(self.offensive_line_rank, 2)
        if self.vegas_win_total is not None:
            payload["vegas_win_total"] = round(self.vegas_win_total, 2)
        if self.offensive_line_adjustment is not None:
            payload["offensive_line_adjustment"] = round(
                self.offensive_line_adjustment, 2
            )
        if self.team_environment_adjustment is not None:
            payload["team_environment_adjustment"] = round(
                self.team_environment_adjustment, 2
            )
        # Do not emit empty Reddit placeholders in normal offline output. If
        # an approved sentiment integration supplies a signal, preserve the
        # richer metadata for callers that explicitly requested it.
        if self.sentiment_coverage != "unavailable":
            payload.update(
                {
                    "sentiment_score": (
                        round(self.sentiment_score, 3)
                        if self.sentiment_score is not None
                        else None
                    ),
                    "sentiment_adjustment": (
                        round(self.sentiment_adjustment, 2)
                        if self.sentiment_adjustment is not None
                        else None
                    ),
                    "sentiment_confidence": (
                        round(self.sentiment_confidence, 3)
                        if self.sentiment_confidence is not None
                        else None
                    ),
                    "sentiment_engagement": (
                        round(self.sentiment_engagement, 2)
                        if self.sentiment_engagement is not None
                        else None
                    ),
                    "sentiment_coverage": self.sentiment_coverage,
                }
            )
        return payload


def _scoring_value(scoring: Mapping[str, Any], key: str, default: float) -> float:
    offense = scoring.get("offense", {})
    if isinstance(offense, Mapping):
        return _number(offense.get(key), default)
    return default


def calculate_projected_points(stats: Mapping[str, Any], profile: LeagueProfile) -> float:
    """Calculate offensive fantasy points from projected raw statistics."""

    offense = profile.scoring.get("offense", {})
    if not isinstance(offense, Mapping):
        offense = {}

    def stat(*names: str) -> float:
        for name in names:
            if name in stats:
                return _number(stats[name])
        return 0.0

    def rule(name: str, default: float = 0.0) -> float:
        return _number(offense.get(name), default)

    points = 0.0
    passing_rate = rule("passing_yards_per_point")
    rushing_rate = rule("rushing_yards_per_point")
    receiving_rate = rule("receiving_yards_per_point")
    if passing_rate > 0:
        points += stat("passing_yards", "PASSING_YDS") / passing_rate
    points += stat("passing_touchdowns", "PASSING_TD") * rule("passing_touchdown")
    points += stat("interceptions", "INTERCEPTIONS", "PASSING_INT") * rule("interception")
    if rushing_rate > 0:
        points += stat("rushing_yards", "RUSHING_YDS") / rushing_rate
    points += stat("rushing_touchdowns", "RUSHING_TD") * rule("rushing_touchdown")
    points += stat("receptions", "RECEPTIONS") * rule("reception")
    if receiving_rate > 0:
        points += stat("receiving_yards", "RECEIVING_YDS") / receiving_rate
    points += stat("receiving_touchdowns", "RECEIVING_TD") * rule("receiving_touchdown")
    points += stat("return_touchdowns", "RET_TD") * rule("return_touchdown")
    points += stat("two_point_conversions", "2PT_CONVERSIONS") * rule("two_point_conversion")
    points += stat("fumbles_lost", "FUMBLES_LOST") * rule("fumble_lost")
    return round(points, 4)


def load_player_projections_csv(path: str, profile: LeagueProfile) -> List[PlayerProjection]:
    """Load the scraper's player-projection CSV format.

    When raw stat columns are present, points are recalculated using the supplied
    profile.  Otherwise the source ``FANTASY_POINTS`` column is used.
    """

    projections: List[PlayerProjection] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        field_positions = {
            _normalized_key(name): index
            for index, name in enumerate(reader.fieldnames or [])
        }
        # Early versions of the Yahoo scraper wrote the row values in Yahoo's
        # order (TARGETS, RECEPTIONS, RECEIVING_YDS, RECEIVING_TD) but emitted
        # a header with RECEPTIONS before TARGETS.  Detect that specific legacy
        # layout and map the values back to their real statistics.  New exports
        # use the matching header/order and follow the normal aliases below.
        legacy_receiving_layout = (
            "TARGETS" in field_positions
            and "RECEPTIONS" in field_positions
            and field_positions["RECEPTIONS"] < field_positions["TARGETS"]
        )
        for row in reader:
            name = str(_row_value(row, "PLAYER_NAME", "PLAYER", "NAME") or "").strip()
            if not name:
                continue
            position = normalize_position(_row_value(row, "POSITION", "POS"))
            status = str(_row_value(row, "PLAYER_STATUS", "STATUS") or "").strip().upper()
            games = _number(_row_value(row, "GP", "GAMES"))
            stats: Dict[str, float] = {}
            stat_columns = {
                "passing_yards": ("PASSING_YDS",),
                "passing_touchdowns": ("PASSING_TD",),
                "interceptions": ("PASSING_INT", "INTERCEPTIONS"),
                "rushing_yards": ("RUSHING_YDS",),
                "rushing_touchdowns": ("RUSHING_TD",),
                "receptions": ("RECEPTIONS",),
                "receiving_yards": ("RECEIVING_YDS",),
                "receiving_touchdowns": ("RECEIVING_TD",),
                "return_touchdowns": ("RET_TD",),
                "two_point_conversions": ("2PT_CONVERSIONS",),
                "fumbles_lost": ("FUMBLES_LOST",),
            }
            if legacy_receiving_layout:
                stat_columns.update(
                    {
                        "receptions": ("RECEIVING_YDS",),
                        "receiving_yards": ("RECEIVING_TD",),
                        "receiving_touchdowns": ("TARGETS",),
                    }
                )
            for canonical, columns in stat_columns.items():
                raw = _row_value(row, *columns)
                if raw not in (None, ""):
                    stats[canonical] = _number(raw)
            recalculated = calculate_projected_points(stats, profile) if stats else 0.0
            source_points = _number(_row_value(row, "FANTASY_POINTS", "PROJECTED_FANTASY_POINTS"))
            points = recalculated if stats else source_points
            if status in INACTIVE_STATUSES and games <= 0:
                points = 0.0
                stats = {}
            projections.append(
                PlayerProjection(
                    name=name,
                    position=position,
                    team=str(_row_value(row, "TEAM") or "").strip(),
                    projected_points=points,
                    stats=stats,
                    source=str(path),
                    status=status,
                )
            )
    return projections


def load_ffa_projections_csv(path: str, profile: LeagueProfile) -> List[PlayerProjection]:
    """Load Fantasy Football Advice's detailed projection export.

    FFA uses human-readable column names and supplies separate ADP columns for
    PPR, half-PPR, and standard formats.  Raw statistics are recalculated with
    the caller's private league profile so the source remains scoring-aware.
    """

    projections: List[PlayerProjection] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = str(_row_value(row, "PLAYER", "PLAYER_NAME", "NAME") or "").strip()
            if not name:
                continue
            position = normalize_position(_row_value(row, "POS", "POSITION"))
            stats: Dict[str, float] = {}
            stat_columns = {
                "passing_yards": ("PASS YDS", "PASS_YDS", "PASSING YDS", "PASSING_YDS"),
                "passing_touchdowns": ("PASS TDs", "PASS TDS", "PASS_TD", "PASSING TD"),
                "interceptions": ("INTs", "INT", "INTERCEPTIONS"),
                "rushing_yards": ("RUSH YDS", "RUSH_YDS", "RUSHING YDS"),
                "rushing_touchdowns": ("RUSH TDs", "RUSH TDS", "RUSH_TD", "RUSHING TD"),
                "receptions": ("RECEPTIONS", "REC"),
                "receiving_yards": ("REC YDS", "REC_YDS", "RECEIVING YDS"),
                "receiving_touchdowns": ("REC TDs", "REC TDS", "REC_TD", "RECEIVING TD"),
            }
            for canonical, columns in stat_columns.items():
                raw = _row_value(row, *columns)
                if raw not in (None, "", "—", "-"):
                    stats[canonical] = _number(raw)
            recalculated = calculate_projected_points(stats, profile) if stats else 0.0
            source_points = _number(_row_value(row, "PPR POINTS", "FANTASY POINTS"))
            points = recalculated if stats else source_points
            ffa_adp = parse_currency(_row_value(row, "PPR ADP"))
            projections.append(
                PlayerProjection(
                    name=name,
                    position=position,
                    team=str(_row_value(row, "TEAM") or "").strip(),
                    projected_points=points,
                    stats=stats,
                    source=str(path),
                    ffa_points=points,
                    ffa_adp=ffa_adp,
                )
            )
    return projections


def load_ffa_custom_rankings_csv(path: str) -> List[PlayerProjection]:
    """Load an FFA custom-ranking export as a projection/rank signal."""

    rankings: List[PlayerProjection] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = str(_row_value(row, "PLAYER", "PLAYER_NAME", "NAME") or "").strip()
            if not name:
                continue
            points_raw = _row_value(row, "PROJ", "PROJECTED_POINTS", "FANTASY_POINTS")
            points = parse_currency(points_raw, default=None)
            if points is None:
                continue
            rankings.append(
                PlayerProjection(
                    name=name,
                    position=normalize_position(_row_value(row, "POS", "POSITION")),
                    team=str(_row_value(row, "TEAM") or "").strip(),
                    projected_points=points,
                    source=str(path),
                    ffa_custom_projection=points,
                    ffa_rank=parse_currency(_row_value(row, "RANK")),
                    ffa_adp=parse_currency(_row_value(row, "ADP")),
                    ffa_auction=parse_currency(_row_value(row, "AUCTION")),
                    ffa_popularity=parse_currency(_row_value(row, "POPULARITY", "POP")),
                    ffa_sos=parse_currency(_row_value(row, "SOS", "STRENGTH OF SCHEDULE")),
                )
            )
    return rankings


def merge_ffa_rankings(
    projections: Sequence[PlayerProjection],
    rankings: Sequence[PlayerProjection],
    *,
    custom_weight: float = 0.50,
) -> List[PlayerProjection]:
    """Combine detailed FFA projections with custom FFA ranking projections."""

    custom_weight = max(0.0, min(1.0, float(custom_weight)))
    ranking_by_key = {_normalized_key(player.name): player for player in rankings}
    merged: List[PlayerProjection] = []
    for projection in projections:
        ranking = ranking_by_key.get(_normalized_key(projection.name))
        if ranking is None:
            merged.append(projection)
            continue
        points = (
            projection.projected_points * (1.0 - custom_weight)
            + ranking.projected_points * custom_weight
        )
        merged.append(
            PlayerProjection(
                name=projection.name,
                position=projection.position,
                team=projection.team or ranking.team,
                projected_points=round(points, 4),
                stats=projection.stats,
                source=f"{projection.source}+ffa_custom_rankings",
                ffa_points=round(points, 4),
                ffa_adp=ranking.ffa_adp,
                ffa_rank=ranking.ffa_rank,
                ffa_auction=ranking.ffa_auction,
                ffa_custom_projection=ranking.projected_points,
                ffa_popularity=ranking.ffa_popularity,
                ffa_sos=ranking.ffa_sos,
            )
        )

    existing = {_normalized_key(player.name) for player in projections}
    for ranking in rankings:
        key = _normalized_key(ranking.name)
        if key in existing or ranking.position not in {"QB", "RB", "WR", "TE"}:
            continue
        merged.append(
            PlayerProjection(
                name=ranking.name,
                position=ranking.position,
                team=ranking.team,
                projected_points=ranking.projected_points,
                source=f"{ranking.source}+ffa_custom_rankings",
                ffa_points=ranking.projected_points,
                ffa_adp=ranking.ffa_adp,
                ffa_rank=ranking.ffa_rank,
                ffa_auction=ranking.ffa_auction,
                ffa_custom_projection=ranking.projected_points,
                ffa_popularity=ranking.ffa_popularity,
                ffa_sos=ranking.ffa_sos,
            )
        )
    return merged


def _fantasypros_position(value: Any, default: str = "") -> str:
    """Extract a FantasyPros position from values such as ``WR12`` or ``QB1``."""

    match = re.match(r"^\s*([A-Z]+)", str(value or "").upper())
    return match.group(1) if match else default


def _fantasypros_csv_value(row: Sequence[str], index: Optional[int]) -> Any:
    if index is None or index >= len(row):
        return None
    value = row[index].strip()
    return None if value in {"", "-", "—", "\xa0"} else value


def load_fantasypros_csv_signals(
    projection_paths: Sequence[str],
    *,
    rankings_path: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Load full FantasyPros CSV exports without using the limited API.

    FantasyPros' downloadable projection files use duplicate column labels
    (for example, two ``YDS`` and ``TDS`` columns).  This loader therefore
    reads rows positionally instead of using ``csv.DictReader``, preserving
    the rushing and receiving columns separately.  The FLX export supplies
    RB/WR/TE PPR totals; the QB export supplies quarterback totals.  A draft
    rankings export contributes overall rank and tier.  ADP is intentionally
    left unset unless a separate ADP export is supplied in a future extension.
    """

    signals: Dict[str, Dict[str, Any]] = {}
    for path in projection_paths:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            normalized_header = [_normalized_key(value) for value in header]
            fpts_index = next(
                (index for index, value in enumerate(normalized_header) if value == "FPTS"),
                None,
            )
            pos_index = next(
                (index for index, value in enumerate(normalized_header) if value == "POS"),
                None,
            )
            is_qb_export = pos_index is None or "CMP" in normalized_header
            for row in reader:
                name = str(_fantasypros_csv_value(row, 0) or "").strip()
                if not name:
                    continue
                team = str(_fantasypros_csv_value(row, 1) or "").strip()
                position = (
                    _fantasypros_position(_fantasypros_csv_value(row, pos_index))
                    if not is_qb_export
                    else "QB"
                )
                if position not in {"QB", "RB", "WR", "TE"}:
                    continue
                projected_points = parse_currency(_fantasypros_csv_value(row, fpts_index))
                if projected_points is None or projected_points <= 0:
                    continue
                key = _normalized_key(name)
                target = signals.setdefault(
                    key,
                    {
                        "name": name,
                        "team": team,
                        "position": position,
                    },
                )
                target.update(
                    {
                        "name": target.get("name") or name,
                        "team": target.get("team") or team,
                        "position": target.get("position") or position,
                        "projected_points": projected_points,
                    }
                )

    if rankings_path:
        with Path(rankings_path).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                name = str(_row_value(row, "PLAYER NAME", "PLAYER", "NAME") or "").strip()
                position = _fantasypros_position(_row_value(row, "POS"))
                if not name or position not in {"QB", "RB", "WR", "TE"}:
                    continue
                key = _normalized_key(name)
                target = signals.setdefault(
                    key,
                    {"name": name, "team": str(_row_value(row, "TEAM") or "").strip(), "position": position},
                )
                target["rank"] = parse_currency(_row_value(row, "RK", "RANK"))
                target["tier"] = parse_currency(_row_value(row, "TIERS", "TIER"))
                target["team"] = target.get("team") or str(_row_value(row, "TEAM") or "").strip()
                target["position"] = target.get("position") or position

    return signals


def blend_projection_sources(
    yahoo_players: Sequence[PlayerProjection],
    *,
    ffa_players: Optional[Sequence[PlayerProjection]] = None,
    fantasypros_signals: Optional[Mapping[str, Mapping[str, Any]]] = None,
    ffa_weight: float = 0.40,
    yahoo_weight: float = 0.30,
    fantasypros_weight: float = 0.30,
) -> List[PlayerProjection]:
    """Blend FFA, Yahoo, and FantasyPros projections with per-player fallback.

    Missing source rows are omitted and the remaining source weights are
    renormalized for that player.  This matters for the FantasyPros free tier,
    which may return only a limited ranked subset.
    """

    weights = {
        "ffa": max(0.0, min(1.0, float(ffa_weight))),
        "yahoo": max(0.0, min(1.0, float(yahoo_weight))),
        "fantasypros": max(0.0, min(1.0, float(fantasypros_weight))),
    }
    if not any(weights.values()):
        raise AuctionPrepError("At least one projection-source weight must be positive")

    yahoo_by_key = {_normalized_key(player.name): player for player in yahoo_players}
    ffa_by_key = {
        _normalized_key(player.name): player for player in (ffa_players or [])
    }
    fantasypros_by_key: Dict[str, Mapping[str, Any]] = {}
    for raw_name, signal in (fantasypros_signals or {}).items():
        if not isinstance(signal, Mapping):
            continue
        signal_name = signal.get("name") if isinstance(signal, Mapping) else None
        fantasypros_by_key[_normalized_key(signal_name or raw_name)] = signal

    ordered_keys = list(yahoo_by_key)
    ordered_keys.extend(key for key in ffa_by_key if key not in yahoo_by_key)
    blended: List[PlayerProjection] = []
    for key in ordered_keys:
        yahoo = yahoo_by_key.get(key)
        ffa = ffa_by_key.get(key)
        fantasypros = fantasypros_by_key.get(key)
        if yahoo is not None and yahoo.status in INACTIVE_STATUSES and yahoo.projected_points <= 0:
            continue
        available: List[Tuple[float, float, str]] = []
        if yahoo is not None and weights["yahoo"] > 0 and yahoo.projected_points > 0:
            available.append((weights["yahoo"], yahoo.projected_points, "yahoo"))
        fantasypros_points = (
            _number(fantasypros.get("projected_points"))
            if fantasypros and fantasypros.get("projected_points") is not None
            else None
        )
        ffa_usable = (
            ffa is not None
            and weights["ffa"] > 0
            and ffa.projected_points > 0
        )
        # A zero FFA auction signal rejects the FFA projection for a player
        # without a current Yahoo row.  FantasyPros may still contribute its
        # independent signal, but the stale-fringe guard below prevents that
        # low-ranked signal plus old history from creating draft dollars.
        ffa_only_without_draft_signal = (
            ffa is not None
            and yahoo is None
            and ffa.ffa_auction is not None
            and ffa.ffa_auction <= 0
        )
        ffa_contributes = ffa_usable and not ffa_only_without_draft_signal
        if ffa_contributes:
            available.append((weights["ffa"], ffa.projected_points, "ffa"))
        if fantasypros_points is not None and fantasypros_points > 0 and weights["fantasypros"] > 0:
            available.append((weights["fantasypros"], fantasypros_points, "fantasypros"))
        if not available:
            continue
        total_weight = sum(weight for weight, _, _ in available)
        points = sum(weight * value for weight, value, _ in available) / total_weight
        base = yahoo or ffa
        assert base is not None
        source = "+".join(source for _, _, source in available)
        fantasypros_team = str(fantasypros.get("team") or "").strip() if fantasypros else ""
        blended.append(
            PlayerProjection(
                name=base.name,
                position=base.position,
                team=(
                    yahoo.team
                    if yahoo and yahoo.team
                    else fantasypros_team or (ffa.team if ffa else "")
                ),
                projected_points=round(points, 4),
                stats=yahoo.stats if yahoo else (ffa.stats if ffa else {}),
                source=source,
                fantasypros_points=fantasypros_points,
                fantasypros_rank=(
                    _number(fantasypros.get("rank"))
                    if fantasypros and fantasypros.get("rank") is not None
                    else None
                ),
                fantasypros_adp=(
                    _number(fantasypros.get("adp"))
                    if fantasypros and fantasypros.get("adp") is not None
                    else None
                ),
                ffa_points=(ffa.projected_points if ffa_contributes else None),
                ffa_adp=ffa.ffa_adp if ffa else None,
                ffa_rank=ffa.ffa_rank if ffa else None,
                ffa_auction=ffa.ffa_auction if ffa else None,
                ffa_custom_projection=ffa.ffa_custom_projection if ffa else None,
                ffa_popularity=ffa.ffa_popularity if ffa else None,
                ffa_sos=ffa.ffa_sos if ffa else None,
                status=yahoo.status if yahoo else (ffa.status if ffa else ""),
            )
        )
    return blended


def apply_fantasypros_projections(
    players: Sequence[PlayerProjection],
    signals: Mapping[str, Mapping[str, Any]],
    *,
    weight: float = 0.30,
) -> List[PlayerProjection]:
    """Blend normalized FantasyPros projections into local player projections."""

    weight = max(0.0, min(1.0, weight))
    return blend_projection_sources(
        players,
        fantasypros_signals=signals,
        yahoo_weight=1.0 - weight,
        fantasypros_weight=weight,
        ffa_weight=0.0,
    )


def load_market_values_csv(path: str) -> Dict[str, AuctionMarketRecord]:
    """Load the scraper's pre-draft auction-value CSV keyed by player name."""

    records: Dict[str, AuctionMarketRecord] = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = str(_row_value(row, "PLAYER_NAME", "PLAYER", "NAME") or "").strip()
            if not name:
                continue
            record = AuctionMarketRecord(
                name=name,
                position=normalize_position(_row_value(row, "POSITION", "POS")),
                team=str(_row_value(row, "TEAM") or "").strip(),
                league_value=parse_currency(_row_value(row, "LEAGUE_VALUE")),
                projected_value=parse_currency(_row_value(row, "PROJ_VALUE", "PROJECTED_VALUE")),
                average_cost=parse_currency(_row_value(row, "AVG_COST", "AVERAGE_COST")),
                previous_owner=(
                    str(_row_value(row, "PREVIOUS_OWNER")).strip()
                    if _row_value(row, "PREVIOUS_OWNER")
                    else None
                ),
            )
            records[name.casefold()] = record
    return records


def load_historical_auction_csv(path: str) -> List[HistoricalAuctionRecord]:
    """Load historical auction results exported by the scraper."""

    records: List[HistoricalAuctionRecord] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = str(_row_value(row, "PLAYER", "PLAYER_NAME", "NAME") or "").strip()
            salary = parse_currency(_row_value(row, "SALARY", "COST"))
            if not name or salary is None:
                continue
            records.append(
                HistoricalAuctionRecord(
                    season=int(_number(_row_value(row, "YEAR", "SEASON"), 0)),
                    name=name,
                    position=normalize_position(_row_value(row, "POSITION", "POS")),
                    team=str(_row_value(row, "TEAM") or "").strip(),
                    salary=salary,
                    owner=(
                        str(_row_value(row, "OWNER")).strip()
                        if _row_value(row, "OWNER")
                        else None
                    ),
                )
            )
    return records


def load_historical_auction_files(paths: Iterable[str]) -> List[HistoricalAuctionRecord]:
    """Load and combine one or more historical auction CSV files."""

    records: List[HistoricalAuctionRecord] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            csv_paths = sorted(path.glob("*.csv"))
        else:
            csv_paths = [path]
        for csv_path in csv_paths:
            records.extend(load_historical_auction_csv(str(csv_path)))
    return records


def calculate_replacement_levels(
    players: Sequence[PlayerProjection], profile: LeagueProfile
) -> Dict[str, float]:
    """Estimate replacement points from fixed and flex roster demand.

    Fixed slots are filled first for every team.  The remaining W/R/T flex slots
    are then filled by the best eligible players across those positions.  The
    lowest selected player at each position becomes that position's replacement
    level.
    """

    by_position: Dict[str, List[PlayerProjection]] = defaultdict(list)
    for player in players:
        by_position[player.position].append(player)
    for position_players in by_position.values():
        position_players.sort(key=lambda item: item.projected_points, reverse=True)

    selected: Dict[str, List[PlayerProjection]] = defaultdict(list)
    selected_names: set[str] = set()
    demand = profile.roster.demand_by_position(profile.teams)
    for position, count in demand.items():
        # RB/WR/TE can have both fixed and W/R/T demand.  Only the flex slot
        # labels themselves are deferred to the cross-position allocation.
        if position in {"W/R/T", "FLEX"}:
            continue
        for player in by_position.get(position, [])[:count]:
            selected[position].append(player)
            selected_names.add(_normalized_key(player.name))

    flex_slots = profile.roster.starters.get("W/R/T", 0) + profile.roster.starters.get("FLEX", 0)
    remaining_flex = [
        player
        for position in FLEX_POSITIONS
        for player in by_position.get(position, [])
        if _normalized_key(player.name) not in selected_names
    ]
    remaining_flex.sort(key=lambda item: item.projected_points, reverse=True)
    for player in remaining_flex[: profile.teams * flex_slots]:
        selected[player.position].append(player)
        selected_names.add(_normalized_key(player.name))

    levels: Dict[str, float] = {}
    for position, position_players in selected.items():
        # Flex candidates are appended after fixed-slot candidates, so list
        # insertion order is not a positional ranking.  Using ``[-1]`` here
        # could select an RB11-level player as the RB replacement point when a
        # higher-scoring flex RB happened to be appended last.  Replacement is
        # the lowest-scoring selected player at that position, regardless of
        # how fixed and flex demand were allocated.
        levels[position] = (
            min(player.projected_points for player in position_players)
            if position_players
            else 0.0
        )
    for position in by_position:
        levels.setdefault(position, 0.0)
    return levels


def _coerce_sentiment(value: Any) -> SentimentSignal:
    if isinstance(value, SentimentSignal):
        return value.bounded()
    if isinstance(value, Mapping):
        return SentimentSignal(
            score=_number(value.get("score", value.get("sentiment_score"))),
            confidence=_number(value.get("confidence", value.get("sentiment_confidence"))),
            engagement=_number(value.get("engagement", value.get("engagement_score"))),
        ).bounded()
    return SentimentSignal(score=_number(value)).bounded()


def _sentiment_input(
    sentiment: Mapping[str, Any], player: PlayerProjection, key: str
) -> Any:
    """Find an explicitly supplied signal without treating absence as neutral."""

    for candidate in (key, player.name, player.name.casefold()):
        if candidate in sentiment and sentiment[candidate] not in (None, ""):
            return sentiment[candidate]
    return None


def project_auction_values(
    players: Sequence[PlayerProjection],
    profile: LeagueProfile,
    market_values: Optional[Mapping[str, AuctionMarketRecord]] = None,
    historical_records: Optional[Iterable[HistoricalAuctionRecord]] = None,
    sentiment: Optional[Mapping[str, Any]] = None,
    market_weight: float = 0.25,
    historical_weight: float = 0.15,
    team_environment: Optional[Mapping[str, Mapping[str, Any]]] = None,
    max_sos_adjustment: float = 0.025,
    max_offensive_line_adjustment: float = 0.025,
    max_team_environment_adjustment: float = 0.025,
    max_sentiment_adjustment: float = 0.08,
    max_price_fraction: float = 0.35,
) -> List[AuctionValue]:
    """Calculate league-specific auction values from projections and optional signals."""

    if not players:
        return []
    market_weight = max(0.0, min(1.0, market_weight))
    historical_weight = max(0.0, min(1.0, historical_weight))
    max_sos_adjustment = max(0.0, min(0.10, max_sos_adjustment))
    max_offensive_line_adjustment = max(
        0.0, min(0.10, max_offensive_line_adjustment)
    )
    max_team_environment_adjustment = max(
        0.0, min(0.10, max_team_environment_adjustment)
    )
    max_sentiment_adjustment = max(0.0, min(0.25, max_sentiment_adjustment))
    max_price_fraction = max(0.05, min(1.0, max_price_fraction))
    market_values = market_values or {}
    historical_rows = list(historical_records or [])
    historical_slots = historical_position_slot_values(historical_rows)
    historical_spend_shares = historical_position_spend_shares(historical_rows)
    eligible_players = [player for player in players if player.projected_points > 0]
    if not eligible_players:
        return []
    players = eligible_players
    market_by_key = {
        _normalized_key(name): record for name, record in market_values.items()
    }
    sentiment = sentiment or {}
    replacement = calculate_replacement_levels(players, profile)
    vorp_by_name = {
        _normalized_key(player.name): max(
            0.0, player.projected_points - replacement.get(player.position, 0.0)
        )
        for player in players
    }
    total_league_budget = profile.teams * profile.auction_budget
    draft_player_count = profile.teams * profile.roster.draft_slots
    market_candidates = [
        market.league_value or market.projected_value or market.average_cost
        for market in market_values.values()
        if market.league_value or market.projected_value or market.average_cost
    ]
    market_candidates.sort(reverse=True)
    market_total = sum(market_candidates[:draft_player_count])
    market_scale = total_league_budget / market_total if market_total else 1.0
    max_model_value = profile.auction_budget * max_price_fraction
    max_vorp = max(vorp_by_name.values(), default=0.0)
    position_rank_by_key: Dict[str, int] = {}
    players_by_position: Dict[str, List[PlayerProjection]] = defaultdict(list)
    for player in players:
        players_by_position[player.position].append(player)
    for position_players in players_by_position.values():
        ordered = sorted(position_players, key=lambda item: item.projected_points, reverse=True)
        for position_rank, player in enumerate(ordered, 1):
            position_rank_by_key[_normalized_key(player.name)] = position_rank
    historical_slots_by_position: Dict[str, Dict[int, float]] = defaultdict(dict)
    for (position, position_rank), value in historical_slots.items():
        historical_slots_by_position[position][position_rank] = value
    values: List[AuctionValue] = []

    for player in players:
        key = _normalized_key(player.name)
        market = market_by_key.get(key)
        market_value = None
        if market:
            market_value = market.league_value or market.projected_value or market.average_cost
        # A bounded rank curve is a safer fallback than assigning the entire
        # league budget proportionally to raw VORP.  Raw projections can make a
        # high-volume QB or a single elite WR appear worth most of the budget.
        relative_vorp = vorp_by_name[key] / max_vorp if max_vorp else 0.0
        baseline = 1.0 + ((max_model_value - 1.0) * (relative_vorp**0.75))
        blended = baseline
        if market_value is not None:
            calibrated_market = market_value * market_scale
            blended = (baseline * (1 - market_weight)) + (calibrated_market * market_weight)
        historical_position_rank = position_rank_by_key.get(key)
        position_slots = historical_slots_by_position.get(player.position, {})
        historical_value = None
        if position_slots and historical_position_rank is not None:
            # Use the nearest observed slot when the current projection pool
            # is deeper than a historical draft at this position.  In practice
            # this maps fringe players to the historical end-of-draft salary
            # rather than to an unrelated player's old price.
            nearest_rank = min(
                position_slots,
                key=lambda rank: abs(rank - historical_position_rank),
            )
            historical_value = position_slots[nearest_rank]
        if historical_value is not None:
            blended = (blended * (1 - historical_weight)) + (historical_value * historical_weight)
        sos_adjustment = None
        if player.ffa_sos is not None and 1.0 <= player.ffa_sos <= 32.0:
            # FFA SOS is a rank: 1 is easiest and 32 is hardest.  Center the
            # bounded effect at the median schedule and keep it deliberately
            # small so schedule strength breaks close calls without replacing
            # the projection, market, or historical-slot signals.
            sos_factor = (16.5 - player.ffa_sos) / 15.5
            sos_adjustment = blended * sos_factor * max_sos_adjustment
            blended += sos_adjustment
        environment = _team_environment_record(team_environment, player.team)
        offensive_line_rank = parse_currency(environment.get("offensive_line_rank"))
        vegas_win_total = parse_currency(environment.get("vegas_win_total"))
        offensive_line_adjustment = None
        team_environment_adjustment = None
        if player.position in OFFENSIVE_SKILL_POSITIONS and (
            offensive_line_rank is not None or vegas_win_total is not None
        ):
            if offensive_line_rank is not None and 1.0 <= offensive_line_rank <= 32.0:
                # Rank 1 is best and rank 32 is worst. Keep this distinct from
                # FFA SOS: it describes the player's own blocking environment.
                # Apply it to every offensive skill position: a better line can
                # improve quarterback time, route volume, drive sustainability,
                # and touchdown opportunity across the entire unit.
                offensive_line_factor = (16.5 - offensive_line_rank) / 15.5
                offensive_line_adjustment = (
                    blended * offensive_line_factor * max_offensive_line_adjustment
                )
                blended += offensive_line_adjustment
            if vegas_win_total is not None:
                # Use the observed 4.5-to-12.5 win-total range as a stable
                # normalization. This keeps one team's unusually optimistic or
                # pessimistic line from redefining the scale for every player.
                team_factor = max(-1.0, min(1.0, (vegas_win_total - 8.5) / 4.0))
                role_exposure = 1.0
                if player.position == "RB":
                    receptions = max(
                        0.0,
                        _number(
                            player.stats.get(
                                "receptions", player.stats.get("RECEPTIONS", 0.0)
                            )
                        ),
                    )
                    receiving_resilience = min(1.0, receptions / 60.0)
                    # Receiving backs are less exposed to a poor team's
                    # rushing efficiency and script, while receiving work also
                    # benefits from a strong offense. Keep the total adjustment
                    # bounded by the configured 2.5% cap in either direction.
                    role_exposure = (
                        0.5 + 0.5 * receiving_resilience
                        if team_factor >= 0
                        else 1.0 - 0.5 * receiving_resilience
                    )
                team_environment_adjustment = (
                    blended
                    * team_factor
                    * role_exposure
                    * max_team_environment_adjustment
                )
                blended += team_environment_adjustment
        has_yahoo_projection = "yahoo" in str(player.source or "").casefold()
        has_current_market = market_value is not None
        fantasypros_rank = player.fantasypros_rank
        stale_fringe_candidate = (
            not has_yahoo_projection
            and not has_current_market
            and (player.ffa_auction is None or player.ffa_auction <= 0)
            and (fantasypros_rank is None or fantasypros_rank > 300)
        )
        if stale_fringe_candidate:
            # A stale external projection plus an old auction salary must not
            # rescue a player with no current Yahoo or market signal. Keep the
            # player at the $1 nomination floor so the output remains honest
            # without fabricating a hard inactive status.
            blended = 1.0
            sos_adjustment = None
            offensive_line_adjustment = None
            team_environment_adjustment = None
        raw_sentiment = _sentiment_input(sentiment, player, key)
        sentiment_available = raw_sentiment is not None
        signal = _coerce_sentiment(raw_sentiment) if sentiment_available else SentimentSignal()
        sentiment_delta = (
            blended * signal.score * signal.confidence * max_sentiment_adjustment
            if sentiment_available
            else 0.0
        )
        sentiment_adjustment = sentiment_delta if sentiment_available else None
        suggested = (
            1.0
            if stale_fringe_candidate
            else min(profile.auction_budget, max(1.0, blended + sentiment_delta))
        )
        data_quality = 0
        data_quality += 1 if player.projected_points > 0 else 0
        data_quality += 1 if market_value is not None else 0
        data_quality += 1 if historical_value is not None else 0
        data_quality += 1 if player.ffa_points is not None else 0
        data_quality += 1 if player.fantasypros_points is not None else 0
        data_quality += 1 if signal.confidence > 0 else 0
        # Three source checks is usable but not "high" confidence.  The old
        # threshold made nearly every blended player appear equally certain,
        # even when FantasyPros or league-history coverage was missing.
        confidence = (
            "low"
            if stale_fringe_candidate
            else "high" if data_quality >= 4 else "medium" if data_quality == 3 else "low"
        )
        values.append(
            AuctionValue(
                name=player.name,
                position=player.position,
                team=player.team,
                projected_points=player.projected_points,
                replacement_points=replacement.get(player.position, 0.0),
                vorp=vorp_by_name[key],
                baseline_value=baseline,
                market_value=market_value,
                historical_value=historical_value,
                historical_position_rank=historical_position_rank,
                historical_position_spend_share=historical_spend_shares.get(player.position),
                fantasypros_points=player.fantasypros_points,
                fantasypros_rank=player.fantasypros_rank,
                fantasypros_adp=player.fantasypros_adp,
                sentiment_score=signal.score if sentiment_available else None,
                sentiment_adjustment=sentiment_adjustment,
                suggested_value=suggested,
                confidence=confidence,
                ffa_points=player.ffa_points,
                ffa_adp=player.ffa_adp,
                ffa_rank=player.ffa_rank,
                ffa_auction=player.ffa_auction,
                ffa_custom_projection=player.ffa_custom_projection,
                ffa_popularity=player.ffa_popularity,
                ffa_sos=player.ffa_sos,
                sos_adjustment=sos_adjustment,
                offensive_line_rank=offensive_line_rank,
                vegas_win_total=vegas_win_total,
                offensive_line_adjustment=offensive_line_adjustment,
                team_environment_adjustment=team_environment_adjustment,
                status=player.status,
                sentiment_confidence=signal.confidence if sentiment_available else None,
                sentiment_engagement=signal.engagement if sentiment_available else None,
                sentiment_coverage="provided" if sentiment_available else "unavailable",
            )
        )
    return sorted(values, key=lambda item: item.suggested_value, reverse=True)


def summarize_historical_auction(records: Iterable[HistoricalAuctionRecord]) -> Dict[str, Any]:
    """Summarize league auction prices by season and position."""

    rows = list(records)
    by_position: Dict[str, List[float]] = defaultdict(list)
    by_season: Dict[int, List[float]] = defaultdict(list)
    by_season_position: Dict[int, Dict[str, List[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    by_owner: Dict[str, List[float]] = defaultdict(list)
    owner_positions: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for record in rows:
        by_position[record.position].append(record.salary)
        by_season[record.season].append(record.salary)
        by_season_position[record.season][record.position].append(record.salary)
        if record.owner:
            by_owner[record.owner].append(record.salary)
            owner_positions[record.owner][record.position] += 1

    def summary(values: Sequence[float]) -> Dict[str, float]:
        if not values:
            return {"count": 0, "average": 0.0, "median": 0.0, "minimum": 0.0, "maximum": 0.0}
        return {
            "count": float(len(values)),
            "average": round(sum(values) / len(values), 2),
            "median": round(median(values), 2),
            "minimum": round(min(values), 2),
            "maximum": round(max(values), 2),
        }

    position_spend_share: Dict[str, List[float]] = defaultdict(list)
    by_season_position_summary: Dict[str, Dict[str, Dict[str, float]]] = {}
    for season, positions in sorted(by_season_position.items()):
        season_total = sum(by_season[season])
        by_season_position_summary[str(season)] = {}
        for position, values in sorted(positions.items()):
            share = sum(values) / season_total if season_total else 0.0
            position_spend_share[position].append(share)
            by_season_position_summary[str(season)][position] = {
                **summary(values),
                "total_spend": round(sum(values), 2),
                "spend_share": round(share, 4),
            }

    return {
        "record_count": len(rows),
        "seasons": sorted(by_season),
        "by_position": {
            position: summary(values) for position, values in sorted(by_position.items())
        },
        "by_season": {str(season): summary(values) for season, values in sorted(by_season.items())},
        "by_season_position": by_season_position_summary,
        "position_spend_share": {
            position: round(sum(shares) / len(shares), 4)
            for position, shares in sorted(position_spend_share.items())
            if shares
        },
        "by_owner": {
            owner: {
                **summary(values),
                "total_spend": round(sum(values), 2),
                "positions": dict(sorted(owner_positions[owner].items())),
            }
            for owner, values in sorted(by_owner.items())
        },
    }


def historical_player_values(
    records: Iterable[HistoricalAuctionRecord],
) -> Dict[str, float]:
    """Return player-name averages for diagnostics, not auction pricing."""

    salaries: Dict[str, List[float]] = defaultdict(list)
    for record in records:
        salaries[_normalized_key(record.name)].append(record.salary)
    return {
        name: round(sum(values) / len(values), 2)
        for name, values in salaries.items()
        if values
    }


def historical_position_slot_values(
    records: Iterable[HistoricalAuctionRecord],
) -> Dict[Tuple[str, int], float]:
    """Return historical average salary by position slot.

    Each season is ranked independently by salary within a position.  A
    ``("RB", 13)`` value therefore describes what the league has typically
    paid for its thirteenth running back, regardless of which player occupied
    that slot.  This prevents an old salary from following a player after
    their role and depth chart have changed.
    """

    by_season_position: Dict[Tuple[int, str], List[HistoricalAuctionRecord]] = defaultdict(list)
    for record in records:
        if record.salary > 0 and record.position:
            by_season_position[(record.season, record.position)].append(record)

    slot_salaries: Dict[Tuple[str, int], List[float]] = defaultdict(list)
    for (_season, position), season_records in by_season_position.items():
        ordered = sorted(season_records, key=lambda record: record.salary, reverse=True)
        for position_rank, record in enumerate(ordered, 1):
            slot_salaries[(position, position_rank)].append(record.salary)
    return {
        key: round(sum(salaries) / len(salaries), 2)
        for key, salaries in slot_salaries.items()
        if salaries
    }


def historical_position_spend_shares(
    records: Iterable[HistoricalAuctionRecord],
) -> Dict[str, float]:
    """Return each position's average share of total auction spending."""

    by_season: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for record in records:
        if record.salary > 0 and record.position:
            by_season[record.season][record.position] += record.salary
    shares: Dict[str, List[float]] = defaultdict(list)
    for position_totals in by_season.values():
        season_total = sum(position_totals.values())
        if not season_total:
            continue
        for position, total in position_totals.items():
            shares[position].append(total / season_total)
    return {
        position: round(sum(values) / len(values), 4)
        for position, values in sorted(shares.items())
        if values
    }


def evaluate_keeper(
    projected_auction_value: float,
    keeper_cost: float,
    *,
    risk_penalty: float = 0.0,
    minimum_surplus: float = 3.0,
    minimum_roi: float = 0.10,
) -> Dict[str, Any]:
    """Evaluate a keeper using projected value, cost, and optional risk penalty."""

    projected = max(0.0, float(projected_auction_value))
    cost = max(0.0, float(keeper_cost))
    risk = max(0.0, float(risk_penalty))
    risk_adjusted_value = max(0.0, projected - risk)
    surplus = risk_adjusted_value - cost
    roi = None if cost == 0 else surplus / cost
    keep = surplus >= minimum_surplus and (roi is None or roi >= minimum_roi)
    return {
        "projected_value": round(projected, 2),
        "keeper_cost": round(cost, 2),
        "risk_penalty": round(risk, 2),
        "risk_adjusted_value": round(risk_adjusted_value, 2),
        "surplus": round(surplus, 2),
        "roi": round(roi, 4) if roi is not None else None,
        "recommendation": "KEEP" if keep else "PASS",
        "reason": (
            "Risk-adjusted value clears both surplus and ROI thresholds"
            if keep
            else "Risk-adjusted value does not clear the configured keeper thresholds"
        ),
    }


__all__ = [
    "AuctionMarketRecord",
    "AuctionPrepError",
    "AuctionValue",
    "HistoricalAuctionRecord",
    "LeagueProfile",
    "PlayerProjection",
    "RosterRequirements",
    "SentimentSignal",
    "blend_projection_sources",
    "calculate_projected_points",
    "calculate_replacement_levels",
    "apply_fantasypros_projections",
    "evaluate_keeper",
    "historical_player_values",
    "historical_position_slot_values",
    "historical_position_spend_shares",
    "load_historical_auction_csv",
    "load_historical_auction_files",
    "load_league_profile",
    "load_market_values_csv",
    "load_team_environment_json",
    "load_ffa_projections_csv",
    "load_ffa_custom_rankings_csv",
    "load_fantasypros_csv_signals",
    "load_player_projections_csv",
    "merge_ffa_rankings",
    "normalize_position",
    "normalize_team_code",
    "parse_currency",
    "project_auction_values",
    "summarize_historical_auction",
]
