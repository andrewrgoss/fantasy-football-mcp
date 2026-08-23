# Installation and local operation

This project can run entirely from local exports. Yahoo OAuth is optional and
is needed only for live league tools.

## Requirements

- Python 3.9 or newer
- Git
- An MCP-capable client for tool use (optional)

## Install

```bash
git clone https://github.com/andrewrgoss/fantasy-football-mcp.git
cd fantasy-football-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp config/league_profile.example.json config/league_profile.local.json
```

Keep `.env`, the local league profile, exports, and generated analysis private.
They are ignored by Git when stored in the documented locations.

## Offline auction setup

Edit `config/league_profile.local.json` with your scoring, roster, budget, and
keeper rules. Put private source files under `data/local/`, or reference files
elsewhere on your machine with absolute paths.

The offline workflow does not require API approval. It supports:

- Yahoo projections and pre-draft market values;
- historical auction results;
- FFA projections and custom rankings;
- downloaded FantasyPros projections and rankings; and
- optional team-context data.

See [Offline auction preparation](docs/OFFLINE_AUCTION_PREP.md) for schemas,
weighting, an MCP request, and sanitized examples.

## Optional live Yahoo access

Yahoo developer credentials do not automatically include Fantasy Sports API
access. Complete the separate read-only access application before expecting
live league calls to work.

The full application language and authentication steps are in
[Yahoo API setup](docs/YAHOO_API_SETUP.md).

After approval, add credentials to `.env` and run:

```bash
.venv/bin/python utils/setup_yahoo_auth.py
```

Refresh an existing grant with:

```bash
.venv/bin/python utils/refresh_yahoo_token.py
```

If Yahoo access is unavailable, generate local exports with the companion
[Yahoo scraper](https://github.com/andrewrgoss/yahoo-fantasy-fball-scraper) and
[auction optimizer](https://github.com/andrewrgoss/yahoo-fantasy-auction-optimizer).

## Start the MCP server

For a stdio client:

```bash
.venv/bin/python fantasy_football_multi_league.py
```

Example client configuration:

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

For the HTTP/FastMCP entrypoint:

```bash
.venv/bin/python fastmcp_server.py
```

Restart the MCP client after changing credentials, `.env`, or server code.

## Optional data integrations

- [FantasyPros data](docs/FANTASYPROS_DATA.md): downloaded CSVs are recommended
  because the free API response is too limited for a complete draft board.
- [Reddit API setup](docs/REDDIT_API_SETUP.md): explicit Reddit approval is
  required; the project operates without sentiment data when unavailable.
- Sleeper: public endpoints require no local credentials.

## Verify the installation

Run the focused offline and privacy tests:

```bash
.venv/bin/python -m pytest -q \
  tests/unit/test_auction_prep.py \
  tests/unit/test_reddit_privacy.py
```

Run the complete suite:

```bash
.venv/bin/python -m pytest
```

## Troubleshooting

### `additional_authorization_required`

The OAuth client is valid but Yahoo has not provisioned it for Fantasy Sports.
Refreshing or recreating the token will not add that entitlement. See
[Yahoo API setup](docs/YAHOO_API_SETUP.md).

### MCP tools do not appear

1. Confirm both configured paths are absolute.
2. Run the stdio command directly and resolve import errors.
3. Restart the MCP client.
4. Confirm the client is loading the configuration file you edited.

### Offline source columns are blank

The value generator preserves source-specific columns only when the matching
input provides that field and the player can be joined reliably. Check the CSV
schema, player name, and position. The tool reports source coverage instead of
inventing values.

### Authentication data is exposed

Revoke the affected credential immediately, remove it from Git history if it
was committed, and issue a replacement. Never paste secrets into issues,
documentation, or logs.

## Documentation

See [docs/README.md](docs/README.md) for the complete documentation index.
