"""Tests for league-agnostic offline auction preparation."""

from pathlib import Path

import pytest

from src.auction_prep import (
    blend_projection_sources,
    LeagueProfile,
    apply_fantasypros_projections,
    PlayerProjection,
    calculate_projected_points,
    evaluate_keeper,
    HistoricalAuctionRecord,
    load_historical_auction_csv,
    load_historical_auction_files,
    load_league_profile,
    load_ffa_custom_rankings_csv,
    load_ffa_projections_csv,
    load_fantasypros_csv_signals,
    load_market_values_csv,
    load_player_projections_csv,
    load_team_environment_json,
    merge_ffa_rankings,
    parse_currency,
    project_auction_values,
    calculate_replacement_levels,
    historical_position_slot_values,
    historical_position_spend_shares,
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


def test_projection_csv_handles_legacy_yahoo_receiving_column_order(tmp_path):
    path = tmp_path / "legacy_yahoo.csv"
    path.write_text(
        "PLAYER_NAME,TEAM,POSITION,FANTASY_POINTS,RUSHING_YDS,RUSHING_TD,RECEPTIONS,RECEIVING_YDS,RECEIVING_TD,TARGETS\n"
        "Legacy Receiver,ABC,WR,248,0,0,120,100,1000,8\n",
        encoding="utf-8",
    )
    rows = load_player_projections_csv(str(path), profile())
    assert rows[0].projected_points == 248.0
    assert rows[0].stats["receptions"] == 100
    assert rows[0].stats["receiving_yards"] == 1000
    assert rows[0].stats["receiving_touchdowns"] == 8


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


def test_historical_positions_are_ranked_by_slot_and_spend_share():
    records = [
        HistoricalAuctionRecord(2024, "RB1", "RB", "ABC", 50, "Manager"),
        HistoricalAuctionRecord(2024, "RB2", "RB", "ABC", 20, "Manager"),
        HistoricalAuctionRecord(2024, "WR1", "WR", "ABC", 30, "Manager"),
        HistoricalAuctionRecord(2025, "Different RB1", "RB", "ABC", 40, "Manager"),
        HistoricalAuctionRecord(2025, "Different RB2", "RB", "ABC", 10, "Manager"),
        HistoricalAuctionRecord(2025, "Different WR1", "WR", "ABC", 50, "Manager"),
    ]

    slots = historical_position_slot_values(records)
    shares = historical_position_spend_shares(records)

    assert slots[("RB", 1)] == 45
    assert slots[("RB", 2)] == 15
    assert shares["RB"] == pytest.approx((70 / 100 + 50 / 100) / 2)


def test_historical_pricing_uses_current_position_slot_not_player_name():
    records = [
        HistoricalAuctionRecord(2025, "Former RB1", "RB", "ABC", 60, "Manager"),
        HistoricalAuctionRecord(2025, "Dameon Pierce", "RB", "ABC", 20, "Manager"),
    ]
    values = project_auction_values(
        [
            PlayerProjection("Dameon Pierce", "RB", "ABC", 300),
            PlayerProjection("Current RB2", "RB", "ABC", 250),
        ],
        profile(),
        historical_records=records,
        historical_weight=1.0,
    )

    by_name = {value.name: value for value in values}
    assert by_name["Dameon Pierce"].historical_position_rank == 1
    assert by_name["Dameon Pierce"].historical_value == 60
    assert by_name["Current RB2"].historical_position_rank == 2
    assert by_name["Current RB2"].historical_value == 20


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
    assert "sentiment_score" in values[0].as_dict()
    assert all(value.suggested_value >= 1 for value in values)


def test_missing_sentiment_is_explicitly_unavailable():
    values = project_auction_values(
        [PlayerProjection("No Reddit Signal", "WR", "ABC", 200)], profile()
    )

    result = values[0]
    assert result.sentiment_score is None
    assert result.sentiment_adjustment is None
    assert result.sentiment_confidence is None
    assert result.sentiment_coverage == "unavailable"
    assert result.confidence == "low"
    assert "sentiment_score" not in result.as_dict()
    assert "sentiment_adjustment" not in result.as_dict()


def test_supplied_neutral_sentiment_is_distinct_from_missing():
    values = project_auction_values(
        [PlayerProjection("Neutral Signal", "WR", "ABC", 200)],
        profile(),
        sentiment={"Neutral Signal": {"score": 0, "confidence": 0.8}},
    )

    result = values[0]
    assert result.sentiment_score == 0
    assert result.sentiment_adjustment == 0
    assert result.sentiment_confidence == 0.8
    assert result.sentiment_coverage == "provided"


def test_replacement_level_uses_lowest_selected_player_not_append_order():
    p = profile()
    # The two fixed RB slots require 24 RBs.  Two flex slots then select the
    # best remaining RB/WR/TE players.  The replacement RB must be the lowest
    # selected RB, not whichever RB happened to be appended last by flex order.
    players = [
        PlayerProjection(f"RB {rank}", "RB", "ABC", 300 - rank * 5)
        for rank in range(1, 50)
    ] + [
        PlayerProjection(f"WR {rank}", "WR", "ABC", 400 - rank * 4)
        for rank in range(1, 80)
    ] + [
        PlayerProjection(f"TE {rank}", "TE", "ABC", 200 - rank * 4)
        for rank in range(1, 30)
    ]
    levels = calculate_replacement_levels(players, p)
    assert levels["RB"] == 170


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


def test_ffa_loader_recalculates_full_ppr_points(tmp_path):
    path = tmp_path / "ffa.csv"
    path.write_text(
        "Player,Pos,Team,Games,Pass Att,Pass Cmp,Pass Yds,Pass TDs,INTs,Carries,Rush Yds,Rush TDs,Targets,Receptions,Rec Yds,Rec TDs,PPR ADP,HPPR ADP,Std ADP\n"
        "Example Receiver,WR,ABC,—,0,0,0,0,0,2,10,1,—,5,50,1,12,14,16\n",
        encoding="utf-8",
    )
    players = load_ffa_projections_csv(str(path), profile())
    assert players[0].projected_points == 23
    assert players[0].ffa_points == 23
    assert players[0].ffa_adp == 12


def test_projection_sources_use_ffa_yahoo_fantasypros_weights():
    blended = blend_projection_sources(
        [PlayerProjection("Example Player", "WR", "ABC", 100)],
        ffa_players=[PlayerProjection("Example Player", "WR", "ABC", 200, ffa_points=200)],
        fantasypros_signals={"example player": {"projected_points": 300}},
        ffa_weight=0.40,
        yahoo_weight=0.30,
        fantasypros_weight=0.30,
    )
    assert blended[0].projected_points == 200
    assert blended[0].ffa_points == 200
    assert blended[0].fantasypros_points == 300


def test_projection_sources_join_name_suffixes_without_duplicates():
    blended = blend_projection_sources(
        [PlayerProjection("James Cook III", "RB", "BUF", 250)],
        ffa_players=[PlayerProjection("James Cook", "RB", "BUF", 300, ffa_points=300)],
    )
    assert len(blended) == 1
    assert blended[0].projected_points == pytest.approx(278.5714)


def test_projection_sources_join_known_nickname_alias():
    blended = blend_projection_sources(
        [PlayerProjection("Kenneth Walker III", "RB", "KC", 200)],
        ffa_players=[PlayerProjection("Ken Walker", "RB", "KC", 300, ffa_auction=38)],
    )
    assert len(blended) == 1
    assert blended[0].projected_points == pytest.approx(257.1429)


def test_projection_sources_prefer_current_fantasypros_team_without_yahoo():
    blended = blend_projection_sources(
        [],
        ffa_players=[PlayerProjection("Example Player", "RB", "KC", 200, ffa_auction=0)],
        fantasypros_signals={
            "example player": {
                "name": "Example Player",
                "team": "PHI",
                "projected_points": 200,
            }
        },
    )
    assert blended[0].team == "PHI"


@pytest.mark.parametrize(
    "yahoo_name,ffa_name",
    [
        ("Kenneth Gainwell", "Kenny Gainwell"),
        ("Chigoziem Okonkwo", "Chig Okonkwo"),
    ],
)
def test_projection_sources_join_documented_nickname_aliases(yahoo_name, ffa_name):
    blended = blend_projection_sources(
        [PlayerProjection(yahoo_name, "TE" if "Okonkwo" in yahoo_name else "RB", "ABC", 200)],
        ffa_players=[
            PlayerProjection(
                ffa_name,
                "TE" if "Okonkwo" in yahoo_name else "RB",
                "ABC",
                300,
                ffa_points=300,
            )
        ],
    )
    assert len(blended) == 1


def test_ffa_only_zero_auction_records_are_not_candidates():
    blended = blend_projection_sources(
        [PlayerProjection("Current Player", "RB", "ABC", 200)],
        ffa_players=[
            PlayerProjection("Stale FFA Player", "RB", "ABC", 180, ffa_auction=0),
            PlayerProjection("FFA Auction Player", "RB", "ABC", 170, ffa_auction=12),
        ],
    )
    assert {player.name for player in blended} == {"Current Player", "FFA Auction Player"}


def test_zero_projection_players_are_not_rescued_by_history():
    values = project_auction_values(
        [
            PlayerProjection("Inactive Player", "RB", "ABC", 0),
            PlayerProjection("Active Player", "RB", "ABC", 200),
        ],
        profile(),
        historical_records=[
            HistoricalAuctionRecord(2025, "Inactive Player", "ABC", "RB", 40, "Manager")
        ],
    )
    assert [value.name for value in values] == ["Active Player"]


def test_stale_fringe_sources_are_capped_at_one_dollar():
    values = project_auction_values(
        [
            PlayerProjection(
                "Stale Fringe Player",
                "WR",
                "ABC",
                24.0,
                source="ffa+fantasypros",
                fantasypros_points=24.0,
                fantasypros_rank=442,
                ffa_auction=0,
            )
        ],
        profile(),
        historical_records=[
            HistoricalAuctionRecord(2025, "Stale Fringe Player", "ABC", "WR", 21, "Manager")
        ],
    )

    assert values[0].suggested_value == 1.0
    assert values[0].confidence == "low"


def test_ir_player_is_excluded_even_if_other_sources_have_points(tmp_path):
    path = tmp_path / "projections.csv"
    path.write_text(
        "PLAYER_NAME,TEAM,POSITION,PLAYER_STATUS,GP*,RECEPTIONS,RECEIVING_YDS,RECEIVING_TD\n"
        "Unavailable Receiver,ABC,WR,IR,0,40,500,5\n",
        encoding="utf-8",
    )
    yahoo = load_player_projections_csv(str(path), profile())
    blended = blend_projection_sources(
        yahoo,
        ffa_players=[
            PlayerProjection("Unavailable Receiver", "WR", "ABC", 220, ffa_auction=20)
        ],
    )
    assert blended == []


def test_ffa_custom_rankings_merge_keeps_rank_and_auction_context(tmp_path):
    path = tmp_path / "ffa_custom.csv"
    path.write_text(
        "Rank,Player,Team,Pos,Pos Rk,Tier,Value,Proj,ADP,Bye,SOS,Auction,Popularity\n"
        "1,Example Player,ABC,WR,WR1,1,900,300,2.5,7,4,55,0.82\n",
        encoding="utf-8",
    )
    rankings = load_ffa_custom_rankings_csv(str(path))
    merged = merge_ffa_rankings(
        [PlayerProjection("Example Player", "WR", "ABC", 200)], rankings
    )
    assert merged[0].projected_points == 250
    assert merged[0].ffa_custom_projection == 300
    assert merged[0].ffa_rank == 1
    assert merged[0].ffa_auction == 55
    assert merged[0].ffa_popularity == 0.82
    assert merged[0].ffa_sos == 4


def test_ffa_sos_is_a_bounded_small_value_adjustment():
    values = project_auction_values(
        [
            PlayerProjection(
                "Easy Schedule",
                "WR",
                "ABC",
                300,
                source="yahoo+ffa",
                ffa_sos=1,
            ),
            PlayerProjection(
                "Hard Schedule",
                "WR",
                "ABC",
                300,
                source="yahoo+ffa",
                ffa_sos=32,
            ),
        ],
        profile(),
        max_sos_adjustment=0.025,
    )

    by_name = {value.name: value for value in values}
    assert by_name["Easy Schedule"].sos_adjustment > 0
    assert by_name["Hard Schedule"].sos_adjustment < 0
    assert abs(by_name["Easy Schedule"].sos_adjustment) <= 1.75
    assert abs(by_name["Hard Schedule"].sos_adjustment) <= 1.75


def test_team_environment_loader_normalizes_codes_and_fields(tmp_path):
    path = tmp_path / "team_environment.json"
    path.write_text(
        '{"teams": {"JAC": {"offensive_line_rank": 16, "vegas_win_total": 7.5}}}',
        encoding="utf-8",
    )
    loaded = load_team_environment_json(str(path))
    assert loaded == {
        "JAX": {"offensive_line_rank": 16.0, "vegas_win_total": 7.5}
    }


def test_offensive_environment_adjustments_are_small_and_receiving_resilient():
    values = project_auction_values(
        [
            PlayerProjection(
                "Receiving RB",
                "RB",
                "PHI",
                250,
                stats={"receptions": 70},
                source="yahoo+ffa",
            ),
            PlayerProjection(
                "Early Down RB",
                "RB",
                "CLE",
                250,
                stats={"receptions": 10},
                source="yahoo+ffa",
            ),
            PlayerProjection(
                "Context WR",
                "WR",
                "CLE",
                250,
                source="yahoo+ffa",
            ),
            PlayerProjection(
                "Context DEF",
                "DEF",
                "PHI",
                100,
                source="yahoo+ffa",
            ),
        ],
        profile(),
        team_environment={
            "PHI": {"offensive_line_rank": 2, "vegas_win_total": 11.5},
            "CLE": {"offensive_line_rank": 28, "vegas_win_total": 5.5},
        },
        max_sos_adjustment=0.025,
        max_offensive_line_adjustment=0.025,
        max_team_environment_adjustment=0.025,
    )
    by_name = {value.name: value for value in values}
    receiving = by_name["Receiving RB"]
    early = by_name["Early Down RB"]
    receiver_context = by_name["Context WR"]
    defense_context = by_name["Context DEF"]

    assert receiving.offensive_line_adjustment > 0
    assert receiving.team_environment_adjustment > 0
    assert early.offensive_line_adjustment < 0
    assert early.team_environment_adjustment < 0
    assert abs(receiving.offensive_line_adjustment) <= receiving.suggested_value * 0.025
    assert abs(receiving.team_environment_adjustment) <= receiving.suggested_value * 0.025
    assert receiver_context.offensive_line_adjustment < 0
    assert receiver_context.team_environment_adjustment < 0
    assert abs(receiver_context.offensive_line_adjustment) <= receiver_context.suggested_value * 0.025
    assert abs(receiver_context.team_environment_adjustment) <= receiver_context.suggested_value * 0.025
    assert defense_context.offensive_line_adjustment is None
    assert defense_context.team_environment_adjustment is None
    assert abs(early.team_environment_adjustment) < abs(
        early.suggested_value * 0.025
    )


def test_fantasypros_csv_loader_handles_duplicate_stat_headers_and_rankings(tmp_path):
    flx = tmp_path / "fantasypros_flx.csv"
    flx.write_text(
        "Player,Team,POS,ATT,YDS,TDS,REC,YDS,TDS,FL,FPTS\n"
        "\xa0,\xa0,,,,,,,,,\n"
        "Example Runner,ABC,RB1,200,1000,10,50,400,3,2,300\n",
        encoding="utf-8",
    )
    qb = tmp_path / "fantasypros_qb.csv"
    qb.write_text(
        "Player,Team,ATT,CMP,YDS,TDS,INTS,ATT,YDS,TDS,FL,FPTS\n"
        "Example Quarterback,ABC,500,330,4000,30,10,80,400,5,2,300\n",
        encoding="utf-8",
    )
    rankings = tmp_path / "fantasypros_rankings.csv"
    rankings.write_text(
        "RK,TIERS,PLAYER NAME,TEAM,POS\n"
        "7,2,Example Runner,ABC,RB3\n"
        "8,2,Example Quarterback,ABC,QB2\n",
        encoding="utf-8",
    )

    signals = load_fantasypros_csv_signals(
        [str(flx), str(qb)], rankings_path=str(rankings)
    )
    assert signals["EXAMPLERUNNER"]["projected_points"] == 300
    assert signals["EXAMPLERUNNER"]["rank"] == 7
    assert signals["EXAMPLEQUARTERBACK"]["projected_points"] == 300
    assert signals["EXAMPLEQUARTERBACK"]["rank"] == 8
    assert all(signal.get("adp") is None for signal in signals.values())


def test_fantasypros_nested_projection_shape_uses_requested_scoring():
    signals = normalize_player_signals(
        {
            "players": [
                {
                    "name": "Example Runner",
                    "position_id": "RB",
                    "team_id": "XYZ",
                    "stats": {
                        "points": 220,
                        "points_ppr": 275,
                        "points_half": 247.5,
                    },
                }
            ]
        },
        scoring="PPR",
    )
    assert signals["example runner"]["projected_points"] == 275
    assert signals["example runner"]["position"] == "RB"


def test_fantasypros_player_metadata_normalizes_scoring_specific_rank_and_adp():
    signals = normalize_player_signals(
        {
            "players": [
                {
                    "player_name": "Example Runner",
                    "rank_ecr_ppr": 12,
                    "rank_adp_ppr": 15.5,
                }
            ]
        },
        scoring="PPR",
    )
    assert signals["example runner"]["rank"] == 12
    assert signals["example runner"]["adp"] == 15.5


def test_fantasypros_client_requires_explicit_key():
    with pytest.raises(FantasyProsConfigurationError):
        import asyncio

        asyncio.run(FantasyProsClient(api_key="").get_projections(2026))


def test_public_examples_are_sanitized_and_loadable():
    """Keep public sample schemas executable without relying on private data."""

    root = Path(__file__).resolve().parents[2]
    examples = root / "data" / "examples"
    public_profile = load_league_profile(
        str(root / "config" / "league_profile.example.json")
    )

    yahoo = load_player_projections_csv(
        str(examples / "yahoo_player_projections.example.csv"), public_profile
    )
    market = load_market_values_csv(
        str(examples / "yahoo_market_values.example.csv")
    )
    history = load_historical_auction_csv(
        str(examples / "historical_auction_results.example.csv")
    )
    ffa = load_ffa_projections_csv(
        str(examples / "ffa_detailed_projections.example.csv"), public_profile
    )
    ffa_rankings = load_ffa_custom_rankings_csv(
        str(examples / "ffa_custom_rankings.example.csv")
    )
    fantasypros = load_fantasypros_csv_signals(
        [
            str(examples / "fantasypros_projections.example.csv"),
            str(examples / "fantasypros_qb_projections.example.csv"),
        ],
        rankings_path=str(examples / "fantasypros_rankings.example.csv"),
    )
    team_environment = load_team_environment_json(
        str(examples / "2026_team_environment.json")
    )

    assert yahoo and market and history and ffa and ffa_rankings and fantasypros
    assert len(team_environment) == 32
    assert public_profile.league_id == "replace-with-league-id"
    # Public history demonstrates price-by-position without publishing any
    # manager or fantasy-team identity.
    assert all(record.owner is None for record in history)
