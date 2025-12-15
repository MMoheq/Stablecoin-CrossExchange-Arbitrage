# ==============================================================
# show_graph.py — Visualize the arbitrage graph
# ==============================================================

"""
Builds the arbitrage graph using graph.build_graph() and visualizes it.

- Each node = (exchange, coin)
- Nodes are coloured by exchange and show:
      exchange:coin
      price_in_usd
- Edges:
    - blue  = trade edges (intra-exchange swaps)
    - green = transfer edges (cross-exchange transfers)
  Edge labels show the edge *cost* used in the search (−log(rate)).

Run:
    python show_graph.py
"""

from __future__ import annotations

import matplotlib.pyplot as plt  # type: ignore
import networkx as nx            # type: ignore

from scripts.graph import build_graph
from scripts.data import EXCHANGES


def main() -> None:

    nodes, adj = build_graph()

    G = nx.DiGraph()

    # Add nodes with attributes
    for node_id, meta in nodes.items():
        ex, coin = node_id
        G.add_node(
            node_id,
            exchange=ex,
            coin=coin,
            price_usd=meta["price_usd"],
            snapshot_ts=meta["snapshot_ts"],
        )

    # Add edges with attributes
    for from_node, edges in adj.items():
        for e in edges:
            kind = e.get("kind", "trade")
            if kind == "trade":
                color = "tab:blue"
            else:
                color = "tab:green"

            G.add_edge(
                e["from"],
                e["to"],
                kind=kind,
                rate=e["rate"],
                cost=e["cost"],
                chain=e.get("chain"),
                transfer_time_sec=e.get("transfer_time_sec", 0.0),
                color=color,
            )

    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    if G.number_of_nodes() == 0:
        print("No nodes to display (probably no prices were fetched).")
        return

    exchange_names = list(EXCHANGES.keys())
    exchange_to_idx = {ex: i for i, ex in enumerate(exchange_names)}

    node_colors = []
    node_labels = {}

    for node in G.nodes():
        ex = G.nodes[node]["exchange"]
        coin = G.nodes[node]["coin"]
        price = G.nodes[node]["price_usd"]
        node_labels[node] = f"{ex}:{coin}\n{price:.6f}"
        idx = exchange_to_idx.get(ex, 0)
        node_colors.append(idx)

    # Edge colours already stored as attribute
    edge_colors = [G.edges[e].get("color", "black") for e in G.edges()]

    # Edge labels: show edge cost (−log(rate))
    edge_labels = {}
    for u, v, data in G.edges(data=True):
        cost = data.get("cost")
        if cost is not None:
            edge_labels[(u, v)] = f"{cost:.4f}"

    # Layout
    pos = nx.spring_layout(G, seed=42, k=0.8)

    plt.figure(figsize=(11, 9))
    nx.draw_networkx_nodes(
        G,
        pos,
        node_size=900,
        node_color=node_colors,
        cmap=plt.cm.Set2,
    )
    nx.draw_networkx_edges(
        G,
        pos,
        edge_color=edge_colors,
        arrows=True,
        width=1.5,
        alpha=0.8,
    )
    nx.draw_networkx_labels(
        G,
        pos,
        labels=node_labels,
        font_size=7,
    )

    # Draw edge labels (costs)
    nx.draw_networkx_edge_labels(
        G,
        pos,
        edge_labels=edge_labels,
        font_size=6,
        label_pos=0.5,
    )

    # Legend / explanation
    plt.title("Stablecoin Arbitrage Graph\nNodes = (exchange, coin) with price; edges labelled by cost")
    plt.axis("off")

    legend_lines = [
        "Node colour: exchange",
        "Node label:",
        "   exchange:coin",
        "   price_usd",
        "",
        "Edge colour:",
        "   Blue  = Trade (intra-exchange swap)",
        "   Green = Transfer (cross-exchange, with withdrawal fee)",
        "",
        "Edge label: cost = -log(rate)",
    ]
    plt.text(
        1.05,
        0.5,
        "\n".join(legend_lines),
        transform=plt.gca().transAxes,
        va="center",
        fontsize=8,
    )

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
