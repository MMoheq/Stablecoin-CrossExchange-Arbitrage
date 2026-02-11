# ==============================================================
# test_2hop_max_baseline.py — Test 2-hop max depth baseline
# ==============================================================

"""
Test 2-hop max depth baseline (A* with h=0, max_depth=2).
- Starts from 1 node per exchange
- Can jump to any internal coin in the same exchange (trade)
- Then can jump to that coin on another exchange (transfer)
- That's it (max depth = 2)

Writes results to results/2hop_max_baseline.txt
"""

from __future__ import annotations

import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Set

# Make sure we can import from the project root
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId
from scripts.baseline_algorithms import two_hop_max_depth_search, PlanResult
from scripts.data import EXCHANGES

# Configuration
CASH_USD: float = 10_000.0
MAX_TIME_SEC: float = 60.0  # 1 minute per search (should be fast with depth=2)
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


def pick_one_node_per_exchange(nodes: Dict[NodeId, dict]) -> List[NodeId]:
    """
    Pick exactly one node per exchange.
    Prefers common stablecoins (USDT, USDC, BUSD) if available.
    """
    exchange_to_nodes: Dict[str, List[NodeId]] = {}
    
    # Group nodes by exchange
    for node in nodes.keys():
        ex, coin = node
        if ex not in exchange_to_nodes:
            exchange_to_nodes[ex] = []
        exchange_to_nodes[ex].append(node)
    
    # Prefer common coins in order: USDT, USDC, BUSD, then any
    preferred_coins = ["USDT", "USDC", "BUSD", "DAI", "USDP"]
    
    selected: List[NodeId] = []
    for ex in sorted(exchange_to_nodes.keys()):
        candidates = exchange_to_nodes[ex]
        
        # Try to find a preferred coin
        chosen = None
        for coin in preferred_coins:
            for node in candidates:
                if node[1] == coin:
                    chosen = node
                    break
            if chosen:
                break
        
        # If no preferred coin found, just take the first one
        if not chosen:
            chosen = candidates[0]
        
        selected.append(chosen)
    
    return selected


def run_2hop_test(start_node: NodeId) -> TestResult:
    """Run 2-hop max depth search from a start node."""
    t0 = time.perf_counter()
    error: Optional[str] = None
    result: Optional[PlanResult] = None

    try:
        result = two_hop_max_depth_search(
            start_node=start_node,
            liquid_cash_usd=CASH_USD,
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
    out_path = results_dir / "2hop_max_baseline.txt"
    
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
        f.write("=== 2-Hop Max Depth Baseline Test (A* with h=0, max_depth=2) ===\n")
        f.write(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Configuration:\n")
        f.write(f"  Cash: ${CASH_USD:,.2f}\n")
        f.write(f"  Max depth: 2 (strict limit)\n")
        f.write(f"  Max time per search: {MAX_TIME_SEC:.1f}s\n")
        f.write(f"  Min profit: ${MIN_PROFIT_USD:.2f}\n")
        f.write(f"  Strategy: Start → (trade within exchange) → (transfer to another exchange)\n\n")
    
    log_and_write("=== Building graph ===")
    nodes, _ = build_graph()
    log_and_write(f"Graph has {len(nodes)} nodes")

    # Choose one node per exchange
    start_nodes = pick_one_node_per_exchange(nodes)
    log_and_write("\nUsing start nodes (one per exchange):")
    for n in start_nodes:
        log_and_write(f"  - {n[0]}:{n[1]}")

    log_and_write(f"\nRunning with {MAX_WORKERS} parallel workers\n")

    # Run tests in parallel
    def run_task(start: NodeId) -> TestResult:
        """Wrapper function for parallel execution."""
        start_str = f"{start[0]}:{start[1]}"
        log_and_write(f"\n[START] Running 2-hop max from {start_str} (cash=${CASH_USD:,.2f}) ...", flush=True)
        
        res = run_2hop_test(start)
        
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
        # Show the full path for successful results (should be exactly 2 nodes for 2-hop)
        if res.success and res.path:
            path_str = " -> ".join(f"({ex},{coin})" for (ex, coin) in res.path)
            log_and_write(f"         Path: {path_str}")
    
    log_and_write(f"\nCompleted: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_and_write(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()

