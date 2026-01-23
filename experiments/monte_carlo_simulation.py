# ======================================================================
# monte_carlo_heuristics.py — Monte Carlo experiments for h1, h2, h3, h4
# ======================================================================

from __future__ import annotations

import sys
import time
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List

# ----------------------------------------------------------------------
# Import project modules
# ----------------------------------------------------------------------

# Make sure we can import from the project root (folder that has "scripts/")
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId
from scripts.astar_vol import (
    astar_best_path_with_liquidity,
    PlanResult as AStarPlanResult,
)
from scripts.h3_parallel import parallel_search_from_random_starts
from scripts.weighted_astar import (
    weighted_astar_best_path,
    PlanResult as WeightedPlanResult,
)
from scripts.baseline_algorithms import (
    simple_1hop_arbitrage,
    simple_2hop_arbitrage,
    PlanResult as BaselinePlanResult,
)
from scripts.bellman_ford_arbitrage import (
    bellman_ford_arbitrage,
    PlanResult as BellmanFordPlanResult,
)

# Both A*, Weighted A*, baseline algorithms, and Bellman-Ford return a PlanResult-like object
PlanLike = AStarPlanResult | WeightedPlanResult | BaselinePlanResult | BellmanFordPlanResult

# ----------------------------------------------------------------------
# "Quick" Monte Carlo knobs so it doesn't run forever
# ----------------------------------------------------------------------
MC_MAX_DEPTH: int = 5          # shallower search than 6
MC_MAX_TIME_SEC: float = 60.0  # cap per search (seconds)
MC_NUM_TRIALS: int = 10        # trials per heuristic (was 50)
MC_NUM_STARTS_H3: int = 2      # parallel random starts for h3
MC_CASH_LEVELS = [1_000.0, 10_000.0, 100_000.0]


# ----------------------------------------------------------------------
# Dataclass for storing a single trial result
# ----------------------------------------------------------------------

@dataclass
class MonteCarloResult:
    heuristic: str
    start_node: Optional[NodeId]        # None for h3_parallel
    cash_usd: float
    final_cash_usd: Optional[float]
    profit_usd: Optional[float]
    path_len: Optional[int]
    duration_sec: float
    success: bool
    error: Optional[str]


# ----------------------------------------------------------------------
# Single-run wrapper (similar to compare_heuristics_live)
# ----------------------------------------------------------------------

def run_single_search(
    heuristic: str,
    cash_usd: float,
    start_node: Optional[NodeId] = None,
    max_depth: int = MC_MAX_DEPTH,
    max_time_sec: float = MC_MAX_TIME_SEC,
    min_profit_usd: float = 0.0,
) -> MonteCarloResult:
    """
    Run one search with a given heuristic and return a structured result.

    Heuristic options:
      - "h1_liquidity"  -> astar_best_path_with_liquidity using h1
      - "h2_slippage"   -> astar_best_path_with_liquidity using h2
      - "h4_chaincongestion_exchange_risk" -> weighted_astar_best_path (h4+h5)
      - "h3_parallel"   -> parallel_search_from_random_starts (wrapper over A*)
      - "simple_1hop"   -> simple_1hop_arbitrage (naive 1-hop baseline)
      - "simple_2hop"   -> simple_2hop_arbitrage (naive 2-hop baseline)
      - "bellman_ford"  -> bellman_ford_arbitrage (negative cycle detection, related research baseline)
    """
    t0 = time.perf_counter()
    error: Optional[str] = None
    result: Optional[PlanLike] = None

    try:
        if heuristic == "h3_parallel":
            # Parallel search from multiple random starts (meta-heuristic).
            result = parallel_search_from_random_starts(
                liquid_cash_usd=cash_usd,
                max_depth=max_depth,
                max_time_sec=max_time_sec,
                min_profit_usd=min_profit_usd,
                heuristic="h1_liquidity",  # base heuristic for inner A*
                num_starts=MC_NUM_STARTS_H3,
            )

        elif heuristic in ("h1_liquidity", "h2_slippage"):
            if start_node is None:
                raise ValueError("start_node must be provided for h1/h2 searches")
            result = astar_best_path_with_liquidity(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_depth=max_depth,
                max_time_sec=max_time_sec,
                min_profit_usd=min_profit_usd,
                heuristic=heuristic,
            )

        elif heuristic == "h4_chaincongestion_exchange_risk":
            if start_node is None:
                raise ValueError("start_node must be provided for h4 searches")
            # Weighted A* for chain + exchange risk (h4 + h5)
            result = weighted_astar_best_path(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_depth=max_depth,
                max_time_sec=max_time_sec,
                min_profit_usd=min_profit_usd,
            )

        elif heuristic == "simple_1hop":
            if start_node is None:
                raise ValueError("start_node must be provided for simple_1hop")
            result = simple_1hop_arbitrage(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_time_sec=max_time_sec,
                min_profit_usd=min_profit_usd,
            )

        elif heuristic == "simple_2hop":
            if start_node is None:
                raise ValueError("start_node must be provided for simple_2hop")
            result = simple_2hop_arbitrage(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_time_sec=max_time_sec,
                min_profit_usd=min_profit_usd,
            )

        elif heuristic == "bellman_ford":
            if start_node is None:
                raise ValueError("start_node must be provided for bellman_ford")
            result = bellman_ford_arbitrage(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_time_sec=max_time_sec,
                min_profit_usd=min_profit_usd,
            )

        else:
            raise ValueError(
                f"Unknown heuristic: {heuristic}. Must be one of "
                f"'h1_liquidity', 'h2_slippage', 'h4_chaincongestion_exchange_risk', "
                f"'h3_parallel', 'simple_1hop', 'simple_2hop', 'bellman_ford'."
            )

    except Exception as e:
        error = str(e)

    duration = time.perf_counter() - t0

    if result is None:
        return MonteCarloResult(
            heuristic=heuristic,
            start_node=start_node,
            cash_usd=cash_usd,
            final_cash_usd=None,
            profit_usd=None,
            path_len=None,
            duration_sec=duration,
            success=False,
            error=error or "No profitable path found",
        )

    profit = result.final_cash_usd - cash_usd

    return MonteCarloResult(
        heuristic=heuristic,
        start_node=start_node,
        cash_usd=cash_usd,
        final_cash_usd=result.final_cash_usd,
        profit_usd=profit,
        path_len=len(result.path),
        duration_sec=duration,
        success=True,
        error=None,
    )


# ----------------------------------------------------------------------
# Helper: pick random start node for h1/h2/h4
# ----------------------------------------------------------------------

def pick_random_start_node(nodes: Dict[NodeId, dict]) -> NodeId:
    """
    Choose a random node as a starting wallet.
    """
    return random.choice(list(nodes.keys()))


# ----------------------------------------------------------------------
# Monte Carlo driver
# ----------------------------------------------------------------------

def main():
    random.seed(42)  # Small bit of reproducibility

    print("=== Building graph for Monte Carlo experiments ===")
    nodes, _ = build_graph()
    num_nodes = len(nodes)
    print(f"Graph has {num_nodes} nodes")

    if num_nodes == 0:
        print("No nodes available in graph — aborting.")
        return

    # Where to write results
    results_dir = project_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / "monte_carlo_heuristics.txt"

    # Configuration of the simulation (quick mode)
    NUM_TRIALS = MC_NUM_TRIALS
    CASH_LEVELS = MC_CASH_LEVELS
    HEURISTICS = [
        "h1_liquidity",
        "h2_slippage",
        "h4_chaincongestion_exchange_risk",
        "h3_parallel",
        "simple_1hop",
        "simple_2hop",
        "bellman_ford",
    ]

    all_results: List[MonteCarloResult] = []

    with out_path.open("w", encoding="utf-8") as f:
        f.write("Monte Carlo experiments for h1, h2, h3, h4 (quick mode)\n")
        f.write("=======================================================\n\n")
        f.write(f"Number of nodes in graph: {num_nodes}\n")
        f.write(f"Cash levels: {CASH_LEVELS}\n")
        f.write(f"Heuristics: {HEURISTICS}\n")
        f.write(f"Trials per heuristic: {NUM_TRIALS}\n")
        f.write(f"Max depth: {MC_MAX_DEPTH}\n")
        f.write(f"Max time per search: {MC_MAX_TIME_SEC}s\n\n")

        # Run Monte Carlo trials
        for h in HEURISTICS:
            f.write(f"\n-------------------------------\n")
            f.write(f"Heuristic: {h}\n")
            f.write(f"-------------------------------\n")

            for trial_idx in range(1, NUM_TRIALS + 1):
                cash = random.choice(CASH_LEVELS)

                if h in ("h1_liquidity", "h2_slippage", "h4_chaincongestion_exchange_risk", 
                         "simple_1hop", "simple_2hop", "bellman_ford"):
                    start = pick_random_start_node(nodes)
                else:
                    start = None  # h3_parallel chooses its own starts

                print(f"[{h}] Trial {trial_idx}/{NUM_TRIALS} — cash=${cash:,.2f}")
                res = run_single_search(
                    heuristic=h,
                    cash_usd=cash,
                    start_node=start,
                )
                all_results.append(res)

                start_str = (
                    "random_parallel"
                    if res.start_node is None
                    else f"{res.start_node[0]}:{res.start_node[1]}"
                )
                status = "OK" if res.success else "FAIL"
                final_str = (
                    f"${res.final_cash_usd:.2f}"
                    if res.final_cash_usd is not None
                    else "N/A"
                )
                profit_str = (
                    f"${res.profit_usd:.2f}"
                    if res.profit_usd is not None
                    else "N/A"
                )

                f.write(
                    f"Trial {trial_idx:03d} [{status}] "
                    f"start={start_str:18s} "
                    f"cash=${res.cash_usd:9,.2f} "
                    f"final={final_str:10s} "
                    f"profit={profit_str:10s} "
                    f"len={str(res.path_len):>3s} "
                    f"time={res.duration_sec:6.3f}s"
                )
                if not res.success and res.error:
                    f.write(f"  (error={res.error})")
                f.write("\n")

        # ------------------------------------------------------------------
        # Aggregate summary by heuristic
        # ------------------------------------------------------------------
        f.write("\n\n================= SUMMARY BY HEURISTIC =================\n")

        by_heur: Dict[str, List[MonteCarloResult]] = {h: [] for h in HEURISTICS}
        for r in all_results:
            by_heur[r.heuristic].append(r)

        for h in HEURISTICS:
            group = by_heur[h]
            if not group:
                continue

            num_trials = len(group)
            successes = [g for g in group if g.success]
            num_success = len(successes)
            success_rate = num_success / num_trials if num_trials > 0 else 0.0

            avg_profit = (
                sum(g.profit_usd for g in successes if g.profit_usd is not None) /
                num_success
                if num_success > 0 else 0.0
            )

            avg_time = (
                sum(g.duration_sec for g in group) / num_trials
                if num_trials > 0 else 0.0
            )

            f.write(f"\nHeuristic: {h}\n")
            f.write(f"  Trials:        {num_trials}\n")
            f.write(f"  Successes:     {num_success}\n")
            f.write(f"  Success rate:  {success_rate*100:.2f}%\n")
            f.write(f"  Avg profit*:   ${avg_profit:.4f} (over successful runs)\n")
            f.write(f"  Avg runtime:   {avg_time:.3f}s per trial\n")

    print(f"\nMonte Carlo experiments complete.")
    print(f"Results written to: {out_path}")


if __name__ == "__main__":
    main()
