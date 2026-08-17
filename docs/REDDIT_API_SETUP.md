# Reddit API Credentials Setup Guide

This guide covers the approval and credential steps for the Fantasy Football MCP
Server's local, read-only sentiment-analysis feature.

## Current Reddit access requirement

Reddit now requires explicit approval before an application accesses Reddit data
through the Data API. Current policy also calls for app registration and a
developer profile. Review Reddit's [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy)
and [Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki)
before requesting access.

This repository is an external, local Python/MCP application that uses PRAW; it
is not a Devvit app running on Reddit or an academic research project. Use
Reddit's [Data API access request form](https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164)
and explain that distinction if the form asks why the use case cannot be built on
Devvit. Do not make API calls until Reddit explicitly approves the request.

For the request, describe the intended use accurately: one personal user, read-only
sentiment analysis for fantasy football discussions, initially limited to
`r/fantasyfootball` and `r/DynastyFF`, with no other App Users and no posting,
voting, messaging, moderation, resale, redistribution, profiling, off-platform
identity matching, or model training. The tool uses recent posts/comments to
produce aggregate sentiment, keeps credentials private, filters deleted content,
and honors Reddit removals and API rate limits. See the [Reddit data-handling
statement](REDDIT_DATA_HANDLING.md) for the implementation details.

## Overview

The app uses Reddit's API (via the PRAW library) to analyze fantasy football player sentiment from:
- r/fantasyfootball
- r/DynastyFF

## Step 1: Request Reddit Data API access

Submit the access request before attempting to use the credentials. The current
Reddit policy says approval is required and that apps must have a clearly defined
purpose and limited scope. Do not create a second request for the same use case;
reply to an existing ticket if Reddit asks for clarification.

## Step 2: Register the Reddit application after approval

Follow the app-registration and developer-profile instructions Reddit provides
with an approved request. Use a descriptive name such as `Fantasy Football MCP`
and identify it as a private, single-user, read-only local client.

If Reddit explicitly directs you to the legacy app form at
https://www.reddit.com/prefs/apps, use a **script** client with redirect URI
`http://localhost:8080`; otherwise, do not substitute the legacy flow. Creating a
client does not itself grant Data API approval, so do not make API calls until
Reddit has approved the request.

## Step 3: Get Your Credentials

After creating the app, you'll see a page with your app details:

1. **Client ID** (under your app name)
   - This is a string that looks like: `abc123def456ghi789`
   - Copy this value - this is your `REDDIT_CLIENT_ID`

2. **Secret** (shown as "secret" next to your app)
   - This is a longer string that looks like: `xyz789abc123def456ghi789jkl012mno345`
   - Click "edit" or "reveal" to see it if hidden
   - Copy this value - this is your `REDDIT_CLIENT_SECRET`

3. **Username** (optional but recommended)
   - Your Reddit username (the one you're logged in as)
   - This is used in the user agent string for API requests
   - This is your `REDDIT_USERNAME`

## Step 4: Add Credentials to Your .env File

Add the following lines to your `.env` file in the project root:

```env
# Reddit API Credentials (for sentiment analysis)
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USERNAME=your_reddit_username
```

**Example:**
```env
REDDIT_CLIENT_ID=abc123def456ghi789
REDDIT_CLIENT_SECRET=xyz789abc123def456ghi789jkl012mno345
REDDIT_USERNAME=myusername
```

## Step 5: Verify Installation

Make sure the required packages are installed:

```bash
pip install praw textblob
```

Or if using the requirements file:

```bash
pip install -r requirements.txt
```

## Step 6: Test the Configuration

The Reddit API will be automatically initialized when you use features that require it, such as:

- `ff_analyze_reddit_sentiment` - Analyze Reddit sentiment for players

If credentials are missing or incorrect, the app will:
- Log a warning message
- Continue operating without Reddit sentiment analysis
- Use fallback sentiment analysis methods

## Important Notes

### Rate Limits and data handling
- Reddit documents a limit of 100 queries per minute per OAuth client for eligible free Data API usage.
- The app includes rate limiting and error handling, but your approved limits and terms control.
- If you hit a limit, stop and allow the limit window to reset; do not attempt to bypass it.
- Do not retain or redistribute deleted Reddit content. The analyzer filters
  removed posts/comments and deleted authors before scoring, returns aggregate
  signals rather than raw text, and clears in-memory content after each request.
- Do not retain author names, author IDs, profiles, URLs, or other
  author-identifying metadata. Keep credentials and temporary data local.

### App Type
- Reddit's current policy requires app registration and a developer profile. Follow
  the registration instructions Reddit provides with an approved request.
- Do not assume that the legacy OAuth client form alone grants access. If Reddit
  redirects you to Devvit or the legacy app form refuses to create an app, do not
  repeatedly resubmit. Use the Data API access request and wait for Reddit's
  response.

### Security
- **Never commit your `.env` file** to version control
- Keep your `REDDIT_CLIENT_SECRET` private
- The username is optional but helps identify your app to Reddit

### Troubleshooting

**"Reddit API credentials not configured"**
- Check that all three variables are in your `.env` file
- Verify there are no extra spaces or quotes around the values
- Restart the MCP server after adding credentials

**"Reddit API connection test failed"**
- Verify your Client ID and Secret are correct
- Check that you selected "script" as the app type
- Ensure you're using the correct Reddit account

**"PRAW not available"**
- Run: `pip install praw textblob`
- Check that you're in the correct Python environment

## Optional: Verify Reddit API Access

You can test your credentials manually with this Python snippet:

```python
import os
from dotenv import load_dotenv
import praw

load_dotenv()

reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=f"fantasy-football-mcp:v1.0 by /u/{os.getenv('REDDIT_USERNAME', 'unknown')}"
)

# Test connection
try:
    subreddit = reddit.subreddit("fantasyfootball")
    print(f"✅ Connected! Subreddit has {subreddit.subscribers} subscribers")
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

## What Happens Without Reddit Credentials?

The app will still function normally, but:
- Reddit sentiment analysis will be unavailable
- The `ff_analyze_reddit_sentiment` tool will return fallback results
- You'll see warnings in the logs about missing credentials

All other features (lineup optimization, draft assistance, etc.) work independently of Reddit API.
