# Fantasy Football MCP

A local Model Context Protocol server for Yahoo Fantasy Football analysis, live
league tools, and offline salary-cap draft preparation.

The project supports two complementary workflows:

- **Live Yahoo tools** for leagues, rosters, standings, matchups, players,
  waivers, draft results, and lineup analysis when Yahoo Fantasy Sports API
  access is approved.
- **Offline auction tools** that work from private local exports without Yahoo,
  Reddit, or FantasyPros API approval. These tools calculate scoring-aware
  projections, replacement levels, position-slot auction history, keeper
  surplus, tiers, and bounded context adjustments.

Private credentials, league profiles, exports, and generated strategy documents
do not belong in the public repository. The included examples use public NFL
context or invented league/player data.

## Highlights

- Yahoo multi-league discovery and read-only league analysis.
- Salary-cap values derived from a caller-supplied scoring and roster profile.
- Configurable Yahoo, Fantasy Football Advice (FFA), and FantasyPros projection
  blending with per-player renormalization when a source is missing.
- Current Yahoo market values and historical position-slot prices used as
  separate calibration layers.
- Small, explainable strength-of-schedule, offensive-line, and team-environment
  adjustments.
- Keeper surplus analysis and a reusable workflow for producing a private
  auction strategy document.
- Optional Sleeper enrichment and Reddit sentiment. Reddit remains disabled
  unless the application has explicit Data API approval.

## MCP tools

| Area | Tools |
| --- | --- |
| League | `ff_get_leagues`, `ff_get_league_info`, `ff_get_standings` |
| Rosters and matchups | `ff_get_roster`, `ff_get_matchup`, `ff_compare_teams`, `ff_build_lineup` |
| Players and waivers | `ff_get_players`, `ff_get_waiver_wire`, `ff_get_draft_rankings` |
| Draft | `ff_get_draft_recommendation`, `ff_analyze_draft_state`, `ff_get_draft_results` |
| Offline auction | `ff_get_auction_profile`, `ff_project_auction_values`, `ff_summarize_historical_auction`, `ff_evaluate_keeper` |
| Optional integrations | `ff_analyze_reddit_sentiment` |
| Operations | `ff_refresh_token`, `ff_get_api_status`, `ff_clear_cache` |

## Quick start

```bash
git clone https://github.com/andrewrgoss/fantasy-football-mcp.git
cd fantasy-football-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp config/league_profile.example.json config/league_profile.local.json
```

Edit only the local `.env` and `config/league_profile.local.json`. Both are
ignored by Git.

Start the stdio MCP server:

```bash
.venv/bin/python fantasy_football_multi_league.py
```

Or start the FastMCP HTTP server:

```bash
.venv/bin/python fastmcp_server.py
```

An MCP client can register the stdio server with the repository's absolute
paths:

```json
{
  "mcpServers": {
    "yahoo-fantasy-football": {
      "command": "/absolute/path/fantasy-football-mcp/.venv/bin/python",
      "args": [
        "/absolute/path/fantasy-football-mcp/fantasy_football_multi_league.py"
      ]
    }
  }
}
```

Restart the MCP client after changing `.env`, authentication state, or server
code.

## Offline auction preparation

The offline workflow is the easiest way to use the project. It does not require
Yahoo or Reddit API approval and can use downloaded FantasyPros CSVs instead of
the limited free API response.

Typical private inputs are:

- a local league-profile JSON copied from
  [`config/league_profile.example.json`](config/league_profile.example.json);
- Yahoo season projections and pre-draft auction values;
- optional FFA detailed projections and custom rankings;
- optional FantasyPros FLX, QB, and overall rankings CSV downloads;
- one or more historical auction-results CSVs; and
- optional public team context such as
  [`data/examples/2026_team_environment.json`](data/examples/2026_team_environment.json).

The repository includes invented CSV examples under [`data/examples`](data/examples)
and a complete guide in
[`docs/OFFLINE_AUCTION_PREP.md`](docs/OFFLINE_AUCTION_PREP.md).

The default three-source projection blend, when all sources are supplied, is
FFA 40%, Yahoo 30%, and FantasyPros 30%. These are configurable inputs rather
than universal truth. Yahoo market prices and historical auction prices are not
folded into those percentages; they calibrate the projection-derived value
afterward.

Historical prices are matched by current position slot, not by player name. A
current RB13 is compared with historical RB13 prices. This avoids treating an
old salary paid for a now-changed player role as current evidence.

## Data sources and approval status

### Yahoo

Yahoo Fantasy Sports API access is separately reviewed and read-only. OAuth
credentials alone do not prove that the application is provisioned for Fantasy
Sports. The copy-ready application language, OAuth setup, provisioning preflight,
and fallback options are in
[`docs/YAHOO_API_SETUP.md`](docs/YAHOO_API_SETUP.md).

Existing browser-export workflows can be used instead of waiting for approval:

- [Yahoo Fantasy Football Scraper](https://github.com/andrewrgoss/yahoo-fantasy-fball-scraper)
- [Yahoo Fantasy Auction Optimizer](https://github.com/andrewrgoss/yahoo-fantasy-auction-optimizer)

This repository reads compatible exports in place; it does not copy them into
source control.

### FantasyPros

The optional API client is retained, but the free API may return only a limited
subset of projections/rankings and does not provide useful pagination for the
missing player pool. Downloaded CSV exports are therefore the recommended input
for a complete offline board. See
[`docs/FANTASYPROS_DATA.md`](docs/FANTASYPROS_DATA.md) for key-request language,
terms, API limitations, and CSV setup.

### Reddit

Reddit sentiment is optional and unavailable without explicit Data API approval.
The repository retains the request language and local privacy rules, but the
offline auction workflow does not fabricate sentiment placeholders when Reddit
is unavailable. See:

- [`docs/REDDIT_API_SETUP.md`](docs/REDDIT_API_SETUP.md)
- [`docs/REDDIT_DATA_HANDLING.md`](docs/REDDIT_DATA_HANDLING.md)

### Sleeper

Sleeper's public endpoints are used by optional roster, waiver, trending, and
recent-performance enrichment. No Sleeper account credentials are required by
the current client.

## Strategy-document workflow

The auction values are inputs to a strategy, not the strategy itself. Keeper
rules, likely opponent keepers, positional tier breaks, budget allocation,
roster constraints, and live news still require explicit analysis.

The process is documented in
[`docs/STRATEGY_DOCUMENT_WORKFLOW.md`](docs/STRATEGY_DOCUMENT_WORKFLOW.md), with
a fully sanitized example at
[`examples/auction_draft_strategy.example.md`](examples/auction_draft_strategy.example.md).

Generated documents should be written to a private location or `data/local/`,
not committed.

## Privacy and security

Never commit:

- `.env` or OAuth credentials;
- `.yahoo_token.json`, `.py.json`, or other token files;
- `config/league_profile.local.json`;
- private league identifiers, names, manager/team names, keeper sheets, or
  historical exports;
- proprietary projection downloads; or
- generated personal auction boards and strategy documents.

The repository ignores the conventional private locations. Before publishing,
run the privacy checks described in
[`docs/OFFLINE_AUCTION_PREP.md`](docs/OFFLINE_AUCTION_PREP.md).

## Development

Run the focused offline and privacy tests:

```bash
.venv/bin/python -m pytest -q \
  tests/unit/test_auction_prep.py \
  tests/unit/test_reddit_privacy.py
```

Run the complete available suite:

```bash
.venv/bin/python -m pytest
```

The repository contains two supported entrypoints:

- `fantasy_football_multi_league.py` for stdio MCP clients;
- `fastmcp_server.py` for FastMCP HTTP deployment.

See [`INSTALLATION.md`](INSTALLATION.md) for installation troubleshooting and
[`docs/README.md`](docs/README.md) for the documentation index.

## License

MIT License. See [`LICENSE`](LICENSE).
