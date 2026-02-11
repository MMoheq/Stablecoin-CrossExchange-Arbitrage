# ==============================================================
# test_dijkstra_baseline.py — Test Dijkstra's algorithm (A* with h=0)
# ==============================================================

"""
Test Dijkstra's algorithm baseline (A* with h(n)=0, no depth limit).
Writes results to results/dijkstra_baseline.txt
"""

from __future__ import annotations

import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List

# Make sure we can import from the project root
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId
from scripts.baseline_algorithms import dijkstra_like_search, PlanResult

# Configuration
CASH_USD: float = 10_000.0
MAX_DEPTH: int = 6  # No strict limit, but reasonable max
MAX_TIME_SEC: float = 180.0  # 3 minutes per search
MIN_PROFIT_USD: float = 0.0
MAX_WORKERS: int = 4


@dataclass
class TestResult:
    start_node: NodeId
    final_cash_usd: Optional[float]
    profit_usd: Optional[float]
    path_len: Optional[int]
    path: Optional[List[NodeId]]  # Full path: [(exchange, coin), ...]
    duration_sec: float
    success: bool
    error: Optional[str]


def pick_start_nodes(nodes: Dict[NodeId, dict]) -> List[NodeId]:
    """
    Choose a small, fixed set of interesting start nodes for experiments.
    Prefers binance:BUSD, binance:USDT, kraken:USDT if present,
    then fills with a few random ones.
    """
    import random
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

    return preferred[:5]  # Use up to 5 start nodes


def run_dijkstra_test(start_node: NodeId) -> TestResult:
    """Run Dijkstra's algorithm from a start node."""
    t0 = time.perf_counter()
    error: Optional[str] = None
    result: Optional[PlanResult] = None

    try:
        result = dijkstra_like_search(
            start_node=start_node,
            liquid_cash_usd=CASH_USD,
            max_depth=MAX_DEPTH,
            max_time_sec=MAX_TIME_SEC,
            min_profit_usd=MIN_PROFIT_USD,
        )
    except Exception as e:
        error = str(e)

    duration = time.perf_counter() - t0

    if result is None:
        return TestResult(
            start_node=start_node,
            final_cash_usd=None,
            profit_usd=None,
            path_len=None,
            path=None,
            duration_sec=duration,
            success=False,
            error=error or "No profitable path found",
        )

    profit = result.final_cash_usd - CASH_USD

    return TestResult(
        start_node=start_node,
        final_cash_usd=result.final_cash_usd,
        profit_usd=profit,
        path_len=len(result.path),
        path=result.path.copy(),
        duration_sec=duration,
        success=True,
        error=None,
    )


def main() -> None:
    # Setup output file
    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / "dijkstra_baseline.txt"
    
    # Thread-safe file writing
    file_lock = threading.Lock()
    all_results: List[TestResult] = []
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
        f.write("=== Dijkstra's Algorithm Baseline Test (A* with h=0) ===\n")
        f.write(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Configuration:\n")
        f.write(f"  Cash: ${CASH_USD:,.2f}\n")
        f.write(f"  Max depth: {MAX_DEPTH}\n")
        f.write(f"  Max time per search: {MAX_TIME_SEC:.1f}s\n")
        f.write(f"  Min profit: ${MIN_PROFIT_USD:.2f}\n\n")
    
    log_and_write("=== Building graph ===")
    nodes, _ = build_graph()
    log_and_write(f"Graph has {len(nodes)} nodes")

    # Choose starting nodes
    start_nodes = pick_start_nodes(nodes)
    log_and_write("\nUsing start nodes:")
    for n in start_nodes:
        log_and_write(f"  - {n[0]}:{n[1]}")

    log_and_write(f"\nRunning with {MAX_WORKERS} parallel workers\n")

    # Run tests in parallel
    def run_task(start: NodeId) -> TestResult:
        """Wrapper function for parallel execution."""
        start_str = f"{start[0]}:{start[1]}"
        log_and_write(f"\n[START] Running Dijkstra from {start_str} (cash=${CASH_USD:,.2f}) ...", flush=True)
        
        res = run_dijkstra_test(start)
        
        # Thread-safe result storage
        with results_lock:
            all_results.append(res)
        
        # Log result immediately
        if res.success:
            log_and_write(
                f"[DONE] {start_str}: SUCCESS - "
                f"final=${res.final_cash_usd:.2f} "
                f"(profit=${res.profit_usd:.2f}), "
                f"path_len={res.path_len}, "
                f"time={res.duration_sec:.3f}s",
                flush=True
            )
        else:
            log_and_write(
                f"[DONE] {start_str}: FAIL - {res.error} "
                f"(time={res.duration_sec:.3f}s)",
                flush=True
            )
        
        return res
    
    # Execute all tasks in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(run_task, start): start
            for start in start_nodes
        }
        
        # Wait for all to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                start_node = futures[future]
                log_and_write(
                    f"[ERROR] {start_node}: Exception - {str(e)}",
                    flush=True
                )

    # Summary at the end
    log_and_write("\n\n================ SUMMARY ================")
    successes = [r for r in all_results if r.success]
    failures = [r for r in all_results if not r.success]
    
    log_and_write(f"\nTotal tests: {len(all_results)}")
    log_and_write(f"Successes: {len(successes)}")
    log_and_write(f"Failures: {len(failures)}")
    
    if successes:
        avg_profit = sum(r.profit_usd for r in successes if r.profit_usd is not None) / len(successes)
        avg_time = sum(r.duration_sec for r in successes) / len(successes)
        avg_path_len = sum(r.path_len for r in successes if r.path_len is not None) / len(successes)
        
        log_and_write(f"\nAverage profit (successful): ${avg_profit:.2f}")
        log_and_write(f"Average time (successful): {avg_time:.3f}s")
        log_and_write(f"Average path length (successful): {avg_path_len:.2f}")
    
    log_and_write("\n\nDetailed Results:")
    for res in sorted(all_results, key=lambda x: (x.success, x.profit_usd if x.profit_usd else -1), reverse=True):
        start_str = f"{res.start_node[0]}:{res.start_node[1]}"
        status = "OK" if res.success else "FAIL"
        final_str = f"${res.final_cash_usd:.2f}" if res.final_cash_usd is not None else "N/A"
        profit_str = f"${res.profit_usd:.2f}" if res.profit_usd is not None else "N/A"
        log_and_write(
            f"[{status}] start={start_str:18s} "
            f"final={final_str:10s} "
            f"profit={profit_str:10s} "
            f"len={str(res.path_len):>3s} "
            f"time={res.duration_sec:6.3f}s"
        )
        # Show the full path for successful results
        if res.success and res.path:
            path_str = " -> ".join(f"({ex},{coin})" for (ex, coin) in res.path)
            log_and_write(f"         Path: {path_str}")
    
    log_and_write(f"\nCompleted: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_and_write(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()

