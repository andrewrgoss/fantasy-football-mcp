# Reddit Data API Setup

Reddit sentiment is optional. The offline auction workflow and Yahoo tools do
not require Reddit.

Reddit requires explicit approval for this external PRAW/MCP use case. Review
the [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy),
[Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki),
and [Data API Terms](https://redditinc.com/policies/data-api-terms) before making
requests. Submit the
[Data API access form](https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164).

Do not call Reddit with an unapproved client. Creating a legacy OAuth app does
not itself grant Data API approval.

## Copy-ready access-request answers

Replace bracketed identity fields with truthful information.

- **What do you need assistance with?** `Data Access Request`
- **Your email address:** `[your email address]`
- **Which role best describes your reason for requesting API access?** `I'm a developer`
- **What is your inquiry?** `I'm a developer and want to build a Reddit App that does not work in the Devvit ecosystem.`
- **Reddit account name:** `[your Reddit username]` without `u/`
- **Provide a link to source code or platform:** the public URL of your fork
- **Subreddits:** `r/fantasyfootball` and `r/DynastyFF` initially
- **Operating username:** the same Reddit username
- **Attachments:** none required unless Reddit requests them

**Benefit/purpose for Redditors:**

```text
This is a private, single-user decision-support tool for one Redditor. It summarizes public fantasy-football discussion so I can make better personal fantasy football draft, roster, matchup, and waiver decisions. It is not academic research, has no other App Users, and does not act on behalf of other Redditors or change anything on Reddit.
```

**Detailed application description:**

```text
Fantasy Football MCP is a personal, single-user, read-only local MCP server, not academic research or a public bot. After Reddit approves access, it will use one registered OAuth client through PRAW to retrieve recent public posts and comments matching requested fantasy-football player names, initially limited to r/fantasyfootball and r/DynastyFF. It will calculate aggregate sentiment and engagement locally for my own fantasy football draft, roster, matchup, and waiver analysis. It has no other App Users and will not post, vote, comment, message, moderate, follow, join communities, profile Redditors, infer sensitive characteristics, match users to off-platform identities, or otherwise change Reddit. It will not sell, redistribute, publish raw content, or use Reddit content for model training. No author identifiers will be retained, deleted content will be filtered, raw content will be held only in memory for the current analysis, and the client will honor OAuth, rate limits, content-removal requirements, and applicable Reddit terms.
```

**Why Devvit does not fit:**

```text
Devvit is designed for apps hosted in Reddit communities. This use case is a private, local MCP server that combines read-only Reddit data with other permitted fantasy-football data and is invoked from a local assistant. It requires a local Python/PRAW process and OAuth credentials, does not need a Reddit-hosted user interface or subreddit installation, and must keep the workflow and temporary data local. Devvit does not support this cross-service, personal, local-only MCP workflow.
```

## If the request is denied without specifics

Generic denials may cite the Responsible Builder Policy without identifying a
missing requirement. Reply on the existing ticket rather than opening duplicate
requests. Remove the bracketed ticket placeholder before sending:

```text
Hello Reddit Data Team,

I am following up on ticket [ticket number]. Could you identify the specific Responsible Builder Policy requirement that caused the denial?

This is not academic research, a commercial product, a public bot, or a service for other Redditors. It is a private, single-user local fantasy-football decision-support tool that I run for my own draft preparation. The public GitHub repository contains source code only; it does not host the app, distribute Reddit data, or expose credentials.

If approved, one registered OAuth client would read only recent public posts and comments matching a requested player, initially limited to r/fantasyfootball and r/DynastyFF. It would not post, comment, vote, message, moderate, join communities, follow users, access private data, or automate any Reddit account. There would be no other App Users.

Sentiment would be calculated locally using deterministic TextBlob and keyword scoring. No Reddit content would be sent to a hosted model or used for model training. The tool would not profile Redditors, infer sensitive characteristics, re-identify users, or match Reddit accounts to off-platform identities. It would retain no usernames, author IDs, or profiles, keep content only for the current analysis, remove deleted content, and honor OAuth, rate limits, and retention requirements.

Reddit data would be combined locally with my own league settings and other permitted fantasy-football data solely for personal, non-commercial use. No Reddit content would be sold, redistributed, or published.

Devvit is not suitable because this has no Reddit-hosted UI, subreddit installation, or Reddit-side user interaction. It is a local Python/MCP process that reads Reddit alongside other permitted fantasy-football data.

Source: [public URL of your fork]

If a developer profile, app label, privacy statement, narrower subreddit scope, or another specific requirement is needed, please tell me exactly what is missing so I can correct it.
```

## Register credentials after approval

Follow the app-registration and developer-profile instructions Reddit provides.
If Reddit explicitly directs you to the legacy app form, create a **script**
client and use `http://localhost:8080` as the redirect URI. Do not assume the
legacy form bypasses approval.

Store approved credentials only in `.env`:

```env
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_reddit_username
```

Restart the MCP server, then invoke `ff_analyze_reddit_sentiment`. The tool
should report unavailability when approval or credentials are absent; it must
not fabricate a neutral sentiment result.

## Data handling

The implementation returns aggregate signals, filters removed/deleted content,
does not retain author identifiers, and clears raw content after the request.
See [REDDIT_DATA_HANDLING.md](REDDIT_DATA_HANDLING.md) for the detailed boundary.
