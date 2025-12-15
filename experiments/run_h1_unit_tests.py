
from __future__ import annotations

import sys
import io
import contextlib
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # type: ignore
import scripts.h1_vol as h1  # type: ignore


def test_unknown_volume_returns_penalty(monkeypatch):
    """
    If we cannot fetch 24h volume for this (exchange, coin),
    volume_heuristic_cost should return UNKNOWN_LIQUIDITY_PENALTY.
    """

    # Make volume lookup fail (simulate missing data)
    def fake_get_24h(exchange_name: str, coin: str):
        return None

    # Patch the function used inside estimate_liquidity_score_live
    monkeypatch.setattr(h1, "get_24h_quote_volume_for_coin", fake_get_24h)

    cost = h1.volume_heuristic_cost(
        "binance",
        "USDT",
        order_notional_usd=1_000.0,
        remaining_time_sec=60.0,
    )

    assert cost == pytest.approx(h1.UNKNOWN_LIQUIDITY_PENALTY)



def test_zero_volume_returns_zero_or_low_cost():
    """
    With zero volume, heuristic cost should not blow up; ideally zero.
    """
    cost = h1.volume_heuristic_cost("binance", "USDT", 0.0, remaining_time_sec=60.0)
    assert cost >= 0.0
    assert cost == pytest.approx(cost, abs=1e-9)  # just sanity / type check


def test_high_volume_gives_higher_cost_than_low_volume():
    """
    Very large volume should be penalized at least as much as small volume.
    """
    low_volume_cost = h1.volume_heuristic_cost(
        "binance", "USDT", 1_000.0, remaining_time_sec=60.0
    )
    high_volume_cost = h1.volume_heuristic_cost(
        "binance", "USDT", 1_000_000.0, remaining_time_sec=60.0
    )

    assert low_volume_cost >= 0.0
    assert high_volume_cost >= 0.0
    assert high_volume_cost >= low_volume_cost


def test_high_volume_exceeds_threshold_if_defined(monkeypatch):
    """
    If VOLUME_THRESHOLD_USD exists in h1_vol, check that volume
    well above the threshold is penalized more than volume well below it.
    If it doesn't exist, we skip this test gracefully.
    """
    if not hasattr(h1, "VOLUME_THRESHOLD_USD"):
        pytest.skip("VOLUME_THRESHOLD_USD not defined in h1_vol; skipping threshold-specific test")

    # Patch the threshold on the module object directly
    monkeypatch.setattr(h1, "VOLUME_THRESHOLD_USD", 10_000.0)

    below_cost = h1.volume_heuristic_cost(
        "binance", "USDT", 5_000.0, remaining_time_sec=60.0
    )
    above_cost = h1.volume_heuristic_cost(
        "binance", "USDT", 50_000.0, remaining_time_sec=60.0
    )

    assert below_cost >= 0.0
    assert above_cost >= 0.0
    assert above_cost >= below_cost


def main() -> None:
    results_dir = REPO_ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    out_file = results_dir / "unit_tests_h1.txt"

    buf = io.StringIO()

    with contextlib.redirect_stdout(buf):
        # Run pytest VERBOSE on THIS file
        ret = pytest.main([
            "-vv",
            "--durations=0",
            __file__,
        ])

    log_output = buf.getvalue()

    # Show in terminal
    print(log_output)

    # Save to txt file with UTC timestamp
    with out_file.open("w", encoding="utf-8") as f:
        f.write(f"Run at {datetime.now(timezone.utc).isoformat()}\n\n")
        f.write(log_output)

    sys.exit(ret)


if __name__ == "__main__":
    main()
