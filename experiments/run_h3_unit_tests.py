# ======================================================================
# run_h3_unit_tests.py / test_h3_parallel.py
# — Unit tests for the parallel search heuristic + verbose runner
# ======================================================================

from __future__ import annotations

import sys
import io
import contextlib
from pathlib import Path
from datetime import datetime, timezone

# ----------------------------------------------------------------------
# Make repo root importable so "scripts.*" works when run from /experiments
# ----------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # type: ignore
from scripts.h3_parallel import parallel_search_from_random_starts


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


class DummyResult:
    """Minimal PlanResult-like object used in tests."""
    def __init__(self, final_cash_usd: float):
        self.final_cash_usd = final_cash_usd
        self.path = []      # not used by h3, but harmless
        self.edges = []     # same here


# ======================================================================
# Tests
# ======================================================================

def test_parallel_search_empty_graph(monkeypatch):
    """If build_graph returns no nodes, we should get None."""

    def fake_build_graph():
        return {}, {}   # nodes, adj

    # Patch build_graph inside scripts.h3_parallel
    monkeypatch.setattr(
        "scripts.h3_parallel.build_graph",
        fake_build_graph,
    )

    result = parallel_search_from_random_starts(
        liquid_cash_usd=1000.0,
        max_depth=3,
        max_time_sec=10.0,
        min_profit_usd=0.0,
        heuristic="h1_liquidity",
        num_starts=3,
    )

    assert result is None


def test_parallel_search_picks_best_result(monkeypatch):
    """
    Given several starting nodes with different profits, the function
    should return the one with the highest final_cash_usd.
    """

    # Fake graph with three nodes
    nodes = {
        ("ex1", "USDT"): {},
        ("ex2", "USDT"): {},
        ("ex3", "USDT"): {},
    }

    def fake_build_graph():
        return nodes, {}

    monkeypatch.setattr(
        "scripts.h3_parallel.build_graph",
        fake_build_graph,
    )

    # Make random.sample deterministic: pick the first k nodes
    def fake_sample(population, k):
        pop_list = list(population)
        return pop_list[:k]

    monkeypatch.setattr(
        "scripts.h3_parallel.random.sample",
        fake_sample,
    )

    # Fake A* results: ex2 is the best
    def fake_astar(start_node, liquid_cash_usd, max_depth, max_time_sec,
                   min_profit_usd, heuristic):
        if start_node == ("ex1", "USDT"):
            return DummyResult(liquid_cash_usd + 1.0)
        if start_node == ("ex2", "USDT"):
            return DummyResult(liquid_cash_usd + 5.0)
        if start_node == ("ex3", "USDT"):
            return DummyResult(liquid_cash_usd + 2.0)
        return None

    monkeypatch.setattr(
        "scripts.h3_parallel.astar_best_path_with_liquidity",
        fake_astar,
    )

    base_cash = 1000.0
    result = parallel_search_from_random_starts(
        liquid_cash_usd=base_cash,
        max_depth=3,
        max_time_sec=10.0,
        min_profit_usd=0.0,
        heuristic="h1_liquidity",
        num_starts=3,
    )

    assert isinstance(result, DummyResult)
    # Should pick ex2’s result with +5 profit
    assert result.final_cash_usd == pytest.approx(base_cash + 5.0)


def test_parallel_search_respects_num_starts(monkeypatch):
    """
    If num_starts > number of nodes, we should only run as many searches
    as there are nodes.
    """

    # Only two nodes in the graph
    nodes = {
        ("ex1", "USDT"): {},
        ("ex2", "USDT"): {},
    }

    def fake_build_graph():
        return nodes, {}

    monkeypatch.setattr(
        "scripts.h3_parallel.build_graph",
        fake_build_graph,
    )

    # Deterministic sample again
    def fake_sample(population, k):
        pop_list = list(population)
        return pop_list[:k]

    monkeypatch.setattr(
        "scripts.h3_parallel.random.sample",
        fake_sample,
    )

    call_count = {"n": 0}

    def fake_astar(start_node, liquid_cash_usd, max_depth, max_time_sec,
                   min_profit_usd, heuristic):
        call_count["n"] += 1
        # Return some valid DummyResult so the search succeeds
        return DummyResult(liquid_cash_usd + 1.0)

    monkeypatch.setattr(
        "scripts.h3_parallel.astar_best_path_with_liquidity",
        fake_astar,
    )

    result = parallel_search_from_random_starts(
        liquid_cash_usd=500.0,
        max_depth=3,
        max_time_sec=10.0,
        min_profit_usd=0.0,
        heuristic="h1_liquidity",
        num_starts=5,   # ask for more than available nodes
    )

    # We only have 2 nodes, so A* should have been called twice
    assert call_count["n"] == 2
    assert isinstance(result, DummyResult)


# ======================================================================
# Verbose runner + output logger
# ======================================================================

def main() -> None:
    results_dir = REPO_ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    out_file = results_dir / "unit_tests_h3.txt"

    buf = io.StringIO()

    with contextlib.redirect_stdout(buf):
        # Verbose pytest run on THIS file
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
