# Reddit Data Handling

This project is a personal, non-commercial, single-user local tool. Reddit
access is disabled until Reddit explicitly approves the use case and the client
is registered as required by Reddit's current policies.

## Scope

- The initial read-only scope is limited to public posts and comments in
  `r/fantasyfootball` and `r/DynastyFF` that match a requested player name.
- The client does not access private messages, user profiles, moderator data, or
  account-level activity.
- There are no other App Users. The Reddit username is used only as contact
  information in the OAuth User-Agent.

## Processing and retention

- Content is held in memory only for the current sentiment calculation.
- The analyzer returns aggregate sentiment, engagement, counts, and injury-mention
  statistics; it does not return raw post/comment text or URLs.
- Author names, author IDs, profile URLs, flair, and other author-identifying
  metadata are never stored or returned.
- Posts and comments with Reddit removal markers, deleted authors, or removal
  metadata are excluded before analysis. In-memory content and content-derived
  cache keys are cleared when the request finishes.
- The client does not sell, redistribute, publish, or use Reddit content to train
  machine-learning or AI models. It does not infer sensitive characteristics or
  match Reddit users to off-platform identities.

## Access controls

- Requests use OAuth and a descriptive User-Agent.
- The client enforces a minimum request interval and must stop or back off when
  Reddit reports throttling or rate limits.
- Reddit content is combined locally with the user's own fantasy-football data;
  no Reddit data is sent to a hosted service by this integration.

This statement describes the local implementation. Reddit's [Responsible Builder
Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy),
[Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki),
and [Data API Terms](https://redditinc.com/policies/data-api-terms) control access
and may impose additional requirements.
