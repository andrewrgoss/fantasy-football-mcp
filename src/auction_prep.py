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
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _row_value(row: Mapping[str, Any], *names: str) -> Any:
    normalized = {_normalized_key(key): value for key, value in row.items()}
    for name in names:
        if _normalized_key(name) in normalized:
            return normalized[_normalized_key(name)]
    return None


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
    sentiment_score: float
    sentiment_adjustment: float
    suggested_value: float
    confidence: str

    def as_dict(self) -> Dict[str, Any]:
        return {
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
            "fantasypros_points": (
                round(self.fantasypros_points, 2) if self.fantasypros_points is not None else None
            ),
            "fantasypros_rank": (
                round(self.fantasypros_rank, 2) if self.fantasypros_rank is not None else None
            ),
            "fantasypros_adp": (
                round(self.fantasypros_adp, 2) if self.fantasypros_adp is not None else None
            ),
            "sentiment_score": round(self.sentiment_score, 3),
            "sentiment_adjustment": round(self.sentiment_adjustment, 2),
            "suggested_value": round(self.suggested_value, 2),
            "confidence": self.confidence,
        }


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
        for row in csv.DictReader(handle):
            name = str(_row_value(row, "PLAYER_NAME", "PLAYER", "NAME") or "").strip()
            if not name:
                continue
            position = normalize_position(_row_value(row, "POSITION", "POS"))
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
            for canonical, columns in stat_columns.items():
                raw = _row_value(row, *columns)
                if raw not in (None, ""):
                    stats[canonical] = _number(raw)
            recalculated = calculate_projected_points(stats, profile) if stats else 0.0
            source_points = _number(_row_value(row, "FANTASY_POINTS", "PROJECTED_FANTASY_POINTS"))
            points = recalculated if stats else source_points
            projections.append(
                PlayerProjection(
                    name=name,
                    position=position,
                    team=str(_row_value(row, "TEAM") or "").strip(),
                    projected_points=points,
                    stats=stats,
                    source=str(path),
                )
            )
    return projections


def apply_fantasypros_projections(
    players: Sequence[PlayerProjection],
    signals: Mapping[str, Mapping[str, Any]],
    *,
    weight: float = 0.30,
) -> List[PlayerProjection]:
    """Blend normalized FantasyPros projections into local player projections."""

    weight = max(0.0, min(1.0, weight))
    blended: List[PlayerProjection] = []
    for player in players:
        signal = signals.get(player.name.casefold()) or signals.get(player.name)
        if not signal or signal.get("projected_points") is None:
            blended.append(player)
            continue
        external_points = _number(signal.get("projected_points"))
        points = (player.projected_points * (1 - weight)) + (external_points * weight)
        blended.append(
            PlayerProjection(
                name=player.name,
                position=player.position,
                team=player.team,
                projected_points=round(points, 4),
                stats=player.stats,
                source=f"{player.source}+fantasypros",
                fantasypros_points=external_points,
                fantasypros_rank=_number(signal.get("rank")),
                fantasypros_adp=_number(signal.get("adp")),
            )
        )
    return blended


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
        if position in FLEX_POSITIONS or position == "W/R/T":
            continue
        for player in by_position.get(position, [])[:count]:
            selected[position].append(player)
            selected_names.add(player.name.casefold())

    flex_slots = profile.roster.starters.get("W/R/T", 0) + profile.roster.starters.get("FLEX", 0)
    remaining_flex = [
        player
        for position in FLEX_POSITIONS
        for player in by_position.get(position, [])
        if player.name.casefold() not in selected_names
    ]
    remaining_flex.sort(key=lambda item: item.projected_points, reverse=True)
    for player in remaining_flex[: profile.teams * flex_slots]:
        selected[player.position].append(player)
        selected_names.add(player.name.casefold())

    levels: Dict[str, float] = {}
    for position, position_players in selected.items():
        levels[position] = position_players[-1].projected_points if position_players else 0.0
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


def project_auction_values(
    players: Sequence[PlayerProjection],
    profile: LeagueProfile,
    market_values: Optional[Mapping[str, AuctionMarketRecord]] = None,
    historical_records: Optional[Iterable[HistoricalAuctionRecord]] = None,
    sentiment: Optional[Mapping[str, Any]] = None,
    market_weight: float = 0.25,
    historical_weight: float = 0.15,
    max_sentiment_adjustment: float = 0.08,
    max_price_fraction: float = 0.35,
) -> List[AuctionValue]:
    """Calculate league-specific auction values from projections and optional signals."""

    if not players:
        return []
    market_weight = max(0.0, min(1.0, market_weight))
    historical_weight = max(0.0, min(1.0, historical_weight))
    max_sentiment_adjustment = max(0.0, min(0.25, max_sentiment_adjustment))
    max_price_fraction = max(0.05, min(1.0, max_price_fraction))
    market_values = market_values or {}
    historical_values = historical_player_values(historical_records or [])
    sentiment = sentiment or {}
    replacement = calculate_replacement_levels(players, profile)
    vorp_by_name = {
        player.name.casefold(): max(
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
    values: List[AuctionValue] = []

    for player in players:
        key = player.name.casefold()
        market = market_values.get(key) or market_values.get(player.name)
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
        historical_value = historical_values.get(key)
        if historical_value is not None:
            blended = (blended * (1 - historical_weight)) + (historical_value * historical_weight)
        signal = _coerce_sentiment(sentiment.get(key) or sentiment.get(player.name, {}))
        sentiment_adjustment = blended * signal.score * signal.confidence * max_sentiment_adjustment
        suggested = min(profile.auction_budget, max(1.0, blended + sentiment_adjustment))
        data_quality = 0
        data_quality += 1 if player.projected_points > 0 else 0
        data_quality += 1 if market_value is not None else 0
        data_quality += 1 if historical_value is not None else 0
        data_quality += 1 if player.fantasypros_points is not None else 0
        data_quality += 1 if signal.confidence > 0 else 0
        confidence = "high" if data_quality >= 3 else "medium" if data_quality == 2 else "low"
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
                fantasypros_points=player.fantasypros_points,
                fantasypros_rank=player.fantasypros_rank,
                fantasypros_adp=player.fantasypros_adp,
                sentiment_score=signal.score,
                sentiment_adjustment=sentiment_adjustment,
                suggested_value=suggested,
                confidence=confidence,
            )
        )
    return sorted(values, key=lambda item: item.suggested_value, reverse=True)


def summarize_historical_auction(records: Iterable[HistoricalAuctionRecord]) -> Dict[str, Any]:
    """Summarize league auction prices by season and position."""

    rows = list(records)
    by_position: Dict[str, List[float]] = defaultdict(list)
    by_season: Dict[int, List[float]] = defaultdict(list)
    by_owner: Dict[str, List[float]] = defaultdict(list)
    owner_positions: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for record in rows:
        by_position[record.position].append(record.salary)
        by_season[record.season].append(record.salary)
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

    return {
        "record_count": len(rows),
        "seasons": sorted(by_season),
        "by_position": {
            position: summary(values) for position, values in sorted(by_position.items())
        },
        "by_season": {str(season): summary(values) for season, values in sorted(by_season.items())},
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
    """Return each historically drafted player's average auction salary."""

    salaries: Dict[str, List[float]] = defaultdict(list)
    for record in records:
        salaries[record.name.casefold()].append(record.salary)
    return {
        name: round(sum(values) / len(values), 2)
        for name, values in salaries.items()
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
    "calculate_projected_points",
    "calculate_replacement_levels",
    "apply_fantasypros_projections",
    "evaluate_keeper",
    "historical_player_values",
    "load_historical_auction_csv",
    "load_historical_auction_files",
    "load_league_profile",
    "load_market_values_csv",
    "load_player_projections_csv",
    "normalize_position",
    "parse_currency",
    "project_auction_values",
    "summarize_historical_auction",
]
