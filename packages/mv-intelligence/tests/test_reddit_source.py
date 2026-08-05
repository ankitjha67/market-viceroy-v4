"""Tests for the Reddit official-API source (parse + weighted sentiment)."""

from __future__ import annotations

from mv.intelligence.sources.reddit_api import (
    parse_posts,
    posts_to_news_items,
    social_sentiment,
)


def _payload(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"data": {"children": [{"data": row} for row in rows]}}


def test_parse_posts_maps_fields_and_drops_malformed() -> None:
    posts = parse_posts(
        _payload(
            [
                {
                    "title": "Bitcoin surges to a record high",
                    "created_utc": 1754300000,
                    "score": 500,
                    "num_comments": 120,
                    "subreddit": "CryptoCurrency",
                },
                {"title": "", "created_utc": 1754300000},  # no title
                {"title": "No timestamp"},  # no created_utc
            ]
        )
    )
    assert len(posts) == 1
    assert posts[0].subreddit == "CryptoCurrency"
    assert posts[0].created.tzinfo is not None  # publish-time stamped


def test_social_sentiment_weights_by_reception() -> None:
    posts = parse_posts(
        _payload(
            [
                {"title": "Bitcoin surges, strong rally and gains", "created_utc": 1, "score": 100},
                {"title": "Bitcoin crashes and plunges on fears", "created_utc": 2, "score": 1},
            ]
        )
    )
    score = social_sentiment(posts)
    assert score is not None
    assert score > 0  # the heavily-upvoted bullish post dominates the weighting


def test_no_posts_is_none_not_neutral() -> None:
    assert social_sentiment([]) is None


def test_posts_become_publish_time_news_items() -> None:
    posts = parse_posts(_payload([{"title": "Ethereum upgrade ships", "created_utc": 1754300000}]))
    items = posts_to_news_items(posts)
    assert items[0].title == "Ethereum upgrade ships"
    assert items[0].published == posts[0].created
