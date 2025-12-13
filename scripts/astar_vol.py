# ==========================================================
# astar_volat.py — A* search with volume / liquidity heuristic
# ==========================================================

from __future__ import annotations # lets the file use flexible type hints without worrying about import order.

import heapq
from dataclasses import dataclass #used so we dont use _init_ and _repr_
from math import exp
from typing import Any, Dict, List, Optional, Tuple

from scripts.graph import build_graph            
from scripts.h1_vol import volume_heuristic_cost 


# Node is ("binance", "USDT")
NodeId = Tuple[str, str]


@dataclass(frozen=True)
class SearchState:
    node: NodeId
    depth: int
    elapsed_sec: float  # total time spent along this path so far


@dataclass
class PlanResult:
    path: List[NodeId]              # sequence of nodes
    edges: List[Dict[str, Any]]     # sequence of edge dicts, used for edge costs and extracted from fees.py
    final_cash_usd: float
    profit_usd: float


def _final_cash_from_log_cost(
    initial_cash_usd: float,
    total_log_cost: float,
) -> float:
    """
    Our graph edges store:

        cost = -log(rate)

    where 'rate' is the multiplicative factor on *portfolio value*
    after that step (including fees & withdrawal loss).

    If we sum all costs:

        total_log_cost = sum_i -log(rate_i) = -log(prod_i rate_i)

    then:

        prod_i rate_i = exp(-total_log_cost)
        final_cash    = initial_cash * prod_i rate_i
                       = initial_cash * exp(-total_log_cost)
    """
    return initial_cash_usd * exp(-total_log_cost)


def astar_best_path_with_liquidity(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 6,
    max_time_sec: float = 1800.0,   # 30 minutes by default
    min_profit_usd: float = 0.0,
) -> Optional[PlanResult]:
    """
    A* search over the arbitrage graph that:

      * Starts at `start_node` with `liquid_cash_usd` (USD value).
      * Uses edge["rate"] / edge["cost"] from graph.py
        (these already encode spreads + taker/withdrawal fees).
      * Uses edge["transfer_time_sec"] for timing.
      * Uses volume_heuristic_cost(...) to penalize illiquid markets.
      * Treats ANY reachable node as a potential destination where
        the trader does their last buy, then conceptually sells to USD.
      * Picks the path with the highest final USD value.

    We do **not** require returning to the original node.

    Returns
    -------
    PlanResult or None if no profitable path within constraints.
    """
    # Build graph (nodes: metadata; adj: adjacency list)
    nodes, adj = build_graph()

    if start_node not in nodes:
        raise ValueError(f"Start node {start_node} not present in graph.")

    # Priority queue entries:
    #   (f_score, g_score, counter, SearchState, path_nodes, path_edges)
    #
    # g_score = sum(cost)    (cost = -log(rate), lower is better)
    # h_score = volume_heuristic_cost(...)  (>= 0)
    # f_score = g_score + h_score           (A* objective)
    #
    # We use a monotonically increasing integer 'counter' so that
    # heapq never needs to compare SearchState objects directly.
    start_state = SearchState(node=start_node, depth=0, elapsed_sec=0.0)
    start_g = 0.0

    # Initial heuristic: liquidity at the start node
    start_h = volume_heuristic_cost(
        exchange_name=start_node[0],
        coin=start_node[1],
        order_notional_usd=liquid_cash_usd,
        remaining_time_sec=max_time_sec,
    )
    start_f = start_g + start_h

    frontier: List[
        Tuple[float, float, int, SearchState, List[NodeId], List[Dict[str, Any]]]
    ] = []

    counter = 0  # unique tie-breaker based on position 
    heapq.heappush(frontier, (start_f, start_g, counter, start_state, [start_node], []))
    counter += 1

    # For pruning: best (lowest) g_score we've seen for (node, depth)
    best_g_seen: Dict[Tuple[NodeId, int], float] = {(start_node, 0): start_g}

    best_result: Optional[PlanResult] = None

    while frontier:
        f_score, g_score, _, state, path_nodes, path_edges = heapq.heappop(frontier)
        current_node = state.node

        # Recompute current cash in USD from g_score
        current_cash = _final_cash_from_log_cost(liquid_cash_usd, g_score)

        # Record this as a candidate destination (unless it's the trivial start state)
        if state.depth > 0:
            final_cash = current_cash
            profit = final_cash - liquid_cash_usd

            if final_cash > liquid_cash_usd and profit >= min_profit_usd:
                if best_result is None or final_cash > best_result.final_cash_usd:
                    best_result = PlanResult(
                        path=path_nodes.copy(),
                        edges=path_edges.copy(),
                        final_cash_usd=final_cash,
                        profit_usd=profit,
                    )

        # Stop expanding if depth/time limits reached
        if state.depth >= max_depth or state.elapsed_sec >= max_time_sec:
            continue

        # Expand neighbors
        for edge in adj.get(current_node, []):
            to_node: NodeId = edge["to"]

            # Time update
            dt = float(edge.get("transfer_time_sec", 0.0))
            new_elapsed = state.elapsed_sec + dt
            if new_elapsed > max_time_sec:
                continue

            # Cost update (graph.py already gives us cost = -log(rate))
            edge_cost = float(edge.get("cost", 0.0))
            new_g = g_score + edge_cost
            new_depth = state.depth + 1
            new_state = SearchState(node=to_node, depth=new_depth, elapsed_sec=new_elapsed)

            key = (to_node, new_depth)

            # If we've already reached (node, depth) with a strictly better g (lower),
            # we don't need to expand this worse version.
            if key in best_g_seen and new_g >= best_g_seen[key]:
                continue
            best_g_seen[key] = new_g

            # Heuristic: liquidity cost at the neighbor
            remaining_time = max_time_sec - new_elapsed
            # Current notional after taking this edge:
            new_cash = _final_cash_from_log_cost(liquid_cash_usd, new_g)

            h = volume_heuristic_cost(
                exchange_name=to_node[0],
                coin=to_node[1],
                order_notional_usd=new_cash,
                remaining_time_sec=remaining_time,
            )

            f = new_g + h

            # Extend paths
            new_path_nodes = path_nodes + [to_node]
            new_path_edges = path_edges + [edge]

            # Push with a fresh unique counter so heapq never compares SearchState
            heapq.heappush(
                frontier,
                (f, new_g, counter, new_state, new_path_nodes, new_path_edges),
            )
            counter += 1

    return best_result
