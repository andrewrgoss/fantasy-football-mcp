# Offline Auction-Draft Preparation

The offline auction tools work without Yahoo or Reddit API approval. They read
private local files in place and return league-specific values through MCP.

## Privacy boundary

Use the repository as code, not as storage for a real league. Keep the following
in `data/local/` or another private directory:

- completed league profiles;
- Yahoo projections and market exports;
- historical draft results;
- keeper spreadsheets;
- FFA and FantasyPros downloads;
- generated auction boards; and
- final strategy documents.

`data/local/` and `config/*.local.json` are ignored. The files under
[`data/examples`](../data/examples) use public team context or invented data.
They document file shape and are not a usable set of NFL projections.

## 1. Create a private league profile

```bash
cp config/league_profile.example.json config/league_profile.local.json
```

Edit the local copy with the real season, team count, salary-cap budget,
scoring, starting slots, bench, IR, and relevant keeper/playoff settings. The
server uses `config/league_profile.local.json` by default or reads the path from:

```env
FANTASY_LEAGUE_PROFILE=/private/path/league_profile.json
```

The public template intentionally contains an invented league ID/name and
ordinary example settings.

## 2. Assemble projection and market inputs

The primary Yahoo projection format is illustrated by
[`yahoo_player_projections.example.csv`](../data/examples/yahoo_player_projections.example.csv).
When raw passing, rushing, and receiving columns are present, the loader
recalculates fantasy points using the local profile instead of trusting a
source's default scoring.

Yahoo pre-draft market values use the shape in
[`yahoo_market_values.example.csv`](../data/examples/yahoo_market_values.example.csv).
These prices calibrate the projection-derived baseline; they are not a
projection source.

The companion scraper can generate compatible exports:

- [Yahoo Fantasy Football Scraper](https://github.com/andrewrgoss/yahoo-fantasy-fball-scraper)
- [Yahoo Fantasy Auction Optimizer](https://github.com/andrewrgoss/yahoo-fantasy-auction-optimizer)

Do not put a Yahoo username/password in command history or source control. Use
the scraper's current local authentication method and keep its outputs private.

## 3. Add optional projection sources

FFA detailed projections and custom rankings are separate inputs. The default
FFA bucket blends their scoring-aware projection points 50/50. Example shapes:

- [`ffa_detailed_projections.example.csv`](../data/examples/ffa_detailed_projections.example.csv)
- [`ffa_custom_rankings.example.csv`](../data/examples/ffa_custom_rankings.example.csv)

The public repository does not distribute FFA data. Users must obtain and use
their own files under the applicable terms.

FantasyPros local exports are preferred over the limited free API:

- [`fantasypros_projections.example.csv`](../data/examples/fantasypros_projections.example.csv)
- [`fantasypros_qb_projections.example.csv`](../data/examples/fantasypros_qb_projections.example.csv)
- [`fantasypros_rankings.example.csv`](../data/examples/fantasypros_rankings.example.csv)

See [FANTASYPROS_DATA.md](FANTASYPROS_DATA.md) for the limitations and private
environment variables.

When FFA, Yahoo, and FantasyPros are all available, the default projection
weights are:

| Source | Default |
| --- | ---: |
| FFA | 40% |
| Yahoo | 30% |
| FantasyPros | 30% |

The weights are configurable. At the player level, an absent source is omitted
and the remaining weights are renormalized. Missing data is never interpreted
as a zero projection.

## 4. Add historical auction results

Use one CSV or a directory of CSVs matching
[`historical_auction_results.example.csv`](../data/examples/historical_auction_results.example.csv).

Historical prices are ranked independently within each season and position.
The current projected RB13 is calibrated against historical RB13 salaries, for
example. Player-name price history remains available only for diagnostics; it
does not set current value because careers, depth charts, and roles change.

The summary tool also reports position spend shares and optional manager-level
patterns. If manager names are included in private source files, do not publish
the raw or summarized identity-level output.

## 5. Add optional team context

[`2026_team_environment.json`](../data/examples/2026_team_environment.json)
contains a public snapshot of offensive-line rankings and Vegas win totals. It
is safe to commit because it has no league identity, credentials, or proprietary
player projections.

The default model treats strength of schedule, offensive line, and team
environment as separate bounded inputs:

- FFA SOS: maximum 2.5%; rank 1 is easiest and 32 hardest.
- Offensive line: maximum 2.5%; rank 1 is best and 32 worst.
- Vegas win total: maximum 2.5%; centered on a neutral expectation.

Line and team adjustments apply to QB, RB, WR, and TE. RB team-environment
exposure is role-sensitive: receiving backs receive partial protection from a
poor real-life team outlook, while low-reception backs receive more of the
negative-game-script penalty. Defense is excluded.

These inputs are priors, not guarantees. Update the public snapshot when source
rankings or betting lines change, and preserve the source URL/as-of metadata.

## 6. Call the MCP tool

Example arguments for `ff_project_auction_values`:

```text
profile_path: /private/path/league_profile.json
projection_path: /private/path/yahoo_player_projections.csv
market_values_path: /private/path/yahoo_market_values.csv
historical_path: /private/path/historical_results/
ffa_projection_path: /private/path/ffa_detailed_projections.csv
ffa_custom_rankings_path: /private/path/ffa_custom_rankings.csv
fantasypros_projection_path: /private/path/fantasypros_flx.csv
fantasypros_qb_projection_path: /private/path/fantasypros_qb.csv
fantasypros_rankings_path: /private/path/fantasypros_rankings.csv
team_environment_path: /path/to/repo/data/examples/2026_team_environment.json
ffa_weight: 0.40
yahoo_weight: 0.30
fantasypros_weight: 0.30
ffa_custom_weight: 0.50
market_weight: 0.25
historical_weight: 0.15
max_sos_adjustment: 0.025
max_offensive_line_adjustment: 0.025
max_team_environment_adjustment: 0.025
limit: 200
```

Only `projection_path` and a valid league profile are required. Add the other
layers as available.

The output exposes source-specific points/ranks, replacement points, VORP,
market and historical calibration, context inputs/adjustments, suggested value,
and data confidence. Empty Reddit columns are omitted unless an approved
sentiment map is explicitly supplied.

## 7. Apply source-quality checks

The implementation:

- normalizes documented player suffix/nickname variants before joins;
- rejects zero-projection rows;
- honors inactive Yahoo statuses;
- prevents an old player salary from setting a current price;
- caps stale fringe players at the $1 nomination floor when current draft
  signals do not support them; and
- leaves truly unavailable source fields blank rather than inventing values.

Always check injuries, transactions, depth charts, suspensions, and role changes
immediately before the draft. A deterministic model cannot know about a late
news event that is absent from its inputs.

## 8. Produce a private strategy document

The CSV is only the value board. Use
[STRATEGY_DOCUMENT_WORKFLOW.md](STRATEGY_DOCUMENT_WORKFLOW.md) to combine it
with keeper rules, projected keeper choices, tier breaks, budget allocations,
and live-draft constraints. The final document should remain private.

## Pre-publication privacy checks

Review both tracked changes and ignored files:

```bash
git status --short --ignored
git diff --check
git grep -n -i -E 'league name|team name|league id|email address'
git check-ignore -v .env config/league_profile.local.json data/local/
```

Also inspect `git diff --cached` immediately before committing. Never print or
paste credential values while performing the audit.
