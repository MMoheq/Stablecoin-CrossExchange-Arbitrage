# ==============================================================================
# h4_chaincongestion_exchange_risk.py
# — Chain congestion (kickback risk) + exchange reliability / freeze-risk
# ==============================================================================

from __future__ import annotations

from functools import lru_cache
from typing import Tuple

from scripts.graph import build_graph
from scripts.transfer_time import (
    get_chain_time_seconds,
    get_user_execution_overhead_seconds,
)

# Node is (exchange, coin)
NodeId = Tuple[str, str]

# Build graph ONCE and reuse
_NODES, _ADJ = build_graph()


# ---------------------------------------------------------------------------
# 0. Heuristic tuning parameters
# ---------------------------------------------------------------------------

# λ_chain: how much we care about "fast chain = risky"
CHAIN_HEURISTIC_WEIGHT: float = 1.0

# λ_exchange: how much we care about exchange freeze / reliability risk
EXCHANGE_HEURISTIC_WEIGHT: float = 1.0

# Fallback penalties
UNKNOWN_CHAIN_PENALTY: float = 5.0
UNKNOWN_EXCHANGE_PENALTY: float = 5.0


# ---------------------------------------------------------------------------
# 1. Chain congestion / kickback-risk model (h4-style)
# ---------------------------------------------------------------------------

def _extract_chain_name(edge: dict) -> str | None:
    """Infer blockchain/network name from an edge."""
    for key in ("chain", "network", "withdraw_chain"):
        val = edge.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().upper()
    return None


@lru_cache(maxsize=None)
def _fastest_transfer_time_for_node(node: NodeId) -> float | None:
    """
    For a given node (exchange, coin), look at outgoing transfer edges and
    estimate the **fastest** effective hop in seconds, using transfer_time.py.

    Cached so each node is computed at most once per run.
    """
    outgoing_edges = _ADJ.get(node, [])

    raw_times: list[float] = []

    for e in outgoing_edges:
        if e.get("kind") != "transfer":
            continue

        chain_name = _extract_chain_name(e)

        chain_time_sec = None
        if chain_name is not None:
            chain_time_sec = get_chain_time_seconds(chain_name)

        # Fallback: edge's own "transfer_time_sec" if chain isn't recognized
        if chain_time_sec is None:
            tt = e.get("transfer_time_sec")
            if isinstance(tt, (int, float)) and tt > 0:
                chain_time_sec = float(tt)

        if chain_time_sec is None:
            continue

        raw_times.append(chain_time_sec)

    if not raw_times:
        # No valid transfer timing information
        return None

    fastest_chain_sec = min(raw_times)

    # Add user/UI execution overhead (login, confirmations, etc.).
    effective_sec = fastest_chain_sec + get_user_execution_overhead_seconds()
    return effective_sec


def estimate_chain_kickback_risk_score(
    exchange_name: str,
    coin: str,
    remaining_time_sec: float,
) -> float:
    """
    Kickback / timing risk score in [0, 1]:

      * 1.0 ⇒ very fast transfers (high risk of chasing fleeting arb)
      * 0.0 ⇒ very slow / borderline transfers (you likely won't chase them)
    """
    if remaining_time_sec <= 0:
        return 0.0

    node: NodeId = (exchange_name, coin)
    fastest_effective_sec = _fastest_transfer_time_for_node(node)

    # No transfer info ⇒ treat as no extra chain risk for this heuristic
    if fastest_effective_sec is None:
        return 0.0

    ratio = fastest_effective_sec / remaining_time_sec

    # If even the fastest hop is longer than the remaining window,
    # we won't chase fast arb here → low extra risk.
    if ratio >= 1.0:
        return 0.0

    # Fast chain ⇒ small ratio ⇒ high risk_score (= 1 - ratio)
    risk_score = 1.0 - ratio

    # Clamp to [0, 1]
    if risk_score < 0.0:
        risk_score = 0.0
    elif risk_score > 1.0:
        risk_score = 1.0

    return risk_score


# Backwards-compatible alias (in case anything still imports the old name)
def estimate_chain_reliability_score(
    exchange_name: str,
    coin: str,
    remaining_time_sec: float,
) -> float:
    """Alias for older name; kept for compatibility."""
    return estimate_chain_kickback_risk_score(exchange_name, coin, remaining_time_sec)


def chain_congestion_heuristic_cost(
    exchange_name: str,
    coin: str,
    remaining_time_sec: float,
) -> float:
    """
    Chain component h4(n) for node n = (exchange, coin).

    FAST chains (short transfer times) → HIGH cost
    SLOW / borderline chains → LOW or zero cost
    """
    risk_score = estimate_chain_kickback_risk_score(
        exchange_name=exchange_name,
        coin=coin,
        remaining_time_sec=remaining_time_sec,
    )

    if not isinstance(risk_score, (int, float)):
        return UNKNOWN_CHAIN_PENALTY

    penalty = CHAIN_HEURISTIC_WEIGHT * float(risk_score)
    return max(0.0, penalty)


# ---------------------------------------------------------------------------
# 2. Exchange reliability / freeze-risk model (h5-style)
# ---------------------------------------------------------------------------

# Scores are normalized to [0, 1].
# Higher = more reliable (lower freeze risk).
EXCHANGE_RELIABILITY_SCORE = {
    "binance": 0.9,
    "kraken":  0.9,
    "kucoin":  0.6,
    "bybit":   0.4,
}


def estimate_exchange_reliability_score(
    exchange_name: str,
) -> float:
    """
    Return a normalized exchange reliability score in [0, 1].

    Higher = more reliable (lower freeze risk).
    """
    score = EXCHANGE_RELIABILITY_SCORE.get(exchange_name)

    if score is None:
        return 0.0  # unknown exchange = very risky

    # Clamp for safety
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0

    return score


def exchange_risk_heuristic_cost(
    exchange_name: str,
) -> float:
    """
    Exchange component h5(n) for node n = (exchange, coin).

    Penalizes exchanges with higher operational / freeze risk.
    """
    score = estimate_exchange_reliability_score(exchange_name)

    if score <= 0:
        return UNKNOWN_EXCHANGE_PENALTY

    # Lower reliability → higher penalty
    penalty = EXCHANGE_HEURISTIC_WEIGHT * (1.0 - score)
    return penalty


# ---------------------------------------------------------------------------
# 3. Combined chain + exchange heuristic
# ---------------------------------------------------------------------------

def chain_exchange_risk_heuristic_cost(
    exchange_name: str,
    coin: str,
    remaining_time_sec: float,
) -> float:
    """
    Combined heuristic for node n = (exchange, coin).

    h_combined(n) = h_chain(n) + h_exchange(n)

    Where:
      - h_chain penalizes FAST chains (kickback / timing risk)
      - h_exchange penalizes risky exchanges (freeze / halt risk)

    You can tune the relative importance via:
      - CHAIN_HEURISTIC_WEIGHT
      - EXCHANGE_HEURISTIC_WEIGHT
    """
    h_chain = chain_congestion_heuristic_cost(
        exchange_name=exchange_name,
        coin=coin,
        remaining_time_sec=remaining_time_sec,
    )

    h_exchange = exchange_risk_heuristic_cost(exchange_name)

    return h_chain + h_exchange