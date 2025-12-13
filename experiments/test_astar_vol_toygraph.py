import math
from scripts import astar_vol

NodeId = tuple[str, str]

def make_toy_graph():
    # pretend these are (exchange, coin)
    A: NodeId = ("ex1", "USDT")
    B: NodeId = ("ex1", "USDC")
    C: NodeId = ("ex1", "DAI")

    nodes = {
        A: {"exchange": "ex1", "coin": "USDT", "price_usd": 1.0, "snapshot_ts": 0.0},
        B: {"exchange": "ex1", "coin": "USDC", "price_usd": 1.0, "snapshot_ts": 0.0},
        C: {"exchange": "ex1", "coin": "DAI",  "price_usd": 1.0, "snapshot_ts": 0.0},
    }

    def edge(rate, from_node, to_node):
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

    adj = {
        A: [
            edge(1.01, A, B),
            edge(1.01 * 1.01 * 0.99, A, C),  # slightly worse than going via B
        ],
        B: [edge(1.01, B, C)],
        C: [],
    }

    return nodes, adj

def test_astar_finds_better_two_step_path(monkeypatch):
    # Patch build_graph() inside astar_vol to use our toy graph
    monkeypatch.setattr(astar_vol, "build_graph", make_toy_graph)

    start = ("ex1", "USDT")
    initial_cash = 1000.0

    result = astar_vol.astar_best_path_with_liquidity(
        start_node=start,
        liquid_cash_usd=initial_cash,
        max_depth=3,
        max_time_sec=60.0,
        min_profit_usd=0.0,
    )

    assert result is not None
    # Path should be ex1:USDT -> ex1:USDC -> ex1:DAI
    assert result.path == [
        ("ex1", "USDT"),
        ("ex1", "USDC"),
        ("ex1", "DAI"),
    ]
