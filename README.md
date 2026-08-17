# Fantasy Football MCP Server

A comprehensive Model Context Protocol (MCP) server for Yahoo Fantasy Football that provides intelligent lineup optimization, draft assistance, and league management through AI-powered tools.

## 🚀 Features

### Core Capabilities
- **Multi-League Support** – Automatically discovers and manages all Yahoo Fantasy Football leagues associated with your account
- **🆕 Player Enhancement Layer** – Intelligent projection adjustments with bye week detection, recent performance stats, and breakout/declining player flags
- **Intelligent Lineup Optimization** – Advanced algorithms considering matchups, expert projections, and position-normalized value
- **Draft Assistant** – Real-time draft recommendations with strategy-based analysis and VORP calculations
- **Comprehensive Analytics** – Reddit sentiment analysis, team comparisons, and performance metrics
- **Multiple Deployment Options** – FastMCP, traditional MCP, Docker, and cloud deployment support

### Advanced Analytics
- **Position Normalization** – Smart FLEX decisions accounting for different position baselines
- **Multi-Source Projections** – Combines Yahoo and Sleeper expert rankings with matchup analysis
- **Strategy-Based Optimization** – Conservative, aggressive, and balanced approaches
- **Volatility Scoring** – Floor vs ceiling analysis for consistent or boom-bust plays
- **Live Draft Support** – Real-time recommendations during active drafts

## 🆕 Player Enhancement Layer

The enhancement layer enriches player data with real-world context to fix stale projections and prevent common mistakes:

### Key Features

✅ **Bye Week Detection** – Automatically zeros projections and displays "BYE WEEK - DO NOT START" for players on bye, preventing accidental starts

✅ **Recent Performance Stats** – Fetches last 1-3 weeks of actual performance from Sleeper API and displays trends (L3W avg: X.X pts/game)

✅ **Performance Flags** – Intelligent alerts including:
- `BREAKOUT_CANDIDATE` – Recent performance > 150% of projection
- `TRENDING_UP` – Recent performance exceeds projection
- `DECLINING_ROLE` – Recent performance < 70% of projection
- `HIGH_CEILING` – Explosive upside potential
- `CONSISTENT` – Reliable, steady performance

✅ **Adjusted Projections** – Blends recent reality with stale projections for more accurate start/sit decisions (60/40 or 70/30 weighting based on confidence)

### Example

**Before Enhancement:**
```json
{
  "name": "Rico Dowdle",
  "sleeper_projection": 4.0,
  "recommendation": "Bench"
}
```

**After Enhancement:**
```json
{
  "name": "Rico Dowdle",
  "sleeper_projection": 4.0,
  "adjusted_projection": 14.8,
  "performance_flags": ["BREAKOUT_CANDIDATE", "TRENDING_UP"],
  "enhancement_context": "Recent breakout: averaging 18.5 pts over last 3 weeks",
  "recommendation": "Strong Start"
}
```

The enhancement layer is **non-breaking** and automatically applies to:
- `ff_get_roster` (with `include_external_data=True`)
- `ff_get_waiver_wire` (with `include_external_data=True`)
- `ff_get_players` (with `include_external_data=True`)
- `ff_build_lineup` (automatic)

## 🛠️ Available MCP Tools

### League & Team Management
- `ff_get_leagues` – List all leagues for your authenticated Yahoo account
- `ff_get_league_info` – Retrieve detailed league metadata and team information
- `ff_get_standings` – View current league standings with wins, losses, and points
- `ff_get_roster` – Inspect detailed roster information for any team
- `ff_get_matchup` – Analyze weekly matchup details and projections
- `ff_compare_teams` – Side-by-side team roster comparisons for trades/analysis
- `ff_build_lineup` – Generate optimal lineups using advanced optimization algorithms

### Player Discovery & Waiver Wire
- `ff_get_players` – Browse available free agents with ownership percentages
- `ff_get_waiver_wire` – Smart waiver wire targets with expert analysis (configurable count)
- `ff_get_draft_rankings` – Access Yahoo's pre-draft rankings and ADP data

### Draft Assistant Tools
- `ff_get_draft_recommendation` – AI-powered draft pick suggestions with strategy analysis
- `ff_analyze_draft_state` – Real-time roster needs and positional analysis during drafts
- `ff_get_draft_results` – Post-draft analysis with grades and team summaries

### Offline Auction Preparation
- `ff_get_auction_profile` – Validate a private local league profile
- `ff_project_auction_values` – Combine scoring-aware projections, current market prices,
  matched historical prices, optional FantasyPros data, and optional sentiment
- `ff_summarize_historical_auction` – Summarize exported auction prices by season, position, and manager
- `ff_evaluate_keeper` – Compare projected auction value with keeper cost and risk

### Advanced Analytics
- `ff_analyze_reddit_sentiment` – Social media sentiment analysis for player buzz and injury updates
- `ff_get_api_status` – Monitor cache performance and Yahoo API rate limiting
- `ff_clear_cache` – Clear cached responses for fresh data (with pattern support)
- `ff_refresh_token` – Automatically refresh Yahoo OAuth tokens

## 📦 Installation

### Quick Start
```bash
git clone https://github.com/derekrbreese/fantasy-football-mcp-public.git
cd fantasy-football-mcp-public
pip install -r requirements.txt
```

### Yahoo API Setup
Yahoo currently separates Fantasy Sports API access from the legacy Yahoo Developer
application form. Start with the [Yahoo Fantasy Sports API access application](https://sports.yahoo.com/developer/access/).
Yahoo states that access is read-only by default and reviews applications before
provisioning access.

When completing the access application, describe this as a personal, single-user,
local tool for read-only analysis of your own Yahoo Fantasy Football league,
including roster, standings, matchup, player, and auction-draft data. Set the
expected users to `1`, request Fantasy Sports read access, and state that the app
does not redistribute or monetize Yahoo data.

#### Fantasy Sports API Read-Only Access Application

Yahoo reviews each Fantasy Sports API application. Complete every required field
with accurate personal or business information; do not use placeholder contact
details. The following values are appropriate for this local, single-league setup:

- **Name**: Your legal name.
- **Business Title**: Your actual role, such as `Independent Software Developer`.
- **Email Address**: An address you actively monitor for Yahoo follow-up.
- **Phone Number**: Your reachable phone number, including country code.
- **Business Name & Address**: Your actual business name and mailing address. If you
  are applying as an individual, identify yourself as an independent developer and
  provide your actual address.
- **Consumer-Facing Product or App Name**: `Fantasy Football MCP`.
- **Brief Company Description**: `Independent developer building a private, local fantasy football analysis tool for personal use.`
- **Website URL or App Store Details**: `https://github.com/andrewrgoss/fantasy-football-mcp`.
- **Describe Your Intended Use Case**:

  > Fantasy Football MCP is a local, single-user MCP server for read-only analysis of my own private Yahoo Fantasy Football league. It will retrieve league settings, roster data, standings, matchups, player availability, draft results, and auction-draft information to help me prepare for and manage my annual fantasy football draft. The intended user base is one person: the Yahoo account owner and manager of this league. The tool is not a public multi-user service, will not write transactions or settings back to Yahoo, will not resell or redistribute Yahoo data, and is not intended for commercial use.

- **Expected Users**: Select the smallest available range containing `1` user.
- **Client ID**: Enter the **Client ID / Consumer Key** from the Yahoo Developer
  application, if you already created one. This is not the Yahoo App ID. If you do
  not yet have a YDN application, leave this field blank as Yahoo permits.
- **Additional Notes**:

  > Requesting read-only Fantasy Sports API access only. This is a personal, non-commercial, single-league use case with one intended user. I do not need write access, transaction automation, or access to other users' leagues. The application will keep credentials private and comply with Yahoo's API terms and attribution requirements.

Do not request write access; Yahoo currently provides Fantasy Sports API access as
read-only. After approval, use the Client ID and Client Secret in the local `.env`
file as `YAHOO_CLIENT_ID` and `YAHOO_CLIENT_SECRET`.

The legacy [Yahoo Developer application form](https://developer.yahoo.com/apps/) may
still be used to obtain an App ID/Client ID, but its current permissions may show
only OpenID Connect and **TW Auction**. **TW Auction is not Yahoo Fantasy Football**;
do not select it as a substitute for Fantasy Sports access. If the form does not
offer a Fantasy Sports permission, that is expected—use the separate access
application above.

If you create the legacy application, use these values:

- **Application Name**: `Fantasy Football MCP`
- **Description**: `Personal, single-user MCP server for read-only Yahoo Fantasy Football league, roster, standings, matchup, and auction-draft analysis.`
- **Homepage URL**: `https://github.com/andrewrgoss/fantasy-football-mcp`
- **Redirect URI(s)**: `https://localhost:8080` (required by the current form; use HTTPS and omit the trailing slash). The bundled YFPY flow still requests Yahoo's `oob` verifier during local authentication.
- **OAuth Client Type**: `Confidential Client`, because the current server uses a Client Secret during the token exchange.
- **API Permissions**: Do not select `TW Auction`.
- **OpenID Connect Permissions**: None required.

After Yahoo grants Fantasy Sports API access, note the Client ID (Consumer Key) and
Client Secret (Consumer Secret), then place them in the local `.env` file. The
Yahoo **App ID** is used only on Yahoo's access-application form; this server does
not consume it, so do not add a `YAHOO_APP_ID` variable. Do not commit `.env` or
any generated token files.

## ⚙️ Configuration

Create a `.env` file with your API credentials:

```env
# Yahoo API Credentials (Required)
YAHOO_CLIENT_ID=your_consumer_key_here
YAHOO_CLIENT_SECRET=your_consumer_secret_here
YAHOO_ACCESS_TOKEN=your_access_token
YAHOO_REFRESH_TOKEN=your_refresh_token
YAHOO_GUID=your_yahoo_guid

# Reddit API Credentials (Optional - for sentiment analysis; approval required)
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USERNAME=your_reddit_username
```

**Note**: Reddit sentiment analysis is optional. Reddit requires explicit approval
before this external application may use the Data API. Without approved Reddit
credentials, the server still supports Yahoo tools but Reddit sentiment features
remain unavailable. See the [Reddit API Setup Guide](docs/REDDIT_API_SETUP.md)
for the complete request and setup procedure.

**Security**: Keep `.env`, `.yahoo_token.json`, `.py.json`, and
`config/*.local.json` local. These files contain OAuth credentials, tokens, or
private league settings and are ignored by Git.

### Reddit API Setup

Reddit's current [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy)
requires explicit approval before an external script, PRAW client, or MCP server
uses Reddit's Data API. This project is a personal, single-user local integration,
not a Devvit app or an academic research project. Review Reddit's [Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki)
and submit the [Data API access request](https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164)
before configuring Reddit credentials.

For the application, describe the intended use as read-only analysis of public
fantasy-football discussions for one user. The initial scope is limited to
`r/fantasyfootball` and `r/DynastyFF`; additional communities should only be
requested after approval. State that there are no other App Users, and that the
app will not post, vote, message, moderate, resell, redistribute, profile
Redditors, infer sensitive characteristics, match users to off-platform
identities, or use Reddit content for model training. The local analyzer returns
aggregate signals only, keeps no author identifiers, filters deleted content,
and honors OAuth, rate limits, and Reddit's applicable terms.

Reddit's current policy requires app registration and a developer profile. Follow
the registration instructions Reddit provides for the approved request; do not
assume that the legacy `/prefs/apps` script form alone grants access. If the
page loops, redirects to Devvit, or refuses to create the app, stop retrying and
wait for Reddit's access-request review; do not substitute an unapproved client.
After approval and registration, populate `REDDIT_CLIENT_ID`,
`REDDIT_CLIENT_SECRET`, and `REDDIT_USERNAME` in `.env`. See the
[Reddit data-handling statement](docs/REDDIT_DATA_HANDLING.md) for the local
retention and deletion rules implemented by this integration.

#### Copy-ready Reddit access-request form answers

Use the following answers in Reddit's **Data Access Request** form. Replace the
bracketed values with your own contact and account details.

- **What do you need assistance with?** `Data Access Request`
- **Your email address:** `[your email address]`
- **Which role best describes your reason for requesting API access?** `I'm a developer`
- **What is your inquiry?** `I'm a developer and want to build a Reddit App that does not work in the Devvit ecosystem.`
- **Reddit account name:** `[your Reddit username]` (without `u/`)
- **What benefit/purpose will the bot/app have for Redditors?**

  > This is a private, single-user decision-support tool for one Redditor. It
  > summarizes public fantasy-football discussion so I can make better personal
  > Yahoo fantasy football draft, roster, matchup, and waiver decisions. It is
  > not academic research, has no other App Users, and does not act on behalf of
  > other Redditors or change anything on Reddit.

- **Detailed description of what the Bot/App will be doing:** Copy and paste the
  following exactly:

  ```text
  Fantasy Football MCP is a personal, single-user, read-only local MCP server, not academic research or a public bot. After Reddit approves access, it will use one registered OAuth client through PRAW to retrieve recent public posts and comments matching requested fantasy-football player names, initially limited to r/fantasyfootball and r/DynastyFF. It will calculate aggregate sentiment and engagement locally for my own Yahoo fantasy football draft, roster, matchup, and waiver analysis. It has no other App Users and will not post, vote, comment, message, moderate, follow, join communities, profile Redditors, infer sensitive characteristics, match users to off-platform identities, or otherwise change Reddit. It will not sell, redistribute, publish raw content, or use Reddit content for model training. No author identifiers will be retained, deleted content will be filtered, raw content will be held only in memory for the current analysis, and the client will honor OAuth, rate limits, content-removal requirements, and applicable Reddit terms.
  ```

- **What is missing from Devvit that prevents building on that platform?** Copy and
  paste the following exactly:

  ```text
  Devvit is designed for apps hosted in Reddit communities. This use case is a private, local MCP server that combines read-only Reddit data with Yahoo Fantasy Sports data and is invoked from my local assistant. It requires a local Python/PRAW process and OAuth credentials, does not need a Reddit-hosted user interface or subreddit installation, and must keep the workflow and temporary data local. Devvit does not support this cross-service, personal, local-only MCP workflow.
  ```

- **Provide a link to source code or platform:** Use the public URL of the fork
  that contains this client. The currently cloned public source is
  `https://github.com/andrewrgoss/fantasy-football-mcp`.
- **What subreddits do you intend to use the bot/app in?**
  `r/fantasyfootball` and `r/DynastyFF` initially. Additional communities will
  only be requested after approval.
- **If applicable, what username will you be operating this Bot/App under?**
  `[your Reddit username]` (the same account named above).
- **Attachments:** None required.

### Offline Auction-Draft Preparation

The server includes league-agnostic tools for preparing an auction draft before
live Yahoo or Reddit access is available. They use a private local league profile
and exported CSV files; no league-specific settings belong in the public repo.

Start from the public template and keep the completed profile local:

```bash
cp config/league_profile.example.json config/league_profile.local.json
```

`config/league_profile.local.json` is ignored by Git. It defines the season,
team count, auction budget, scoring rules, starting slots, bench, injured reserve,
and optional playoff settings. The server also accepts a custom profile path or
the `FANTASY_LEAGUE_PROFILE` environment variable.

The offline MCP tools are:

- `ff_get_auction_profile` validates the local profile and returns a safe summary.
- `ff_project_auction_values` recalculates projections from league scoring, estimates
  replacement levels from roster demand and flex slots, and blends optional current
  market prices, matched historical prices, and sentiment signals into bounded
  suggested values.
- `ff_summarize_historical_auction` summarizes exported auction prices by season,
  position, and manager so league-specific spending trends can be reviewed.
- `ff_evaluate_keeper` compares a player's projected auction value with keeper cost,
  optional risk, surplus, and return-on-investment thresholds.

Projection exports can use raw stat columns such as `PASSING_YDS`, `RUSHING_YDS`,
`RECEPTIONS`, and `RECEIVING_YDS`; the scoring profile is applied instead of
assuming standard, half-PPR, or full-PPR rules. The scraper-compatible market and
historical formats are documented in
[`src/auction_prep.py`](src/auction_prep.py) and exercised by the unit tests.

When historical results are supplied, the tool uses a matched player's prior
average salary as a conservative market signal. The separate historical-summary
tool exposes season, position, and manager trends for broader inflation and manager analysis;
it does not assume that past prices automatically equal the current market.
Pass either one historical CSV or a directory containing multiple season exports;
the files are read in place and are never copied into this repository.

Sentiment is an optional, bounded adjustment rather than a replacement for player
projections. When Reddit access is approved, an integration can provide each
player's sentiment score, confidence, and engagement; the auction tool keeps the
adjustment confidence-aware and capped.

### FantasyPros Supplemental Data

The auction workflow can optionally blend FantasyPros projections and consensus
rankings into local projections. FantasyPros documents JSON-over-HTTPS endpoints
for rankings, projections, player metadata, news, and injuries in its [official API
documentation](https://www.fantasypros.com/api-data/).

Request a key through FantasyPros, then add it only to the local `.env` file:

```env
FANTASYPROS_API_KEY=your_fantasypros_api_key
FANTASYPROS_API_BASE_URL=https://api.fantasypros.com/public/v2/json
```

FantasyPros is disabled by default. Set `use_fantasypros=true` when calling
`ff_project_auction_values`; the tool derives `PPR`, `HALF`, or `STD` from the
profile unless `fantasypros_scoring` is supplied. It can request projections and
consensus rankings for the profile season, blend projected points using
`fantasypros_weight`, and report the source rank/ADP alongside each value.

Do not scrape FantasyPros pages or commit the API key. Follow the license and
plan that applies to your use: FantasyPros describes free access for building and
testing, personal production access for qualifying personal/non-commercial use,
and separate commercial access for redistribution, historical/bulk data, or
commercial applications.

#### Requesting a FantasyPros API key

The FantasyPros request form asks you to review its non-commercial terms and
describe your intended use. For this project, the following is a copy-ready
answer for the **How do you plan to use the API?** field:

> Fantasy Football MCP is a personal, non-commercial, single-user local tool
> for draft preparation. I will use FantasyPros projections, rankings, ADP,
> news, and injury data with my private league settings and auction history to
> estimate values and evaluate keepers. I will not sell, redistribute, publish
> raw data, expose it to others, build a competing service, or use player
> images. The key stays private; requests are cached and derivative work will
> credit FantasyPros.

The key is for personal, non-commercial use only. Keep it in local environment
configuration, never commit it, and do not use FantasyPros player image URLs
without the required SportRadar permission. Review the complete
[FantasyPros API terms of use](https://api.fantasypros.com/public/v2/terms-of-use)
before submitting the request; the terms also define limits on polling,
redistribution, historical data, and derivative work. The [FantasyPros API
request page](https://www.fantasypros.com/api-data/) describes the available
API tiers and request process.

#### Try the offline tools without external APIs

After creating `config/league_profile.local.json`, reconnect your MCP client so
the four offline tools appear. `ff_get_auction_profile` and
`ff_evaluate_keeper` need no external data. `ff_project_auction_values` accepts
local projection, market-value, and historical-auction CSV paths; its optional
`sentiment` object can be used to supply an already-approved analysis signal.
`ff_summarize_historical_auction` needs only a historical-auction CSV.

The Yahoo league, roster, draft, and Reddit tools remain unavailable until their
respective credentials and approvals are configured.

### Initial Authentication

**First-time setup:**
```bash
cd utils
python setup_yahoo_auth.py
```

**Re-authentication (if tokens expired):**
```bash
cd utils
python reauth_yahoo.py
```

**Token refresh (when access token expires):**
```bash
cd utils
python refresh_yahoo_token.py
```

The authentication scripts will:
- Open your browser for Yahoo OAuth authorization
- Automatically update your `.env` file (preserving existing variable line positions)
- Automatically update MCP config files (Claude Desktop, Cursor, Antigravity) if they exist
- Display confirmation messages

**Important**: After authentication or token refresh, restart your MCP client to use the new tokens.

## 🚀 Deployment Options

### Local Development (FastMCP)
```bash
python fastmcp_server.py
```
Connect via HTTP transport at `http://localhost:8000`

### Claude Code Integration (Stdio)
```bash
python fantasy_football_multi_league.py
```

### Docker Deployment
```bash
docker build -t fantasy-football-mcp .
docker run -p 8080:8080 --env-file .env fantasy-football-mcp
```

### Cloud Deployment (Render/Railway/etc.)
The server includes multiple compatibility layers for various cloud platforms:
- `render_server.py` - Render.com deployment
- `simple_mcp_server.py` - Generic HTTP/WebSocket server
- `fastmcp_server.py` - FastMCP cloud deployments

## 🧪 Testing

```bash
# Run full test suite
pytest

# Test OAuth authentication
python tests/test_oauth.py

# Test MCP connection
python tests/test_mcp_client.py
```

## 📁 Project Structure

```
fantasy-football-mcp-public/
├── fastmcp_server.py              # FastMCP HTTP server implementation
├── fantasy_football_multi_league.py  # Main MCP stdio server
├── lineup_optimizer.py            # Advanced lineup optimization engine
├── matchup_analyzer.py           # Defensive matchup analysis
├── position_normalizer.py        # FLEX position value calculations
├── config/
│   ├── league_profile.example.json  # Public profile template
│   └── league_profile.local.json    # Ignored personal profile (create locally)
├── src/
│   ├── agents/                   # Specialized analysis agents
│   ├── models/                   # Data models for players, lineups, drafts
│   ├── auction_prep.py            # Offline auction and keeper analysis
│   ├── strategies/              # Draft and lineup strategies
│   ├── services/                # Player enhancement and external integrations
│   └── utils/                   # Utility functions and configurations
├── tests/                       # Comprehensive test suite
├── utils/                       # Authentication and token management
└── requirements.txt             # Python dependencies
```

## 🔧 Advanced Configuration

### Strategy Weights (Balanced Default)
```python
{
    "yahoo": 0.40,     # Yahoo expert projections
    "sleeper": 0.40,   # Sleeper expert rankings
    "matchup": 0.10,   # Defensive matchup analysis
    "trending": 0.05,  # Player trending data
    "momentum": 0.05   # Recent performance
}
```

### Draft Strategies
- **Conservative**: Prioritize proven players, minimize risk
- **Aggressive**: Target high-upside breakout candidates
- **Balanced**: Optimal mix of safety and ceiling potential

### Position Scoring Baselines
- RB: ~11 points (standard scoring)
- WR: ~10 points (standard scoring)
- TE: ~7 points (standard scoring)
- FLEX calculations include position scarcity adjustments

## 📊 Performance Metrics

The optimization engine targets:
- **85%+** accuracy on start/sit decisions
- **+2.0** points per optimal decision on average
- **90%+** lineup efficiency vs. manual selection
- **Position-normalized FLEX** decisions to avoid TE traps

## 🔍 Troubleshooting

### Common Issues

**Authentication Errors**
```bash
# Refresh expired tokens (expire hourly)
cd utils
python refresh_yahoo_token.py

# Full re-authentication if refresh fails
cd utils
python reauth_yahoo.py

# Or first-time setup
cd utils
python setup_yahoo_auth.py
```

**Note**: All authentication scripts automatically update your `.env` file and MCP config files. After running any authentication script, restart your MCP client (Claude Desktop, Cursor, etc.) to use the new tokens.

**Only One League Showing**
- Verify `YAHOO_GUID` matches your Yahoo account
- Ensure leagues are active for current season
- Check team ownership detection in logs

**Rate Limiting**
- Yahoo allows 1000 requests/hour
- Server implements 900/hour safety limit
- Use `ff_get_api_status` to monitor usage
- Clear cache with `ff_clear_cache` if needed

**Stale Data**
- Cache TTLs: Leagues (1hr), Standings (5min), Players (15min)
- Force refresh with `ff_clear_cache` tool
- Check last update times in `ff_get_api_status`

## 🤝 Contributing

This is the public version of the Fantasy Football MCP Server. For contributing:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Yahoo Fantasy Sports API for comprehensive league data
- Sleeper API for expert rankings and defensive analysis
- Reddit API for player sentiment analysis
- Model Context Protocol (MCP) framework

---

**Note**: This server requires active Yahoo Fantasy Football leagues and valid API credentials. Ensure you have proper authorization before accessing league data.
