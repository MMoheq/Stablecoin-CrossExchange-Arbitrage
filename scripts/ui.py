# ==============================================================
# ui.py — Simple Streamlit UI for Stablecoin Arbitrage
# ==============================================================

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st           # type: ignore
import matplotlib.pyplot as plt  # type: ignore
import networkx as nx            # type: ignore

from scripts.graph import build_graph
from scripts.data import EXCHANGES
from scripts.astar_vol import astar_best_path_with_liquidity, PlanResult, NodeId
from typing import Optional


# --------------------------------------------------------------
# Small helper: build a NetworkX graph and matplotlib figure
# --------------------------------------------------------------

def build_nx_graph():
    """Use build_graph() and convert to a NetworkX DiGraph."""
    nodes, adj = build_graph()

    G = nx.DiGraph()

    # Add nodes
    for node_id, meta in nodes.items():
        ex, coin = node_id
        G.add_node(
            node_id,
            exchange=ex,
            coin=coin,
            price_usd=meta["price_usd"],
            snapshot_ts=meta["snapshot_ts"],
        )

    # Add edges
    for from_node, edges in adj.items():
        for e in edges:
            kind = e.get("kind", "trade")
            color = "tab:blue" if kind == "trade" else "tab:green"

            G.add_edge(
                e["from"],
                e["to"],
                kind=kind,
                rate=e["rate"],
                cost=e["cost"],
                color=color,
                taker_fee=e.get("taker_fee"),
                withdraw_fee=e.get("withdrawal_fee_units"),
                chain=e.get("chain"),
                transfer_time_sec=e.get("transfer_time_sec", 0.0),
                raw_edge=e,  # keep original dict if we ever need it
            )

    return G


def make_graph_figure(G: nx.DiGraph):
    """Create a matplotlib Figure for the given NetworkX graph."""
    # Colours by exchange
    exchange_names = list(EXCHANGES.keys())
    exchange_to_idx = {ex: i for i, ex in enumerate(exchange_names)}

    node_colors = []
    node_labels = {}

    for node in G.nodes():
        ex = G.nodes[node]["exchange"]
        coin = G.nodes[node]["coin"]
        price = G.nodes[node]["price_usd"]

        node_labels[node] = f"{ex}:{coin}\n{price:.6f}"
        node_colors.append(exchange_to_idx.get(ex, 0))

    edge_colors = [G.edges[e].get("color", "black") for e in G.edges()]

    # Position for all nodes — higher k => more spread out
    pos = nx.spring_layout(G, seed=42, k=1.3)

    fig, ax = plt.subplots(figsize=(10, 7))
    nx.draw_networkx_nodes(
        G,
        pos,
        node_size=650,
        node_color=node_colors,
        cmap=plt.cm.Set2,
        ax=ax,
    )
    nx.draw_networkx_edges(
        G,
        pos,
        edge_color=edge_colors,
        arrows=True,
        width=1.5,
        alpha=0.8,
        ax=ax,
    )
    nx.draw_networkx_labels(
        G,
        pos,
        labels=node_labels,
        font_size=7,
        ax=ax,
    )

    # ---- Edge labels: only cost, split above/below to reduce overlap ----
    edge_labels_trade: dict[tuple, str] = {}
    edge_labels_transfer: dict[tuple, str] = {}

    for u, v, data in G.edges(data=True):
        cost = data.get("cost")
        if cost is None:
            continue

        label = f"c={cost:.4f}"

        if data.get("kind") == "trade":
            # Blue intra-exchange trade edge
            edge_labels_trade[(u, v)] = label
        else:
            # Green cross-exchange transfer edge
            edge_labels_transfer[(u, v)] = label

    # Trades: label closer to the source side of the edge
    nx.draw_networkx_edge_labels(
        G,
        pos,
        edge_labels=edge_labels_trade,
        font_size=6,
        label_pos=0.35,
        ax=ax,
    )

    # Transfers: label closer to the target side of the edge
    nx.draw_networkx_edge_labels(
        G,
        pos,
        edge_labels=edge_labels_transfer,
        font_size=6,
        label_pos=0.65,
        ax=ax,
    )

    ax.set_title("Stablecoin Arbitrage Graph\nNodes = (exchange, coin) with price")
    ax.axis("off")
    fig.tight_layout()

    return fig


# --------------------------------------------------------------
# Helper: run A* and format result text (with chain info)
# --------------------------------------------------------------

def run_search_and_format(
    start_wallet: str,
    liquid_cash: float,
    heuristic_name: str,
) -> str:
    """
    Run A* from the selected start node and return a human-readable report.

    Uses the selected heuristic in the A* search.
    """
    try:
        ex, coin = start_wallet.split(":")
    except ValueError:
        return "Invalid start wallet selection (expected 'exchange:coin')."

    start_node: NodeId = (ex, coin)

    try:
        result: Optional[PlanResult] = astar_best_path_with_liquidity(
            start_node=start_node,
            liquid_cash_usd=liquid_cash,
            max_depth=6,
            max_time_sec=1800.0,
            min_profit_usd=0.0,
            heuristic=heuristic_name,  # Pass selected heuristic to A*
        )
    except Exception as e:
        return f"Error while running A* search: {e}"

    if result is None:
        return (
            f"No profitable path found from {start_wallet} with "
            f"{liquid_cash:.2f} USD using heuristic {heuristic_name}."
        )

    profit_pct = (result.profit_usd / liquid_cash) * 100.0 if liquid_cash > 0 else 0.0
    route_str = " -> ".join(f"{ex}:{c}" for (ex, c) in result.path)

    lines: list[str] = []
    lines.append(f"Max profitable current trade (A* with {heuristic_name}):")
    lines.append(f"Start node: {start_wallet}")
    lines.append(f"Start cash: {liquid_cash:.2f} USD")
    lines.append(f"Final cash: {result.final_cash_usd:.2f} USD")
    lines.append(f"Profit: {result.profit_usd:.2f} USD ({profit_pct:.4f}%)")
    lines.append("")
    lines.append("Route:")
    lines.append(f"  {route_str}")
    lines.append("")
    lines.append("Steps:")

    # One line per edge, showing chain for transfers
    for i, edge in enumerate(result.edges, start=1):
        kind = edge.get("kind", "trade")

        if kind == "trade":
            ex = edge.get("exchange")
            c_from = edge.get("coin_from")
            c_to = edge.get("coin_to")
            taker_fee = edge.get("taker_fee")
            if isinstance(taker_fee, (int, float)):
                fee_str = f", taker fee ≈ {taker_fee * 100:.3f}%"
            else:
                fee_str = ""
            lines.append(
                f"{i}. Trade on {ex}: {c_from} → {c_to}{fee_str}"
            )
        else:
            ex_from = edge.get("exchange")
            ex_to = edge.get("target_exchange")
            coin = edge.get("coin")
            chain = edge.get("chain") or "unknown chain"
            fee_units = edge.get("withdrawal_fee_units")
            t_sec = edge.get("transfer_time_sec")

            details: list[str] = []
            if isinstance(fee_units, (int, float)):
                details.append(f"fee {fee_units:g} {coin}")
            if isinstance(t_sec, (int, float)) and t_sec > 0:
                details.append(f"~{t_sec:.0f}s est. transfer time")
            detail_str = f" ({', '.join(details)})" if details else ""

            lines.append(
                f"{i}. Transfer {coin}: {ex_from} → {ex_to} via {chain}{detail_str}"
            )

    return "\n".join(lines)


# --------------------------------------------------------------
# Streamlit app
# --------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Stablecoin Arbitrage UI",
        layout="wide",
    )

    st.title("Stablecoin Cross-Exchange Arbitrage")
    st.caption("Live graph + heuristic selection + price updates")

    # Session state: store the current NetworkX graph and search result text
    if "graph" not in st.session_state:
        st.session_state["graph"] = build_nx_graph()
    if "best_trade_text" not in st.session_state:
        st.session_state["best_trade_text"] = "Click **Run search** to compute a path."

    G: nx.DiGraph = st.session_state["graph"]

    # Prepare list of starting wallets (exchange:coin)
    start_wallet_options = sorted(f"{ex}:{coin}" for (ex, coin) in G.nodes())
    default_start = "binance:BUSD"
    if default_start not in start_wallet_options and start_wallet_options:
        default_start = start_wallet_options[0]

    # Top layout: graph + controls
    col_graph, col_controls = st.columns([3, 1])

    with col_controls:
        st.subheader("Controls")

        # Update prices -> rebuild the graph
        if st.button("Update price"):
            st.session_state["graph"] = build_nx_graph()
            G = st.session_state["graph"]
            st.success("Prices updated and graph rebuilt.")

            # Refresh start wallet options in case node set changed
            start_wallet_options[:] = sorted(f"{ex}:{coin}" for (ex, coin) in G.nodes())

        # Liquid cash input
        liquid_cash = st.number_input(
            "Liquid cash (USD)",
            min_value=0.0,
            value=1000.0,
            step=100.0,
            help="Total capital available to allocate to a trade.",
        )

        # Start wallet selection
        start_wallet = st.selectbox(
            "Starting wallet (exchange:coin)",
            options=start_wallet_options,
            index=start_wallet_options.index(default_start)
            if default_start in start_wallet_options
            else 0,
            help="Node where your funds currently live.",
        )

        # Heuristic dropdown
        heuristic = st.selectbox(
            "Heuristic",
            [
                "h1_liquidity",  # volume-based heuristic
                "h2_slippage",   # order-book slippage heuristic
            ],
            help="Select which heuristic h(n) to use in the search.",
        )

        st.markdown("---")
        st.subheader("Max profitable current trade")

        # ---- Run button: only run A* when clicked ----
        if st.button("Run search"):
            st.session_state["best_trade_text"] = run_search_and_format(
                start_wallet, liquid_cash, heuristic
            )

        # Display the last result (or the initial message)
        st.text(st.session_state["best_trade_text"])

    with col_graph:
        st.subheader("Arbitrage Graph")
        fig = make_graph_figure(G)
        st.pyplot(fig, use_container_width=True)

        # Explanation of edge colours (plain text only)
        st.markdown(
            """
            **Edge colours**

            • Blue — Trade edge (intra-exchange swap), cost includes taker fee.  
            • Green — Transfer edge (cross-exchange), cost includes withdrawal fee on the chosen chain.  

            **Edge labels**

            • c is the edge cost, defined as negative log of the effective rate after fees.  
            • Taker fees and withdrawal fees are included inside that cost, even if they are not shown separately in the label.
            """
        )


if __name__ == "__main__":
    main()
