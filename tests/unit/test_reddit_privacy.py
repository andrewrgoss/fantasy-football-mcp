"""Tests for Reddit scope and deleted-content handling."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.agents.reddit_analyzer import (
    INITIAL_SUBREDDITS,
    RedditSentimentAgent,
    SentimentModel,
    _is_removed_comment,
    _is_removed_post,
)


def live_author(name="example_user"):
    return SimpleNamespace(name=name)


def post(**overrides):
    values = {
        "title": "Player outlook",
        "selftext": "Start this player",
        "author": live_author(),
        "removed_by_category": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def comment(**overrides):
    values = {"body": "Start this player", "author": live_author()}
    values.update(overrides)
    return SimpleNamespace(**values)


def test_initial_scope_is_narrow_and_explicit():
    assert [entry["name"] for entry in INITIAL_SUBREDDITS] == [
        "fantasyfootball",
        "DynastyFF",
    ]


def test_removed_posts_fail_closed():
    assert not _is_removed_post(post())
    assert _is_removed_post(post(title="[removed]"))
    assert _is_removed_post(post(selftext="[deleted]"))
    assert _is_removed_post(post(removed_by_category="moderator"))
    assert _is_removed_post(post(author=None))
    assert _is_removed_post(post(author=live_author("[deleted]")))
    assert _is_removed_post(post(author=SimpleNamespace(name=None)))


def test_removed_comments_fail_closed():
    assert not _is_removed_comment(comment())
    assert _is_removed_comment(comment(body="[deleted]"))
    assert _is_removed_comment(comment(body=""))
    assert _is_removed_comment(comment(author=None))
    assert _is_removed_comment(comment(author=live_author("[removed]")))


def test_sentiment_summary_does_not_return_raw_reddit_text():
    agent = RedditSentimentAgent.__new__(RedditSentimentAgent)
    agent.injury_keywords = ["injury"]
    agent._calculate_sentiment_async = AsyncMock(return_value=0.4)

    summary = asyncio.run(
        agent._analyze_sentiment_data(
            {
                "posts": [
                    {
                        "text": "Player outlook",
                        "score": 20,
                        "weight": 1.0,
                        "subreddit": "fantasyfootball",
                    }
                ],
                "comments": [
                    {
                        "text": "Start this player",
                        "score": 25,
                        "weight": 1.0,
                        "subreddit": "fantasyfootball",
                    }
                ],
            },
            SentimentModel.KEYWORD_BASED,
            "Player",
        )
    )

    assert summary["top_comments"] == []
