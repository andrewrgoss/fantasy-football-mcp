# Yahoo Fantasy Sports API Setup

Yahoo Fantasy Sports API access is read-only and separately reviewed. Creating
a Yahoo Developer Network application and completing OAuth does not by itself
provision Fantasy Sports access. An application can hold valid OAuth tokens and
still receive:

```text
401 additional_authorization_required
```

That response is a provisioning issue, not an expired-token issue. Recreating
tokens will not fix it.

## 1. Create the Yahoo Developer application

Open the [Yahoo Developer application form](https://developer.yahoo.com/apps/)
and use values appropriate for a local application:

- **Application Name:** `Fantasy Football MCP`
- **Description:** `Personal, single-user MCP server for read-only fantasy football league, roster, standings, matchup, and auction-draft analysis.`
- **Homepage URL:** the public URL of your fork
- **Redirect URI:** `https://localhost:8080`
- **OAuth Client Type:** `Confidential Client`
- **API Permissions:** do not select `TW Auction`; it is unrelated to Yahoo
  Fantasy Football
- **OpenID Connect Permissions:** none required by this server

The current form requires a redirect URI even though the bundled local verifier
flow requests Yahoo's out-of-band authorization code.

Save the generated **Client ID / Consumer Key** and **Client Secret / Consumer
Secret** in the ignored `.env` file:

```env
YAHOO_CLIENT_ID=your_consumer_key
YAHOO_CLIENT_SECRET=your_consumer_secret
```

The Yahoo **App ID** is not consumed by this server. It may be requested on the
separate Fantasy Sports access form, but it does not need a `.env` variable.

## 2. Apply for Fantasy Sports API access

Submit the [Yahoo Fantasy Sports API access application](https://sports.yahoo.com/developer/access/).
Complete every identity/contact field truthfully. Suggested product fields are:

- **Consumer-Facing Product or App Name:** `Fantasy Football MCP`
- **Brief Company Description:** `Independent developer building a private, local fantasy football analysis tool for personal use.`
- **Website URL or App Store Details:** the public URL of your fork
- **Expected Users:** the smallest range containing one user
- **Client ID:** the Client ID / Consumer Key from the developer application;
  this is not the App ID

Copy-ready intended-use response:

```text
Fantasy Football MCP is a local, single-user MCP server for read-only analysis of my own private Yahoo Fantasy Football league. It will retrieve league settings, roster data, standings, matchups, player availability, draft results, and auction-draft information to help me prepare for and manage my annual fantasy football draft. The intended user base is one person: the Yahoo account owner and manager of the league. The tool is not a public multi-user service, will not write transactions or settings back to Yahoo, will not resell or redistribute Yahoo data, and is not intended for commercial use.
```

Copy-ready additional notes:

```text
Requesting read-only Fantasy Sports API access only. This is a personal, non-commercial, single-league use case with one intended user. I do not need write access, transaction automation, or access to other users' leagues. The application will keep credentials private and comply with Yahoo's API terms and attribution requirements.
```

Do not request write access. Do not use `TW Auction` as a substitute for Fantasy
Sports permission.

## 3. Complete local OAuth

After placing the Client ID and Client Secret in `.env`, run:

```bash
.venv/bin/python utils/setup_yahoo_auth.py
```

The script opens Yahoo authorization, exchanges the verification code, saves
tokens to the ignored `.env`, obtains the user GUID when available, and performs
a Fantasy Sports provisioning preflight.

For an expired access token with a valid refresh token:

```bash
.venv/bin/python utils/refresh_yahoo_token.py
```

The MCP also exposes `ff_refresh_token`. Restart the MCP client after changing
authentication state.

## Provisioning outcomes

- `200` from the Fantasy Sports preflight: the application is provisioned.
- `401 token_rejected`: refresh or repeat OAuth.
- `401 additional_authorization_required`: wait for Yahoo approval or contact
  Yahoo about the existing access request. Do not loop token setup.

Yahoo does not publish a guaranteed review time. The offline workflow remains
usable while an application is pending or unapproved.

## Offline Yahoo export fallback

This repository accepts local CSVs for season projections, pre-draft auction
values, and historical draft results. Two public companion projects can produce
or consume those exports:

- [Yahoo Fantasy Football Scraper](https://github.com/andrewrgoss/yahoo-fantasy-fball-scraper)
- [Yahoo Fantasy Auction Optimizer](https://github.com/andrewrgoss/yahoo-fantasy-auction-optimizer)

Keep usernames, passwords, browser state, league IDs, manager/team names, and
scraped files outside the public repository. Prefer an ignored `data/local/`
directory or another private folder.

## Credential safety

Never commit:

- `.env`;
- `.yahoo_token.json`;
- `.py.json`;
- OAuth codes or access/refresh tokens;
- Yahoo login credentials; or
- a completed private league profile.

If a credential artifact was ever committed, remove it from the repository,
revoke or rotate the affected credential, and verify the ignore rules.
