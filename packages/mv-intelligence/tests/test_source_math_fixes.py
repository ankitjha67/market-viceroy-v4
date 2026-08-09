"""Regressions for the source-math defects found by the robustness sweep."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from mv.intelligence.gex.engine import gamma_profile
from mv.intelligence.sources.deribit import OptionSummary
from mv.intelligence.sources.prediction_markets import parse_markets
from mv.intelligence.sources.reddit_api import RedditPost, social_sentiment
from mv.intelligence.sources.sec_13f import Holding, holdings_diff, parse_information_table

_NOW = datetime(2026, 8, 5, tzinfo=timezone.utc)
_EXPIRY = _NOW + timedelta(days=30)


def _opt(strike: float, right: str, oi: float, iv: float = 0.6, under: float = 100000.0) -> Any:
    return OptionSummary(
        strike=strike,
        expiry=_EXPIRY,
        right="C" if right == "C" else "P",
        open_interest=oi,
        mark_iv=iv,
        underlying=under,
    )


def test_gamma_flip_is_found_when_cumulative_crosses_downward() -> None:
    # Calls low, puts high: cumulative GEX goes POSITIVE then NEGATIVE. Only
    # testing the upward crossing reported the flip at the last strike, far
    # above spot and on the wrong side of it.
    chain = [_opt(90000, "C", oi=2000), _opt(110000, "P", oi=3000)]
    profile = gamma_profile(chain, as_of=_NOW)
    assert profile is not None
    assert 90000 < profile.zero_gex < 110000, "the flip sits between the strikes"


def test_a_chain_with_no_measurable_gamma_has_no_profile() -> None:
    # Illiquid Deribit rows quote mark_iv 0. Those cannot produce levels, and
    # inventing them (flip at the first strike, magnet at the last, a
    # "balanced" 0.5 dealer delta) is indistinguishable from a real reading.
    chain = [_opt(90000, "P", oi=2000, iv=0.0), _opt(110000, "C", oi=1500, iv=0.0)]
    assert gamma_profile(chain, as_of=_NOW) is None


def test_spot_is_anchored_on_the_nearest_expiry_not_payload_order() -> None:
    near = OptionSummary(
        strike=100000,
        expiry=_NOW + timedelta(days=7),
        right="C",
        open_interest=500,
        mark_iv=0.6,
        underlying=100000.0,
    )
    far = OptionSummary(
        strike=90000,
        expiry=_NOW + timedelta(days=90),
        right="P",
        open_interest=800,
        mark_iv=0.6,
        underlying=104000.0,  # the far forward, not spot
    )
    forward_order = gamma_profile([near, far], as_of=_NOW)
    reversed_order = gamma_profile([far, near], as_of=_NOW)
    assert forward_order is not None and reversed_order is not None
    assert forward_order.spot == reversed_order.spot == 100000.0


_XML_WITH_PUT = """<?xml version="1.0"?>
<informationTable>
  <infoTable>
    <nameOfIssuer>ACME</nameOfIssuer><cusip>111111111</cusip><value>3000</value>
    <shrsOrPrnAmt><sshPrnamt>700</sshPrnamt></shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>ACME</nameOfIssuer><cusip>111111111</cusip><value>1000</value>
    <shrsOrPrnAmt><sshPrnamt>500</sshPrnamt></shrsOrPrnAmt><putCall>Put</putCall>
  </infoTable>
</informationTable>
"""


def test_option_lines_are_not_merged_into_the_share_position() -> None:
    holdings = parse_information_table(_XML_WITH_PUT)
    assert {h.put_call for h in holdings} == {"", "Put"}
    common = next(h for h in holdings if h.put_call == "")
    assert common.shares == 700, "a protective put must not inflate the share line"


def test_diff_classifies_on_shares_not_market_value() -> None:
    # The filer 2.5x'd the position while the price fell, so market value is
    # unchanged. A value-only diff reported "no change" -- the opposite of what
    # the filer actually did.
    previous = [Holding("ACME", "111111111", 1000, 100)]
    current = [Holding("ACME", "111111111", 1000, 250)]
    changes = holdings_diff(previous, current)
    assert [c.kind for c in changes] == ["increased"]


def test_a_price_move_alone_is_not_a_position_change() -> None:
    previous = [Holding("ACME", "111111111", 1000, 100)]
    current = [Holding("ACME", "111111111", 1800, 100)]  # same shares, rallied
    assert holdings_diff(previous, current) == []


def test_yes_probability_is_matched_by_outcome_name() -> None:
    payload: list[dict[str, Any]] = [
        # YES is the SECOND outcome here: index 0 would report the NO price.
        {
            "question": "Will BTC be above 100k?",
            "outcomes": '["No", "Yes"]',
            "outcomePrices": '["0.80", "0.20"]',
            "volume": 100,
        },
        # A multi-candidate market has no YES at all and must be dropped.
        {
            "question": "Who wins?",
            "outcomes": '["Alice", "Bob"]',
            "outcomePrices": '["0.55", "0.45"]',
            "volume": 100,
        },
    ]
    markets = parse_markets(payload)
    assert len(markets) == 1
    assert markets[0].probability == 0.20


def _post(title: str, score: int = 10) -> RedditPost:
    return RedditPost(title=title, created=_NOW, score=score, num_comments=0, subreddit="x")


def test_lexicon_free_posts_do_not_dilute_a_real_reading() -> None:
    posts = [_post("Bitcoin surges to a record high on strong demand")]
    posts += [_post(f"Daily Discussion Thread {i}") for i in range(39)]
    score = social_sentiment(posts)
    assert score is not None and score > 0.5, "housekeeping posts are not neutral opinions"


def test_no_scorable_title_is_no_coverage() -> None:
    assert social_sentiment([_post("Daily Discussion Thread - August 5")]) is None
    assert social_sentiment([]) is None
