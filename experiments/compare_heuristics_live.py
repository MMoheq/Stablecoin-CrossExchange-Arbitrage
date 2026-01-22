# ==============================================================
# compare_heuristics_live.py — quick experiments for h1, h2, h3, h4
# ==============================================================

from __future__ import annotations

import sys
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Tuple, List, Any

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

# Result from either classic A*, weighted A*, or baseline algorithms
PlanLike = AStarPlanResult | WeightedPlanResult | BaselinePlanResult

# -------------------------------------------------------------------
# "Quick experiment" knobs (tuned so it doesn't take an hour)
# -------------------------------------------------------------------
QUICK_MAX_DEPTH: int = 5          # shallower search than 6
QUICK_MAX_TIME_SEC: float = 60.0  # ≈ 1 minute cap per search (best-effort)
QUICK_NUM_START_NODES: int = 3    # use at most 3 start nodes
QUICK_NUM_STARTS_H3: int = 2      # parallel random starts for h3
QUICK_CASH_LEVELS: List[float] = [1_000.0, 10_000.0, 100_000.0]
MAX_WORKERS: int = 8              # number of parallel threads for running searches


@dataclass
class ExperimentResult:
    heuristic: str
    start_node: Optional[NodeId]  # None for h3_parallel
    cash_usd: float
    final_cash_usd: Optional[float]
    profit_usd: Optional[float]
    path_len: Optional[int]
    duration_sec: float
    success: bool
    error: Optional[str]


def run_single_search(
    heuristic: str,
    cash_usd: float,
    start_node: Optional[NodeId] = None,
    max_depth: int = QUICK_MAX_DEPTH,
    max_time_sec: float = QUICK_MAX_TIME_SEC,
    min_profit_usd: float = 0.0,
) -> ExperimentResult:
    """
    Run one search with a given heuristic and return a structured result.

    Heuristic options:
      - "h1_liquidity"  -> astar_best_path_with_liquidity using h1
      - "h2_slippage"   -> astar_best_path_with_liquidity using h2
      - "h4_chaincongestion_exchange_risk" -> weighted_astar_best_path (h4+h5)
      - "h3_parallel"   -> parallel_search_from_random_starts (wrapper over A*)
      - "simple_1hop"   -> simple_1hop_arbitrage (naive 1-hop baseline)
      - "simple_2hop"   -> simple_2hop_arbitrage (naive 2-hop baseline)
    """
    t0 = time.perf_counter()
    error: Optional[str] = None
    result: Optional[PlanLike] = None

    try:
        if heuristic == "h3_parallel":
            # Parallel search from multiple random starts (internally uses A* with h1).
            random.seed(42)  # small bit of reproducibility
            result = parallel_search_from_random_starts(
                liquid_cash_usd=cash_usd,
                max_depth=max_depth,
                max_time_sec=max_time_sec,
                min_profit_usd=min_profit_usd,
                heuristic="h1_liquidity",
                num_starts=QUICK_NUM_STARTS_H3,
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
            # Weighted A* using chain + exchange risk heuristic (h4 + h5).
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

        else:
            raise ValueError(
                f"Unknown heuristic: {heuristic}. Must be one of "
                f"'h1_liquidity', 'h2_slippage', 'h3_parallel', "
                f"'h4_chaincongestion_exchange_risk', 'simple_1hop', 'simple_2hop'."
            )

    except Exception as e:
        error = str(e)

    duration = time.perf_counter() - t0

    if result is None:
        return ExperimentResult(
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

    return ExperimentResult(
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


def pick_start_nodes(nodes: Dict[NodeId, dict]) -> List[NodeId]:
    """
    Choose a small, fixed set of interesting start nodes for experiments.
    Prefers binance:BUSD, binance:USDT, kraken:USDT if present,
    then fills with a few random ones.
    """
    preferred: List[NodeId] = []
    candidates = set(nodes.keys())

    for ex, coin in [("binance", "BUSD"), ("binance", "USDT"), ("kraken", "USDT")]:
        node = (ex, coin)
        if node in candidates:
            preferred.append(node)
            candidates.remove(node)

    # Add up to 2 random additional nodes to diversify
    extra = list(candidates)
    random.shuffle(extra)
    preferred.extend(extra[:2])

    # Limit to "quick" number of start nodes
    return preferred[:QUICK_NUM_START_NODES]


def main() -> None:
    # Setup output file with incremental writing
    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / "compare_heuristics_live.txt"
    
    # Thread-safe file writing
    file_lock = threading.Lock()
    all_results: List[ExperimentResult] = []
    results_lock = threading.Lock()
    
    def log_and_write(msg: str = "", flush: bool = False) -> None:
        """Print to console and immediately write to file (thread-safe)."""
        print(msg)
        with file_lock:
            with out_path.open("a", encoding="utf-8") as f:
                f.write(msg + "\n")
                if flush:
                    f.flush()
    
    # Clear previous results and write header
    with out_path.open("w", encoding="utf-8") as f:
        f.write("=== Heuristic Comparison Experiments ===\n")
        f.write(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    log_and_write("=== Building graph ===")
    nodes, _ = build_graph()
    log_and_write(f"Graph has {len(nodes)} nodes")

    # Choose starting nodes for h1/h2/h4 experiments
    start_nodes = pick_start_nodes(nodes)
    log_and_write("\nUsing start nodes:")
    for n in start_nodes:
        log_and_write(f"  - {n[0]}:{n[1]}")

    # Different order sizes we want to test (quick settings)
    cash_levels = QUICK_CASH_LEVELS
    
    log_and_write(f"\nRunning with {MAX_WORKERS} parallel workers\n")

    # ---- Run experiments in parallel ----
    for cash in cash_levels:
        log_and_write("\n============================")
        log_and_write(f"Order size: ${cash:,.2f}")
        log_and_write("============================")

        # Build list of all tasks to run in parallel
        tasks: List[Tuple[str, Optional[NodeId], float]] = []
        
        # h1 + h2 + h4: run for each start node
        for start in start_nodes:
            for h in ["h1_liquidity", "h2_slippage", "h4_chaincongestion_exchange_risk"]:
                tasks.append((h, start, cash))
        
        # Simple baselines: run for each start node
        for start in start_nodes:
            for h in ["simple_1hop", "simple_2hop"]:
                tasks.append((h, start, cash))
        
        # h3_parallel: start nodes are chosen inside the function
        tasks.append(("h3_parallel", None, cash))
        
        # Run all tasks in parallel
        def run_task(heuristic: str, start: Optional[NodeId], cash_val: float) -> ExperimentResult:
            """Wrapper function for parallel execution."""
            start_str = (
                "random_parallel"
                if start is None
                else f"{start[0]}:{start[1]}"
            )
            log_and_write(f"\n[START] Running {heuristic} from {start_str} (cash=${cash_val:,.2f}) ...", flush=True)
            
            res = run_single_search(
                heuristic=heuristic,
                cash_usd=cash_val,
                start_node=start,
            )
            
            # Thread-safe result storage
            with results_lock:
                all_results.append(res)
            
            # Log result immediately
            if res.success:
                log_and_write(
                    f"[DONE] {heuristic} from {start_str}: SUCCESS - "
                    f"final=${res.final_cash_usd:.2f} "
                    f"(profit=${res.profit_usd:.2f}), "
                    f"path_len={res.path_len}, "
                    f"time={res.duration_sec:.3f}s",
                    flush=True
                )
            else:
                log_and_write(
                    f"[DONE] {heuristic} from {start_str}: FAIL - {res.error} "
                    f"(time={res.duration_sec:.3f}s)",
                    flush=True
                )
            
            return res
        
        # Execute all tasks in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(run_task, h, start, cash): (h, start, cash)
                for h, start, cash in tasks
            }
            
            # Wait for all to complete (results are logged as they finish)
            for future in as_completed(futures):
                try:
                    future.result()  # This will raise any exceptions
                except Exception as e:
                    heuristic, start_node, cash_val = futures[future]
                    log_and_write(
                        f"[ERROR] {heuristic} from {start_node}: Exception - {str(e)}",
                        flush=True
                    )

    # ---- Compact summary at the end ----
    log_and_write("\n\n================ SUMMARY ================")
    for res in sorted(all_results, key=lambda x: (x.cash_usd, x.heuristic, str(x.start_node))):
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
        log_and_write(
            f"[{status}] h={res.heuristic:30s} "
            f"start={start_str:18s} "
            f"cash=${res.cash_usd:9,.2f} "
            f"final={final_str:10s} "
            f"profit={profit_str:10s} "
            f"len={str(res.path_len):>3s} "
            f"time={res.duration_sec:6.3f}s"
        )
    
    log_and_write(f"\nCompleted: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_and_write(f"\nSaved experiment log to: {out_path}")


if __name__ == "__main__":
    main()
