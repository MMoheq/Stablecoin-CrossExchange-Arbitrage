# ==============================================================
# test_astar_vol_toygraph.py — sanity test for A* on a toy graph
# ==============================================================

from __future__ import annotations

import math
import sys
from pathlib import Path

# Make sure we can import from project root (folder that has "scripts/")
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts import astar_vol  # type: ignore

NodeId = tuple[str, str]


def make_toy_graph():
    """
    Build a tiny 3-node toy graph where the best path from A to C is
    A -> B -> C, and a direct edge A -> C is slightly worse.
    """
    # pretend these are (exchange, coin)
    A: NodeId = ("ex1", "USDT")
    B: NodeId = ("ex1", "USDC")
    C: NodeId = ("ex1", "DAI")

    nodes = {
        A: {"exchange": "ex1", "coin": "USDT", "price_usd": 1.0, "snapshot_ts": 0.0},
        B: {"exchange": "ex1", "coin": "USDC", "price_usd": 1.0, "snapshot_ts": 0.0},
        C: {"exchange": "ex1", "coin": "DAI",  "price_usd": 1.0, "snapshot_ts": 0.0},
    }

    def edge(rate: float, from_node: NodeId, to_node: NodeId) -> dict:
        return {
            "from": from_node,
            "to": to_node,
            "kind": "trade",
            "exchange": "ex1",
            "coin_from": from_node[1],
            "coin_to": to_node[1],
            "rate": rate,
            "cost": -math.log(rate),
            "taker_fee": 0.0,
            "withdrawal_fee_units": None,
            "reference_amount_units": None,
            "chain": None,
            "transfer_time_sec": 0.0,
        }

    # Direct A -> C edge is slightly worse than going via B
    adj = {
        A: [
            edge(1.01, A, B),
            edge(1.01 * 1.01 * 0.99, A, C),  # worse than A->B->C
        ],
        B: [edge(1.01, B, C)],
        C: [],
    }

    return nodes, adj


def run_toy_astar_test() -> None:
    """
    Patch astar_vol.build_graph to use our toy graph and check that the
    algorithm prefers the 2-step path A->B->C over the direct A->C edge.
    """
    # Save original build_graph so we can restore it
    original_build_graph = astar_vol.build_graph

    try:
        # Monkey-patch build_graph inside astar_vol
        astar_vol.build_graph = make_toy_graph  # type: ignore[assignment]

        start: NodeId = ("ex1", "USDT")
        initial_cash = 1000.0

        result = astar_vol.astar_best_path_with_liquidity(
            start_node=start,
            liquid_cash_usd=initial_cash,
            max_depth=3,
            max_time_sec=60.0,
            min_profit_usd=0.0,
            heuristic="h1_liquidity",
        )

        assert result is not None, "A* returned no result on toy graph."

        expected_path = [
            ("ex1", "USDT"),
            ("ex1", "USDC"),
            ("ex1", "DAI"),
        ]
        assert (
            result.path == expected_path
        ), f"Expected path {expected_path}, got {result.path}"

        print("Toy A* test PASSED")
        print(f"Path: {result.path}")
        print(f"Final cash: {result.final_cash_usd:.2f}")

    finally:
        # Always restore original build_graph
        astar_vol.build_graph = original_build_graph  # type: ignore[assignment]


if __name__ == "__main__":
    run_toy_astar_test()
