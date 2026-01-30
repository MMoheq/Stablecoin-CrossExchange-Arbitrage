
from __future__ import annotations

import time
import math
from collections import defaultdict
from typing import Dict, Tuple, List, Any

# from our own modules
from scripts.data import EXCHANGES, STABLE_COINS, COIN_MARKETS, normalize_price_to_usd
from scripts.fees import WITHDRAWAL_FEES, get_taker_fee
from scripts.transfer_time import get_chain_time_seconds

# Node is (exchange, coin)
NodeId = Tuple[str, str]

Adjacency = Dict[NodeId, List[Dict[str, Any]]]


# Maximum deviation from $1.00 for a coin to be considered a stablecoin
# Coins trading outside this range are excluded (e.g., FRAX can trade at $0.80-$0.90)
STABLECOIN_PRICE_TOLERANCE = 0.05  # 5% tolerance: $0.95 - $1.05


def fetch_price_snapshot() -> Tuple[Dict[NodeId, float], float]:
    """
    Fetch a snapshot of USD-normalized prices for all (exchange, coin)
    pairs where we have a configured market in data.py.

    Filters out coins that deviate too far from $1.00 (not true stablecoins).

    Returns:
        prices:    dict[(exchange, coin)] -> price_usd
        timestamp: unix time when snapshot was taken
    """
    prices: Dict[NodeId, float] = {}
    snapshot_ts = time.time()

    for coin in STABLE_COINS:
        for ex_name, ex in EXCHANGES.items():
            market = COIN_MARKETS.get(coin, {}).get(ex_name)
            if not market:
                continue

            try:
                ticker = ex.fetch_ticker(market)
            except Exception:
                continue

            bid = ticker.get("bid")
            ask = ticker.get("ask")
            last = ticker.get("last")

            if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
                mid = (bid + ask) / 2.0
            elif isinstance(last, (int, float)):
                mid = float(last)
            else:
                # no usable price
                continue

            price_usd = normalize_price_to_usd(coin, market, mid)
            if price_usd is None:
                continue

            # Filter out coins that deviate too far from $1.00
            # These are not true stablecoins (e.g., FRAX trading at $0.82)
            if abs(price_usd - 1.0) > STABLECOIN_PRICE_TOLERANCE:
                continue  # Skip this coin on this exchange

            prices[(ex_name, coin)] = price_usd

    return prices, snapshot_ts


def _fetch_actual_trading_pair_rate(
    ex_name: str,
    coin_from: str,
    coin_to: str,
) -> float | None:
    """
    Try to fetch the actual trading pair rate from the exchange.
    Returns the rate (units of coin_to per 1 unit of coin_from) or None if not available.
    """
    ex = EXCHANGES[ex_name]
    
    # Try both directions
    pairs_to_try = [
        (f"{coin_from}/{coin_to}", False),  # Direct: base=coin_from, quote=coin_to
        (f"{coin_to}/{coin_from}", True),     # Inverted: base=coin_to, quote=coin_from
    ]
    
    for pair, needs_invert in pairs_to_try:
        try:
            ticker = ex.fetch_ticker(pair)
            bid = ticker.get("bid")
            ask = ticker.get("ask")
            if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
                mid = (bid + ask) / 2.0
                if needs_invert:
                    return 1.0 / mid  # Invert: 1 coin_from = 1/mid coin_to
                else:
                    return mid  # Direct: 1 coin_from = mid coin_to
        except Exception:
            continue
    
    return None


def _build_trade_edges(
    prices: Dict[NodeId, float],
) -> Adjacency:
    """
    For each exchange, connect all coins listed there with trade edges.

    Each edge:
        kind = "trade"
        rate = effective multiplicative factor on amount
        cost = -log(rate)
    
    IMPORTANT: We try to fetch actual trading pair prices first. If not available,
    we fall back to calculating from normalized USD prices (which may introduce
    small errors due to normalization path differences).
    """
    adj: Adjacency = defaultdict(list)

    for ex_name in EXCHANGES.keys():
        # collect coins that have a price on this exchange
        coins_here = [c for c in STABLE_COINS if (ex_name, c) in prices]
        if len(coins_here) < 2:
            continue

        taker_fee = get_taker_fee(ex_name) or 0.0

        for i in range(len(coins_here)):
            for j in range(len(coins_here)):
                if i == j:
                    continue

                c_from = coins_here[i]
                c_to = coins_here[j]
                
                # Try to fetch actual trading pair rate first
                actual_rate = _fetch_actual_trading_pair_rate(ex_name, c_from, c_to)
                
                if actual_rate is not None:
                    # Use actual trading pair rate
                    raw_rate = actual_rate
                else:
                    # Fallback: calculate from normalized USD prices
                    # This may introduce small errors but is better than nothing
                    p_from = prices[(ex_name, c_from)]  # USD per 1 c_from
                    p_to = prices[(ex_name, c_to)]      # USD per 1 c_to
                    raw_rate = p_from / p_to

                effective_rate = raw_rate * (1.0 - taker_fee)

                if effective_rate <= 0:
                    continue

                cost = -math.log(effective_rate)

                from_node: NodeId = (ex_name, c_from)
                to_node: NodeId = (ex_name, c_to)

                adj[from_node].append(
                    {
                        "from": from_node,
                        "to": to_node,
                        "kind": "trade",
                        "exchange": ex_name,
                        "coin_from": c_from,
                        "coin_to": c_to,
                        "rate": effective_rate,
                        "cost": cost,
                        "taker_fee": taker_fee,
                        "withdrawal_fee_units": None,
                        "reference_amount_units": None,
                        "chain": None,
                        "transfer_time_sec": 0.0,
                        "uses_actual_pair": actual_rate is not None,  # Flag for debugging
                    }
                )

    return adj



REFERENCE_NOTIONAL_USD: float = 10_000.0  # assumed trade size for fee impact


def _build_transfer_edges(
    prices: Dict[NodeId, float],
) -> Adjacency:
    """
    For each coin and pair of exchanges, create transfer edges based on
    WITHDRAWAL_FEES and chain transfer times.

    We assume a reference notional (REFERENCE_NOTIONAL_USD) and compute
    the multiplicative loss of amount from paying a flat withdrawal fee.

        amount_start_units  = REFERENCE_NOTIONAL_USD / price_usd
        amount_after_fee    = amount_start_units - fee_units
        rate = amount_after_fee / amount_start_units = 1 - fee_units / amount_start_units

    Each edge:
        kind  = "transfer"
        rate  = amount multiplier after fee
        cost  = -log(rate)
        chain = network used for transfer
    """
    adj: Adjacency = defaultdict(list)

    # Precompute which exchanges have each coin priced
    coin_exchanges: Dict[str, List[str]] = {
        coin: [ex for (ex, c) in prices.keys() if c == coin]
        for coin in STABLE_COINS
    }

    for coin in STABLE_COINS:
        ex_list = coin_exchanges.get(coin, [])
        if len(ex_list) < 2:
            continue

        for ex_from in ex_list:
            # withdrawal options for this coin on ex_from
            ex_withdraw_cfg = WITHDRAWAL_FEES.get(ex_from, {}).get(coin)
            if not ex_withdraw_cfg:
                continue

            price_from_usd = prices[(ex_from, coin)]
            amount_start_units = REFERENCE_NOTIONAL_USD / price_from_usd

            for ex_to in ex_list:
                if ex_to == ex_from:
                    continue

                # Optional: require common chains between from/to;
                # for now we intersect chain names if both have entries.
                chains_from = ex_withdraw_cfg
                chains_to = WITHDRAWAL_FEES.get(ex_to, {}).get(coin, {})

                if chains_to:
                    common_chains = set(chains_from.keys()) & set(chains_to.keys())
                else:
                    # if we don't know deposit networks for ex_to, just
                    # assume all chains_from are usable (approximation)
                    common_chains = set(chains_from.keys())

                if not common_chains:
                    continue

                for chain in common_chains:
                    fee_units = chains_from[chain]
                    # if fee eats everything, skip
                    if fee_units >= amount_start_units:
                        continue

                    rate = 1.0 - (fee_units / amount_start_units)
                    if rate <= 0:
                        continue

                    cost = -math.log(rate)
                    t_sec = get_chain_time_seconds(chain) or 0.0

                    from_node: NodeId = (ex_from, coin)
                    to_node: NodeId = (ex_to, coin)

                    adj[from_node].append(
                        {
                            "from": from_node,
                            "to": to_node,
                            "kind": "transfer",
                            "exchange": ex_from,
                            "target_exchange": ex_to,
                            "coin": coin,
                            "rate": rate,
                            "cost": cost,
                            "taker_fee": None,
                            "withdrawal_fee_units": fee_units,
                            "reference_amount_units": amount_start_units,
                            "chain": chain,
                            "transfer_time_sec": t_sec,
                        }
                    )

    return adj


def build_graph() -> Tuple[Dict[NodeId, Dict[str, Any]], Adjacency]:
    """
    Build the arbitrage graph.

    Returns:
        nodes:
            dict[(exchange, coin)] -> {
                "exchange": ...,
                "coin": ...,
                "price_usd": ...,
                "snapshot_ts": ...,
            }

        adj:
            adjacency list mapping node -> list of edge dicts.
    """
    prices, snapshot_ts = fetch_price_snapshot()

    # Nodes with metadata (price + snapshot time)
    nodes: Dict[NodeId, Dict[str, Any]] = {
        (ex, coin): {
            "exchange": ex,
            "coin": coin,
            "price_usd": price_usd,
            "snapshot_ts": snapshot_ts,
        }
        for (ex, coin), price_usd in prices.items()
    }

    # Build edges
    adj: Adjacency = defaultdict(list)

    trade_adj = _build_trade_edges(prices)
    transfer_adj = _build_transfer_edges(prices)

    # merge adjacency lists
    for node, edges in trade_adj.items():
        adj[node].extend(edges)
    for node, edges in transfer_adj.items():
        adj[node].extend(edges)

    return nodes, adj


if __name__ == "__main__":
    # Small sanity check: build graph and print basic stats
    nodes, adj = build_graph()
    print(f"Nodes: {len(nodes)}")
    edge_count = sum(len(v) for v in adj.values())
    print(f"Edges: {edge_count}")
