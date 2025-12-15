
"""
Rough end-to-end transfer times per network.

These are *ballpark* values:
- They include on-chain finality + typical exchange processing delay.
- They're meant for comparing routes, not guaranteeing latency.

Units: **seconds**
"""

from typing import Optional, List, Tuple


CHAIN_TRANSFER_TIME_SEC: dict[str, float] = {
    # Fast L1s
    "SOL":      1.0,    # Solana
    "XLM":      4.0,    # Stellar

    # EVM sidechains / L1s
    "BNB":      4.0,    # BNB Smart Chain (BEP-20)
    "BSC":      4.0,    # alias if we ever use it
    "TRX":      30.0,   # Tron (TRC-20)
    "POLYGON":  5.0,    # Polygon PoS
    "MATIC":    5.0,    # Polygon alias

    # Ethereum L2s (Arbitrum / Base etc.)
    "ARB":      120.0,  # Arbitrum
    "BASE":     120.0,  # Base

    # Mainnet Ethereum
    "ETH":      600.0,  # ERC-20 on Ethereum
}

def get_chain_time_seconds(chain: str) -> Optional[float]:
    """
    Return the approximate transfer time for a given network
    (in seconds), or None if unknown.
    """
    return CHAIN_TRANSFER_TIME_SEC.get(chain.upper())


def get_chain_time_minutes(chain: str) -> Optional[float]:
    """
    Same as get_chain_time_seconds(), but in minutes.
    """
    sec = get_chain_time_seconds(chain)
    return None if sec is None else sec / 60.0

BENCHMARK_USER_EXECUTION_OVERHEAD_SEC: float = 45.0 


def get_user_execution_overhead_seconds() -> float:
    """Return the assumed user/UI execution overhead (45 seconds)."""
    return BENCHMARK_USER_EXECUTION_OVERHEAD_SEC

# This allows you to compute: blockchain time + user overhead.

def estimate_total_cycle_time_seconds(
    transfer_hops: List[Tuple[str, str]],
    include_user_overhead: bool = True,
) -> float:
    """
    Estimate total arbitrage cycle duration in seconds.

    Args:
        transfer_hops:
            A list of tuples (exchange_name, chain_name)
            representing each withdrawal hop.
        include_user_overhead:
            Whether to include the 45-second user delay.

    Returns:
        float — total seconds.
    """
    total = 0.0

    # Sum blockchain transfer times
    for _, chain in transfer_hops:
        t = get_chain_time_seconds(chain)
        if t is not None:
            total += t

    # Add user overhead (45s)
    if include_user_overhead:
        total += BENCHMARK_USER_EXECUTION_OVERHEAD_SEC

    return total
