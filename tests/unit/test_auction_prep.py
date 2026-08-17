"""Tests for league-agnostic offline auction preparation."""

import pytest

from src.auction_prep import (
    LeagueProfile,
    apply_fantasypros_projections,
    PlayerProjection,
    calculate_projected_points,
    evaluate_keeper,
    load_historical_auction_csv,
    load_historical_auction_files,
    load_market_values_csv,
    load_player_projections_csv,
    parse_currency,
    project_auction_values,
    summarize_historical_auction,
)
from src.fantasypros_api import (
    FantasyProsClient,
    FantasyProsConfigurationError,
    normalize_player_signals,
)


def profile() -> LeagueProfile:
    return LeagueProfile.from_dict(
        {
            "season": 2026,
            "platform": "Yahoo Fantasy Football",
            "league": {
                "id": "example",
                "name": "Example League",
                "teams": 12,
                "auction_budget": 200,
                "scoring_type": "head_to_head",
            },
            "roster": {
                "starters": {"QB": 1, "WR": 3, "RB": 2, "TE": 1, "W/R/T": 2, "DEF": 1},
                "bench": 5,
                "injured_reserve": 2,
            },
            "scoring": {
                "offense": {
                    "passing_yards_per_point": 25,
                    "passing_touchdown": 4,
                    "interception": -2,
                    "rushing_yards_per_point": 10,
                    "rushing_touchdown": 6,
                    "reception": 1,
                    "receiving_yards_per_point": 10,
                    "receiving_touchdown": 6,
                    "return_touchdown": 6,
                    "two_point_conversion": 2,
                    "fumble_lost": -2,
                }
            },
        }
    )


def test_parse_currency_and_full_ppr_projection():
    assert parse_currency("$1,234.50 ") == 1234.5
    assert parse_currency("") is None
    assert calculate_projected_points(
        {"receptions": 100, "receiving_yards": 1000, "receiving_touchdowns": 8}, profile()
    ) == 248.0


def test_projection_csv_recalculates_using_profile(tmp_path):
    path = tmp_path / "projections.csv"
    path.write_text(
        "PLAYER_NAME,TEAM,POSITION,FANTASY_POINTS,RECEPTIONS,RECEIVING_YDS,RECEIVING_TD\n"
        "Example Receiver,ABC,WR,10,100,1000,8\n",
        encoding="utf-8",
    )
    rows = load_player_projections_csv(str(path), profile())
    assert rows[0].projected_points == 248.0
    assert rows[0].position == "WR"


def test_market_and_history_csvs_are_normalized(tmp_path):
    market_path = tmp_path / "market.csv"
    market_path.write_text(
        "PLAYER_NAME,TEAM,POSITION,LEAGUE_VALUE,PROJ_VALUE,AVG_COST,PREVIOUS_OWNER\n"
        "Example Receiver,ABC,WR,$42 ,$40 ,$38.50 ,FA\n",
        encoding="utf-8",
    )
    history_path = tmp_path / "history.csv"
    history_path.write_text(
        "Year,Pick,Player,Team,Position,Salary,Owner\n"
        "2025,1,Example Receiver,ABC,WR,$42 ,Manager\n",
        encoding="utf-8",
    )
    market = load_market_values_csv(str(market_path))
    history = load_historical_auction_csv(str(history_path))
    assert market["example receiver"].league_value == 42
    assert history[0].salary == 42
    summary = summarize_historical_auction(history)
    assert summary["by_position"]["WR"]["median"] == 42
    assert summary["by_owner"]["Manager"]["total_spend"] == 42


def test_historical_loader_accepts_a_directory(tmp_path):
    for season, salary in ((2024, 42), (2025, 45)):
        (tmp_path / f"draft_{season}.csv").write_text(
            "Year,Pick,Player,Team,Position,Salary,Owner\n"
            f"{season},1,Example Receiver,ABC,WR,${salary},Manager\n",
            encoding="utf-8",
        )
    records = load_historical_auction_files([str(tmp_path)])
    assert [record.season for record in records] == [2024, 2025]
    assert records[0].salary == 42


def test_auction_values_are_bounded_and_accept_sentiment():
    p = profile()
    players = [
        PlayerProjection("Top WR", "WR", "ABC", 300),
        PlayerProjection("Second WR", "WR", "ABC", 250),
        PlayerProjection("Top RB", "RB", "ABC", 280),
        PlayerProjection("Top QB", "QB", "ABC", 290),
    ]
    values = project_auction_values(
        players,
        p,
        sentiment={"top wr": {"score": 1, "confidence": 1}},
        max_price_fraction=0.35,
    )
    assert values[0].suggested_value <= 200
    assert values[0].sentiment_adjustment > 0
    assert all(value.suggested_value >= 1 for value in values)


def test_keeper_evaluation_accounts_for_risk():
    keep = evaluate_keeper(50, 20, risk_penalty=5)
    pass_result = evaluate_keeper(25, 24, risk_penalty=3)
    assert keep["recommendation"] == "KEEP"
    assert pass_result["recommendation"] == "PASS"


def test_fantasypros_signals_normalize_and_blend_without_network():
    signals = normalize_player_signals(
        {
            "players": [
                {
                    "player_name": "Example Receiver",
                    "player_team_id": "ABC",
                    "rank_ecr": 7,
                    "adp": 9.5,
                    "projected_points": 300,
                }
            ]
        }
    )
    blended = apply_fantasypros_projections(
        [PlayerProjection("Example Receiver", "WR", "ABC", 200)], signals, weight=0.5
    )
    assert blended[0].projected_points == 250
    assert blended[0].fantasypros_rank == 7
    assert blended[0].fantasypros_adp == 9.5


def test_fantasypros_client_requires_explicit_key():
    with pytest.raises(FantasyProsConfigurationError):
        import asyncio

        asyncio.run(FantasyProsClient(api_key="").get_projections(2026))
