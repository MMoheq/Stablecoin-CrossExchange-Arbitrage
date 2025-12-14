# ======================================================================
# test_h2_slippage.py — Unit tests for the slippage heuristic
# ======================================================================

import pytest
from scripts.h2_slippage import (
    walk_order_book,
    compute_slippage_bps,
    slippage_heuristic_cost,
    UNKNOWN_SLIPPAGE_PENALTY,
    SLIPPAGE_HEURISTIC_WEIGHT,
    SLIPPAGE_THRESHOLD_BPS,
)


# -----------------------------------------------------------
# Helpers: Fake order books for controlled testing
# -----------------------------------------------------------

def make_orderbook(bids, asks):
    """Utility wrapper to build fake order books."""
    return {"bids": bids, "asks": asks}


# ===========================================================
# walk_order_book tests
# ===========================================================

def test_walk_order_book_exact_fill():
    ob = make_orderbook(
        bids=[[0.99, 1000]],
        asks=[[1.01, 500]],
    )
    total_cost, vwap = walk_order_book(ob, order_size_base=500, side="buy")
    assert total_cost == pytest.approx(500 * 1.01)
    assert vwap == pytest.approx(1.01)


def test_walk_order_book_partial_fill():
    ob = make_orderbook(
        bids=[],
        asks=[[1.00, 200], [1.02, 300]],
    )
    total_cost, vwap = walk_order_book(ob, order_size_base=400, side="buy")
    # 200 units at 1.00, next 200 at 1.02
    assert total_cost == pytest.approx((200 * 1.00) + (200 * 1.02))
    assert vwap == pytest.approx(total_cost / 400)


def test_walk_order_book_empty():
    ob = make_orderbook(bids=[], asks=[])
    total_cost, vwap = walk_order_book(ob, order_size_base=100, side="buy")
    assert total_cost == 0
    assert vwap == 0


# ===========================================================
# compute_slippage_bps tests
# ===========================================================

def test_slippage_zero():
    """If VWAP equals mid-price ⇒ slippage = 0."""
    # Mid-price = 1.00, and we execute exactly at 1.00
    ob = make_orderbook(
        bids=[[0.99, 500]],
        asks=[[1.01, 500]],
    )

    # Override to have both bid/ask at 1.00 so mid = vwap = 1.00
    ob_equal = make_orderbook(
        bids=[[1.00, 500]],
        asks=[[1.00, 500]],
    )

    slip = compute_slippage_bps(ob_equal, order_size_base=100, side="buy")
    assert slip == pytest.approx(0.0)


def test_slippage_positive_buy():
    """Buying should create positive slippage (VWAP > mid)."""
    ob = make_orderbook(
        bids=[[1.00, 1000]],
        asks=[[1.05, 1000]],
    )
    slip = compute_slippage_bps(ob, order_size_base=100, side="buy")
    assert slip is not None
    assert slip > 0


def test_slippage_none_on_invalid_book():
    slip = compute_slippage_bps({}, 100, "buy")
    assert slip is None


# ===========================================================
# slippage_heuristic_cost tests
# ===========================================================

def test_h2_unknown_order_book_penalty(monkeypatch):
    """If fetch_order_book_for_coin returns None, heuristic returns penalty."""

    def fake_fetch(exchange, coin, limit=20):
        return None

    monkeypatch.setattr(
        "scripts.h2_slippage.fetch_order_book_for_coin",
        fake_fetch,
    )

    cost = slippage_heuristic_cost("binance", "USDT", order_size_usd=1000)
    assert cost == UNKNOWN_SLIPPAGE_PENALTY


def test_h2_low_slippage(monkeypatch):
    """If slippage < threshold → cost = 0."""

    def fake_fetch(exchange, coin, limit=20):
        return make_orderbook(
            bids=[[1.00, 10000]],
            asks=[[1.01, 10000]],
        )

    monkeypatch.setattr(
        "scripts.h2_slippage.fetch_order_book_for_coin",
        fake_fetch,
    )

    cost = slippage_heuristic_cost("binance", "USDT", order_size_usd=100)
    assert cost == 0.0


def test_h2_high_slippage(monkeypatch):
    """Slippage above threshold should produce penalty."""

    def fake_fetch(exchange, coin, limit=20):
        # Large slippage scenario (asks far above mid-price)
        return make_orderbook(
            bids=[[1.00, 10000]],
            asks=[[1.50, 10000]],
        )

    monkeypatch.setattr(
        "scripts.h2_slippage.fetch_order_book_for_coin",
        fake_fetch,
    )

    # Compute cost via the heuristic
    slip_cost = slippage_heuristic_cost("binance", "USDT", order_size_usd=100)

    # Compute expected cost directly from slippage_bps
    base_ob = make_orderbook([[1.00, 10000]], [[1.50, 10000]])
    slippage_bps = compute_slippage_bps(base_ob, order_size_base=100, side="buy")
    assert slippage_bps is not None

    expected_cost = SLIPPAGE_HEURISTIC_WEIGHT * max(
        0.0, slippage_bps - SLIPPAGE_THRESHOLD_BPS
    )

    assert slip_cost == pytest.approx(expected_cost)
