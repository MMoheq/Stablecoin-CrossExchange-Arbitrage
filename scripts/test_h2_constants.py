#!/usr/bin/env python3
"""
Test script to gather data on h2_slippage heuristic with different constant values.

This script tests various combinations of:
- SLIPPAGE_HEURISTIC_WEIGHT (w_slip)
- SLIPPAGE_THRESHOLD_BPS (threshold)
- UNKNOWN_SLIPPAGE_PENALTY (penalty for missing data)

Results are collected and displayed in tables.
"""

import sys
import os
from pathlib import Path
import json
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from typing import Optional, Dict, Any, List, Tuple
from scripts.astar_vol import astar_best_path_with_liquidity, PlanResult, NodeId
from scripts import h2_slippage
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


# Test configurations organized into batches
TEST_CONFIGS = {
    "baseline": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 0.5,
        "SLIPPAGE_THRESHOLD_BPS": 10.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 50.0,
    },
    # Test different weights
    "weight_low": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 0.1,
        "SLIPPAGE_THRESHOLD_BPS": 10.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 50.0,
    },
    "weight_medium": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 0.25,
        "SLIPPAGE_THRESHOLD_BPS": 10.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 50.0,
    },
    "weight_high": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 1.0,
        "SLIPPAGE_THRESHOLD_BPS": 10.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 50.0,
    },
    "weight_very_high": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 2.0,
        "SLIPPAGE_THRESHOLD_BPS": 10.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 50.0,
    },
    # Test different thresholds
    "threshold_low": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 0.5,
        "SLIPPAGE_THRESHOLD_BPS": 5.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 50.0,
    },
    "threshold_medium": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 0.5,
        "SLIPPAGE_THRESHOLD_BPS": 20.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 50.0,
    },
    "threshold_high": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 0.5,
        "SLIPPAGE_THRESHOLD_BPS": 50.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 50.0,
    },
    # Test different unknown penalties
    "penalty_low": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 0.5,
        "SLIPPAGE_THRESHOLD_BPS": 10.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 10.0,
    },
    "penalty_medium": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 0.5,
        "SLIPPAGE_THRESHOLD_BPS": 10.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 25.0,
    },
    "penalty_high": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 0.5,
        "SLIPPAGE_THRESHOLD_BPS": 10.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 100.0,
    },
    # Combined variations
    "aggressive": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 1.0,
        "SLIPPAGE_THRESHOLD_BPS": 5.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 100.0,
    },
    "conservative": {
        "SLIPPAGE_HEURISTIC_WEIGHT": 0.25,
        "SLIPPAGE_THRESHOLD_BPS": 20.0,
        "UNKNOWN_SLIPPAGE_PENALTY": 25.0,
    },
}

# Organize configs into batches for parallel execution
BATCHES = {
    "baseline": ["baseline"],
    "weights": ["weight_low", "weight_medium", "weight_high", "weight_very_high"],
    "thresholds": ["threshold_low", "threshold_medium", "threshold_high"],
    "penalties": ["penalty_low", "penalty_medium", "penalty_high"],
    "combined": ["aggressive", "conservative"],
}


# Thread-local storage for constants (to allow parallel execution)
_thread_local = threading.local()


def run_search_with_constants(
    config_name: str,
    config: Dict[str, float],
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 6,
    max_time_sec: float = 1800.0,
) -> Tuple[Optional[PlanResult], float, str]:
    """
    Run A* search with modified h2_slippage constants.
    
    Uses thread-local storage to allow parallel execution.
    
    Returns:
        (result, execution_time_sec, config_name)
    """
    # Save original constants
    original_weight = h2_slippage.SLIPPAGE_HEURISTIC_WEIGHT
    original_threshold = h2_slippage.SLIPPAGE_THRESHOLD_BPS
    original_penalty = h2_slippage.UNKNOWN_SLIPPAGE_PENALTY
    
    # Store in thread-local for this thread
    _thread_local.config = config
    
    try:
        # Modify constants for this thread
        # Note: This is not thread-safe for parallel execution of searches
        # We'll run batches sequentially but allow configs within a batch to queue
        h2_slippage.SLIPPAGE_HEURISTIC_WEIGHT = config["SLIPPAGE_HEURISTIC_WEIGHT"]
        h2_slippage.SLIPPAGE_THRESHOLD_BPS = config["SLIPPAGE_THRESHOLD_BPS"]
        h2_slippage.UNKNOWN_SLIPPAGE_PENALTY = config["UNKNOWN_SLIPPAGE_PENALTY"]
        
        # Run search
        start_time = time.time()
        result = astar_best_path_with_liquidity(
            start_node=start_node,
            liquid_cash_usd=liquid_cash_usd,
            max_depth=max_depth,
            max_time_sec=max_time_sec,
            min_profit_usd=0.0,
            heuristic="h2_slippage",
        )
        execution_time = time.time() - start_time
        
        return result, execution_time, config_name
        
    finally:
        # Restore original constants
        h2_slippage.SLIPPAGE_HEURISTIC_WEIGHT = original_weight
        h2_slippage.SLIPPAGE_THRESHOLD_BPS = original_threshold
        h2_slippage.UNKNOWN_SLIPPAGE_PENALTY = original_penalty


def format_path(result: PlanResult) -> str:
    """Format path as string."""
    return " -> ".join(f"{ex}:{c}" for (ex, c) in result.path)


class ResultLogger:
    """Logger for test results with file persistence."""
    
    def __init__(self, log_dir: Path = None, test_params: Dict[str, Any] = None):
        """Initialize logger with log directory and test parameters."""
        if log_dir is None:
            log_dir = project_root / "results" / "h2_constant_tests"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir = log_dir
        
        # Create timestamped log files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.json_log = log_dir / f"h2_test_results_{timestamp}.json"
        self.text_log = log_dir / f"h2_test_results_{timestamp}.txt"
        
        # Initialize JSON log with metadata
        self.results = {
            "start_time": datetime.now().isoformat(),
            "test_parameters": test_params or {},
            "test_configs": {},
            "results": [],
            "batches_completed": [],
            "batches_pending": [],
            "status": "running",
        }
        self._write_json()
        
        # Initialize text log
        with open(self.text_log, "w") as f:
            f.write("=" * 120 + "\n")
            f.write("H2_SLIPPAGE CONSTANT TESTING - RESULTS LOG\n")
            f.write("=" * 120 + "\n")
            f.write(f"Start time: {datetime.now().isoformat()}\n")
            f.write(f"JSON log: {self.json_log}\n")
            f.write("\n")
            f.write("TEST PARAMETERS:\n")
            f.write("-" * 120 + "\n")
            if test_params:
                for key, value in test_params.items():
                    f.write(f"  {key}: {value}\n")
            else:
                f.write("  (No parameters logged)\n")
            f.write("-" * 120 + "\n")
            f.write("\n")
            f.write("TEST CONFIGURATIONS:\n")
            f.write("-" * 120 + "\n")
            f.write("  Testing variations of h2_slippage constants:\n")
            f.write("    - SLIPPAGE_HEURISTIC_WEIGHT (w_slip): Controls heuristic influence\n")
            f.write("    - SLIPPAGE_THRESHOLD_BPS: Acceptable slippage threshold\n")
            f.write("    - UNKNOWN_SLIPPAGE_PENALTY: Penalty when order book data unavailable\n")
            f.write("-" * 120 + "\n\n")
    
    def log_config(self, config_name: str, config: Dict[str, float]):
        """Log a test configuration."""
        self.results["test_configs"][config_name] = config
        self._write_json()
    
    def log_result(self, result_dict: Dict[str, Any]):
        """Log a single test result."""
        result_dict["timestamp"] = datetime.now().isoformat()
        self.results["results"].append(result_dict)
        self._write_json()
        
        # Also write to text log
        with open(self.text_log, "a") as f:
            f.write(f"\n[{result_dict['timestamp']}] Config: {result_dict['config']}\n")
            f.write(f"  Weight: {result_dict['weight']}, Threshold: {result_dict['threshold']}, Penalty: {result_dict['penalty']}\n")
            if result_dict["found"]:
                f.write(f"  ✓ Profit: ${result_dict['profit']:.2f} ({result_dict['profit_pct']:.4f}%)\n")
                f.write(f"  Path: {result_dict['path']}\n")
                f.write(f"  Execution time: {result_dict['execution_time']:.2f}s\n")
            else:
                f.write(f"  ✗ No profitable path found\n")
                f.write(f"  Execution time: {result_dict['execution_time']:.2f}s\n")
            f.write("\n")
    
    def log_batch_start(self, batch_name: str):
        """Log the start of a batch."""
        if batch_name not in self.results["batches_completed"]:
            self.results["batches_pending"].append(batch_name)
        self._write_json()
        
        with open(self.text_log, "a") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Batch: {batch_name} - Started at {datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n")
    
    def log_batch_complete(self, batch_name: str):
        """Log the completion of a batch."""
        if batch_name in self.results["batches_pending"]:
            self.results["batches_pending"].remove(batch_name)
        if batch_name not in self.results["batches_completed"]:
            self.results["batches_completed"].append(batch_name)
        self._write_json()
        
        with open(self.text_log, "a") as f:
            f.write(f"\nBatch: {batch_name} - Completed at {datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n")
    
    def finalize(self, all_results: List[Dict[str, Any]]):
        """Finalize logging with summary."""
        self.results["end_time"] = datetime.now().isoformat()
        self.results["status"] = "completed"
        self.results["total_configs"] = len(all_results)
        self.results["successful_configs"] = sum(1 for r in all_results if r.get("found", False))
        self._write_json()
        
        # Write summary to text log
        with open(self.text_log, "a") as f:
            f.write("\n" + "=" * 120 + "\n")
            f.write("TESTING COMPLETE\n")
            f.write("=" * 120 + "\n")
            f.write(f"End time: {datetime.now().isoformat()}\n")
            f.write(f"Total configs tested: {len(all_results)}\n")
            f.write(f"Successful: {self.results['successful_configs']}\n")
            f.write(f"Failed: {len(all_results) - self.results['successful_configs']}\n")
            f.write(f"Batches completed: {', '.join(self.results['batches_completed'])}\n")
            if self.results["batches_pending"]:
                f.write(f"Batches pending: {', '.join(self.results['batches_pending'])}\n")
            f.write("\n")
    
    def _write_json(self):
        """Write JSON log file."""
        with open(self.json_log, "w") as f:
            json.dump(self.results, f, indent=2)
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress information."""
        return {
            "status": self.results["status"],
            "batches_completed": len(self.results["batches_completed"]),
            "batches_pending": len(self.results["batches_pending"]),
            "results_count": len(self.results["results"]),
            "json_log": str(self.json_log),
            "text_log": str(self.text_log),
        }


def run_single_config(
    config_name: str,
    config: Dict[str, float],
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int,
    logger: Optional[ResultLogger] = None,
) -> Dict[str, Any]:
    """Run a single configuration and return result dict."""
    result, exec_time, _ = run_search_with_constants(
        config_name=config_name,
        config=config,
        start_node=start_node,
        liquid_cash_usd=liquid_cash_usd,
        max_depth=max_depth,
    )
    
    if result:
        profit = result.final_cash_usd - liquid_cash_usd
        profit_pct = (profit / liquid_cash_usd) * 100.0
        path_str = format_path(result)
        
        result_dict = {
            "config": config_name,
            "weight": config["SLIPPAGE_HEURISTIC_WEIGHT"],
            "threshold": config["SLIPPAGE_THRESHOLD_BPS"],
            "penalty": config["UNKNOWN_SLIPPAGE_PENALTY"],
            "final_cash": result.final_cash_usd,
            "profit": profit,
            "profit_pct": profit_pct,
            "path_length": len(result.path),
            "path": path_str,
            "execution_time": exec_time,
            "found": True,
        }
    else:
        result_dict = {
            "config": config_name,
            "weight": config["SLIPPAGE_HEURISTIC_WEIGHT"],
            "threshold": config["SLIPPAGE_THRESHOLD_BPS"],
            "penalty": config["UNKNOWN_SLIPPAGE_PENALTY"],
            "final_cash": None,
            "profit": None,
            "profit_pct": None,
            "path_length": None,
            "path": None,
            "execution_time": exec_time,
            "found": False,
        }
    
    # Log result immediately
    if logger:
        logger.log_result(result_dict)
    
    return result_dict


def run_test_batch(
    batch_name: str,
    config_names: List[str],
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int,
    max_workers: int = 3,
    sequential: bool = True,
    logger: Optional[ResultLogger] = None,
) -> List[Dict[str, Any]]:
    """
    Run a batch of configurations (sequentially or in parallel).
    
    Args:
        batch_name: Name of the batch (for logging)
        config_names: List of config names to run
        start_node: Starting node
        liquid_cash_usd: Initial capital
        max_depth: Maximum search depth
        max_workers: Number of parallel workers (if sequential=False)
        sequential: If True, run sequentially; if False, run in parallel
    
    Returns:
        List of result dictionaries
    """
    print(f"\n{'='*60}")
    print(f"Batch: {batch_name} ({len(config_names)} configs)")
    if not sequential:
        print(f"Running with {max_workers} parallel workers")
    print(f"{'='*60}")
    
    # Log batch start
    if logger:
        logger.log_batch_start(batch_name)
    
    results = []
    
    if sequential:
        # Run sequentially (safer for shared module constants)
        for config_name in config_names:
            config = TEST_CONFIGS[config_name]
            print(f"  Running {config_name}...", end=" ", flush=True)
            
            result_dict = run_single_config(
                config_name=config_name,
                config=config,
                start_node=start_node,
                liquid_cash_usd=liquid_cash_usd,
                max_depth=max_depth,
                logger=logger,
            )
            
            results.append(result_dict)
            if result_dict["found"]:
                print(f"✓ ${result_dict['profit']:.2f} ({result_dict['profit_pct']:.4f}%)")
            else:
                print("✗ No profitable path")
    else:
        # Run in parallel (with proper synchronization)
        results_lock = threading.Lock()
        
        def run_and_collect(config_name: str):
            """Run a single config and collect result."""
            config = TEST_CONFIGS[config_name]
            print(f"  Starting {config_name}...", flush=True)
            
            result_dict = run_single_config(
                config_name=config_name,
                config=config,
                start_node=start_node,
                liquid_cash_usd=liquid_cash_usd,
                max_depth=max_depth,
                logger=logger,
            )
            
            with results_lock:
                results.append(result_dict)
                if result_dict["found"]:
                    print(f"  ✓ {config_name}: ${result_dict['profit']:.2f} ({result_dict['profit_pct']:.4f}%)")
                else:
                    print(f"  ✗ {config_name}: No profitable path")
        
        # Run in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_and_collect, config_name): config_name
                for config_name in config_names
            }
            
            # Wait for all to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    config_name = futures[future]
                    print(f"  ✗ {config_name}: Error - {e}")
                    with results_lock:
                        results.append({
                            "config": config_name,
                            "weight": None,
                            "threshold": None,
                            "penalty": None,
                            "final_cash": None,
                            "profit": None,
                            "profit_pct": None,
                            "path_length": None,
                            "path": None,
                            "execution_time": 0.0,
                            "found": False,
                        })
    
    # Log batch completion
    if logger:
        logger.log_batch_complete(batch_name)
    
    return results


def run_test_suite(
    start_node: NodeId = ("binance", "USDT"),
    liquid_cash_usd: float = 10000.0,
    max_depth: int = 6,
    batch_names: Optional[List[str]] = None,
    max_workers: int = 3,
    parallel: bool = False,
    logger: Optional[ResultLogger] = None,
) -> List[Dict[str, Any]]:
    """
    Run test configurations in batches (parallel execution within batches).
    
    Args:
        start_node: Starting node
        liquid_cash_usd: Initial capital
        max_depth: Maximum search depth
        batch_names: List of batch names to run (None = all batches)
        max_workers: Number of parallel workers per batch
    
    Returns:
        List of result dictionaries
    """
    all_results = []
    
    print(f"Testing h2_slippage constants with:")
    print(f"  Start node: {start_node[0]}:{start_node[1]}")
    print(f"  Initial capital: ${liquid_cash_usd:,.2f}")
    print(f"  Max depth: {max_depth}")
    print(f"  Parallel workers per batch: {max_workers}")
    
    if batch_names is None:
        batch_names = list(BATCHES.keys())
    
    total_configs = sum(len(BATCHES[b]) for b in batch_names)
    print(f"  Total configurations: {total_configs}")
    
    if logger:
        print(f"  Log files:")
        print(f"    JSON: {logger.json_log}")
        print(f"    Text: {logger.text_log}")
    print()
    
    # Run batches sequentially (but parallel within each batch)
    for batch_name in batch_names:
        if batch_name not in BATCHES:
            print(f"Warning: Unknown batch '{batch_name}', skipping")
            continue
        
        config_names = BATCHES[batch_name]
        batch_results = run_test_batch(
            batch_name=batch_name,
            config_names=config_names,
            start_node=start_node,
            liquid_cash_usd=liquid_cash_usd,
            max_depth=max_depth,
            max_workers=max_workers,
            sequential=not parallel,
            logger=logger,
        )
        all_results.extend(batch_results)
    
    # Finalize logging
    if logger:
        logger.finalize(all_results)
        progress = logger.get_progress()
        print(f"\nProgress saved:")
        print(f"  JSON log: {progress['json_log']}")
        print(f"  Text log: {progress['text_log']}")
        print(f"  Results: {progress['results_count']}/{total_configs}")
    
    return all_results


def print_results_table(results: List[Dict[str, Any]]):
    """Print results in formatted tables."""
    
    # Filter to only successful results for main table
    successful = [r for r in results if r["found"]]
    
    if not successful:
        print("\n❌ No successful searches found!")
        return
    
    # Main results table
    print("\n" + "=" * 120)
    print("H2_SLIPPAGE CONSTANT TESTING RESULTS")
    print("=" * 120)
    print()
    
    # Header
    header = (
        f"{'Config':<20} "
        f"{'Weight':<8} "
        f"{'Threshold':<10} "
        f"{'Penalty':<8} "
        f"{'Profit ($)':<12} "
        f"{'Profit %':<10} "
        f"{'Path Len':<10} "
        f"{'Time (s)':<10} "
        f"{'Path':<50}"
    )
    print(header)
    print("-" * 120)
    
    # Sort by profit (descending)
    successful_sorted = sorted(successful, key=lambda x: x["profit"] or 0, reverse=True)
    
    for r in successful_sorted:
        profit_str = f"${r['profit']:.2f}" if r['profit'] else "N/A"
        profit_pct_str = f"{r['profit_pct']:.4f}%" if r['profit_pct'] else "N/A"
        path_str = r['path'][:47] + "..." if r['path'] and len(r['path']) > 50 else (r['path'] or "N/A")
        
        row = (
            f"{r['config']:<20} "
            f"{r['weight']:<8.2f} "
            f"{r['threshold']:<10.1f} "
            f"{r['penalty']:<8.1f} "
            f"{profit_str:<12} "
            f"{profit_pct_str:<10} "
            f"{r['path_length']:<10} "
            f"{r['execution_time']:<10.2f} "
            f"{path_str:<50}"
        )
        print(row)
    
    print()
    
    # Summary statistics
    print("=" * 120)
    print("SUMMARY STATISTICS")
    print("=" * 120)
    print()
    
    profits = [r["profit"] for r in successful if r["profit"] is not None]
    if profits:
        print(f"Total successful searches: {len(successful)}/{len(results)}")
        print(f"Average profit: ${sum(profits) / len(profits):.2f}")
        print(f"Max profit: ${max(profits):.2f}")
        print(f"Min profit: ${min(profits):.2f}")
        print(f"Profit range: ${max(profits) - min(profits):.2f}")
        print()
        
        # Find best configuration
        best = max(successful, key=lambda x: x["profit"] or 0)
        print(f"Best configuration: {best['config']}")
        print(f"  Weight: {best['weight']}")
        print(f"  Threshold: {best['threshold']} bps")
        print(f"  Penalty: {best['penalty']}")
        print(f"  Profit: ${best['profit']:.2f} ({best['profit_pct']:.4f}%)")
        print(f"  Path: {best['path']}")
        print()
    
    # Group by constant type
    print("=" * 120)
    print("ANALYSIS BY CONSTANT TYPE")
    print("=" * 120)
    print()
    
    # Group by weight
    print("By SLIPPAGE_HEURISTIC_WEIGHT:")
    print(f"{'Weight':<10} {'Avg Profit':<15} {'Max Profit':<15} {'Configs':<10}")
    print("-" * 50)
    weight_groups = {}
    for r in successful:
        w = r["weight"]
        if w not in weight_groups:
            weight_groups[w] = []
        weight_groups[w].append(r)
    
    for weight in sorted(weight_groups.keys()):
        group = weight_groups[weight]
        profits = [r["profit"] for r in group if r["profit"] is not None]
        if profits:
            avg = sum(profits) / len(profits)
            max_p = max(profits)
            print(f"{weight:<10.2f} ${avg:<14.2f} ${max_p:<14.2f} {len(group):<10}")
    print()
    
    # Group by threshold
    print("By SLIPPAGE_THRESHOLD_BPS:")
    print(f"{'Threshold':<12} {'Avg Profit':<15} {'Max Profit':<15} {'Configs':<10}")
    print("-" * 52)
    threshold_groups = {}
    for r in successful:
        t = r["threshold"]
        if t not in threshold_groups:
            threshold_groups[t] = []
        threshold_groups[t].append(r)
    
    for threshold in sorted(threshold_groups.keys()):
        group = threshold_groups[threshold]
        profits = [r["profit"] for r in group if r["profit"] is not None]
        if profits:
            avg = sum(profits) / len(profits)
            max_p = max(profits)
            print(f"{threshold:<12.1f} ${avg:<14.2f} ${max_p:<14.2f} {len(group):<10}")
    print()
    
    # Group by penalty
    print("By UNKNOWN_SLIPPAGE_PENALTY:")
    print(f"{'Penalty':<10} {'Avg Profit':<15} {'Max Profit':<15} {'Configs':<10}")
    print("-" * 50)
    penalty_groups = {}
    for r in successful:
        p = r["penalty"]
        if p not in penalty_groups:
            penalty_groups[p] = []
        penalty_groups[p].append(r)
    
    for penalty in sorted(penalty_groups.keys()):
        group = penalty_groups[penalty]
        profits = [r["profit"] for r in group if r["profit"] is not None]
        if profits:
            avg = sum(profits) / len(profits)
            max_p = max(profits)
            print(f"{penalty:<10.1f} ${avg:<14.2f} ${max_p:<14.2f} {len(group):<10}")
    print()
    
    # Failed searches
    failed = [r for r in results if not r["found"]]
    if failed:
        print("=" * 120)
        print(f"FAILED SEARCHES ({len(failed)})")
        print("=" * 120)
        for r in failed:
            print(f"  {r['config']}: weight={r['weight']}, threshold={r['threshold']}, penalty={r['penalty']}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test h2_slippage heuristic with different constant values"
    )
    parser.add_argument(
        "--batch",
        nargs="+",
        choices=list(BATCHES.keys()) + ["all"],
        default=["all"],
        help="Which batches to run (default: all)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel workers per batch (default: 1 = sequential)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Enable parallel execution within batches (default: sequential for safety)",
    )
    parser.add_argument(
        "--start-node",
        default="binance:USDT",
        help="Starting node in format 'exchange:coin' (default: binance:USDT)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=10000.0,
        help="Initial capital in USD (default: 10000.0)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=6,
        help="Maximum search depth (default: 6)",
    )
    
    args = parser.parse_args()
    
    # Parse start node
    try:
        ex, coin = args.start_node.split(":")
        start_node = (ex, coin)
    except ValueError:
        print(f"Error: Invalid start node format '{args.start_node}'. Expected 'exchange:coin'")
        return
    
    # Determine batches to run
    if "all" in args.batch:
        batch_names = None  # Run all
    else:
        batch_names = args.batch
    
    print("H2_SLIPPAGE Constant Testing Suite")
    print("=" * 120)
    print()
    
    # Initialize logger with test parameters
    test_params = {
        "start_node": f"{start_node[0]}:{start_node[1]}",
        "initial_capital_usd": args.capital,
        "max_depth": args.max_depth,
        "max_time_sec": 1800.0,
        "min_profit_usd": 0.0,
        "batches": batch_names if batch_names else "all",
        "parallel_execution": args.parallel,
        "workers_per_batch": args.workers,
        "total_configurations": sum(len(BATCHES[b]) for b in (batch_names if batch_names else BATCHES.keys())),
    }
    logger = ResultLogger(test_params=test_params)
    
    # Log all test configurations
    for config_name, config in TEST_CONFIGS.items():
        logger.log_config(config_name, config)
    
    # Run test suite
    results = run_test_suite(
        start_node=start_node,
        liquid_cash_usd=args.capital,
        max_depth=args.max_depth,
        batch_names=batch_names,
        max_workers=args.workers,
        parallel=args.parallel,
        logger=logger,
    )
    
    # Print results
    print_results_table(results)
    
    print()
    print("=" * 120)
    print("Testing complete!")
    print("=" * 120)


if __name__ == "__main__":
    main()

