# 🪙 Stablecoin Cross-Exchange Arbitrage

> An intelligent A* search system for discovering profitable arbitrage opportunities across multiple cryptocurrency exchanges using advanced heuristic functions.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.52+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Heuristics](#-heuristics)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Usage](#-usage)
- [Key Results](#-key-results)
- [Visualizations & Videos](#-visualizations--videos)
- [Documentation](#-documentation)
- [Project Structure](#-project-structure)
- [Contributing](#-contributing)

---

## 🎯 Overview

This project implements a sophisticated arbitrage detection system that:

- **Fetches live market data** from multiple exchanges (Binance, Kraken, KuCoin, Bybit, Coinbase)
- **Builds a weighted graph** representing exchange wallets and trading/transfer opportunities
- **Uses A* search algorithms** with multiple heuristic functions to find optimal arbitrage paths
- **Provides real-time visualization** through an interactive Streamlit UI
- **Compares heuristic performance** through comprehensive testing and Monte Carlo simulations

The system identifies profitable routes by considering:
- Trading fees and slippage
- Withdrawal fees and transfer times
- Market liquidity and order book depth
- Blockchain congestion and exchange reliability
- Multiple starting positions and parallel exploration

---

## ✨ Features

### Core Capabilities
- 🔄 **Multi-Exchange Support**: Binance, Kraken, KuCoin, Bybit, Coinbase
- 💱 **Multiple Stablecoins**: USDT, USDC, DAI, BUSD, TUSD, FDUSD, PYUSD, USDP
- 🧮 **Advanced Search Algorithms**: A* with multiple heuristic functions
- 📊 **Real-Time Data**: Live prices, order books, and 24h volume
- 🎨 **Interactive UI**: Streamlit-based visualization with real-time logging
- 📈 **Performance Analysis**: Comprehensive testing framework and result logging

### Heuristic Functions
- **h1_liquidity**: Volume-based heuristic prioritizing high-liquidity markets
- **h2_slippage**: Order-book slippage-based heuristic minimizing price impact
- **h3_parallel**: Parallel A* searches from random starting points
- **h4_chaincongestion_exchange_risk**: Weighted A* considering blockchain and exchange risks

---

## 🧠 Heuristics

### h1_liquidity
**Volume-based heuristic** that prefers routes with high trading volume and good liquidity.

- Uses 24-hour trading volume to estimate market depth
- Accounts for order size relative to typical trading volume
- Time-aware (considers remaining arbitrage window)
- **Best for**: Conservative strategies prioritizing reliable execution

### h2_slippage
**Order-book slippage-based heuristic** that penalizes routes where large orders would move prices significantly.

- Walks the order book to estimate actual slippage
- Considers real market depth at current prices
- More accurate for large orders
- **Best for**: Large capital deployments where slippage matters

### h3_parallel
**Meta-heuristic** that runs multiple A* searches in parallel from random starting nodes.

- Explores diverse starting positions simultaneously
- Finds optimal paths from multiple perspectives
- Thread-safe parallel execution
- **Best for**: Discovering opportunities when optimal starting point is unknown

### h4_chaincongestion_exchange_risk
**Weighted A* heuristic** that penalizes fast/risky blockchains and less reliable exchanges.

- Considers blockchain congestion and transfer times
- Accounts for exchange reliability and operational risk
- Fastest execution time (10-20x faster than others)
- **Best for**: Production use requiring speed and risk awareness

**📖 Detailed comparison**: See [HEURISTIC_COMPARISON.md](docs/HEURISTIC_COMPARISON.md)

---

## 🚀 Installation

### Prerequisites
- Python 3.12 or higher
- pip package manager

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Stablecoin-CrossExchange-Arbitrage
   ```

2. **Create virtual environment** (recommended)
   ```bash
   # Windows
   python -m venv venv312
   venv312\Scripts\activate

   # macOS/Linux
   python3 -m venv venv312
   source venv312/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

---

## ⚡ Quick Start

### Run the Streamlit UI

```bash
streamlit run scripts/ui.py
```

The UI will open in your browser at `http://localhost:8501`

**Note**: The UI takes about 1 minute to load initially as it fetches live market data from all exchanges.

### Run Experiments

```bash
# Monte Carlo simulation (10 trials per heuristic)
python experiments/monte_carlo_simulation.py

# Live heuristic comparison
python experiments/compare_heuristics_live.py

# Unit tests
python experiments/run_h1_unit_tests.py
python experiments/run_h2_unit_tests.py
python experiments/run_h3_unit_tests.py
python experiments/run_h4_unit_tests.py
```

---

## 📖 Usage

### Streamlit UI

The UI is organized into four tabs:

1. **Arbitrage Graph**: Main view with graph visualization and search controls
2. **Live Prices**: Real-time price table for all exchange-coin pairs
3. **Fees**: Trading and withdrawal fees used in calculations
4. **How to Use**: Detailed help documentation

#### Running a Search

1. Click **"Update price"** to fetch latest market data
2. Select **"Liquid cash (USD)"** (e.g., $10,000)
3. Choose a **Heuristic** (h1, h2, h3, or h4)
4. Select **"Starting wallet"** (e.g., `binance:USDT`)
5. Click **"Run search"**
6. View results in the **"Max profitable current trade"** section

**Note**: For `h3_parallel`, the starting wallet selector is hidden as it uses random starting points.

### Programmatic Usage

```python
from scripts.graph import build_nx_graph
from scripts.astar_vol import astar_best_path_with_liquidity

# Build graph with live data
G = build_nx_graph()

# Run A* search with h1_liquidity
result = astar_best_path_with_liquidity(
    G=G,
    start="binance:USDT",
    liquid_cash=10000.0,
    heuristic="h1_liquidity",
    max_depth=5
)

print(f"Profit: ${result.final_cash - result.start_cash:.2f}")
print(f"Path: {' -> '.join(result.path)}")
```

---

## 📊 Key Results

### Performance Metrics

Based on comprehensive testing across multiple order sizes ($1K, $10K, $100K):

| Heuristic | Avg Execution Time | Success Rate | Avg Profit* | Efficiency ($/sec) |
|-----------|-------------------|--------------|-------------|---------------------|
| **h4** | **4.7s** | 80% | $180.33 | **$38.45** |
| h1 | 81.8s | 100% | $110.14 | $1.35 |
| h2 | 66.3s | 80% | $91.67 | $1.38 |
| h3 | 104.5s | 100% | $203.49 | $1.95 |

*Average profit from Monte Carlo simulation (10 trials, varied start nodes)

### Key Findings

1. **Speed Advantage**: h4 is **10-20x faster** than other heuristics while maintaining competitive profit
2. **Reliability**: h1 and h3 achieve **100% success rate**; h2 and h4 have 80% (failures with TUSD markets)
3. **Profit Scaling**: Profit percentage remains constant (~0.42%) across order sizes, suggesting linear scaling
4. **Path Efficiency**: h2/h4 find shorter paths (2-4 hops) compared to h1 (3-6 hops)
5. **Start Node Sensitivity**: binance:USDT consistently outperforms binance:BUSD by 20-25%

**📈 Detailed analysis**: See [HEURISTIC_DATA_PATTERNS.md](docs/HEURISTIC_DATA_PATTERNS.md)

---

## 🎥 Visualizations & Videos

### Adding Videos to README

Yes! You can add videos to your README in several ways:

#### Option 1: YouTube/Vimeo Links (Recommended)
```markdown
## Demo Video
[![Demo Video](https://img.youtube.com/vi/VIDEO_ID/0.jpg)](https://www.youtube.com/watch?v=VIDEO_ID)
```

#### Option 2: Direct Video Links
```markdown
## Project Demo
https://youtu.be/VIDEO_ID
```

#### Option 3: Animated GIFs
```markdown
![UI Demo](docs/images/ui_demo.gif)
```

#### Option 4: HTML Embed (GitHub may sanitize)
```html
<video width="800" controls>
  <source src="docs/videos/demo.mp4" type="video/mp4">
  Your browser does not support the video tag.
</video>
```

### Recommended Video Content

Consider creating videos for:

1. **UI Walkthrough**: Demonstrate the Streamlit interface, running searches, interpreting results
2. **Heuristic Comparison**: Side-by-side comparison of different heuristics finding paths
3. **Real-Time Search**: Show the algorithm running with live logging
4. **Results Analysis**: Walk through the data patterns and visualizations

### Current Videos

*Add your video links here when available*

```markdown
## Demo Videos

### UI Overview
[![UI Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/0.jpg)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)

### Heuristic Comparison
[![Heuristic Comparison](https://img.youtube.com/vi/YOUR_VIDEO_ID/0.jpg)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)
```

---

## 📚 Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[HEURISTIC_COMPARISON.md](docs/HEURISTIC_COMPARISON.md)**: Detailed comparison of h1 and h2 heuristics
- **[HEURISTIC_DATA_PATTERNS.md](docs/HEURISTIC_DATA_PATTERNS.md)**: Analysis of patterns and anomalies for visualization
- **[HEURISTIC_TESTING_STRATEGY.md](docs/HEURISTIC_TESTING_STRATEGY.md)**: Systematic approach to heuristic testing
- **[H2_CONSTANT_TEST_RESULTS.md](docs/H2_CONSTANT_TEST_RESULTS.md)**: Results from h2_slippage constant optimization
- **[STREAMLIT_CLOUD_EXCHANGE_ISSUES.md](docs/STREAMLIT_CLOUD_EXCHANGE_ISSUES.md)**: Troubleshooting guide for deployment

### Results

Test results and logs are stored in `results/`:
- `compare_heuristics_live.txt`: Live comparison results
- `monte_carlo_heuristics.txt`: Monte Carlo simulation results
- `h2_constant_tests/`: Detailed h2 constant testing data (JSON + TXT)

---

## 📁 Project Structure

```
Stablecoin-CrossExchange-Arbitrage/
├── scripts/              # Core implementation
│   ├── ui.py             # Streamlit UI
│   ├── astar_vol.py      # A* search algorithm
│   ├── graph.py          # Graph construction
│   ├── data.py           # Exchange and coin definitions
│   ├── fees.py           # Fee calculations
│   ├── h1_vol.py         # h1_liquidity heuristic
│   ├── h2_slippage.py    # h2_slippage heuristic
│   ├── h3_parallel.py    # h3_parallel heuristic
│   └── h4_chaincongestion_exchange_risk.py  # h4 heuristic
├── experiments/          # Testing and comparison scripts
│   ├── monte_carlo_simulation.py
│   ├── compare_heuristics_live.py
│   └── run_*_unit_tests.py
├── docs/                 # Documentation
│   ├── HEURISTIC_COMPARISON.md
│   ├── HEURISTIC_DATA_PATTERNS.md
│   └── ...
├── results/              # Test results and logs
│   ├── compare_heuristics_live.txt
│   ├── monte_carlo_heuristics.txt
│   └── h2_constant_tests/
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

---

## 🔧 Technical Details

### Dependencies

- **ccxt**: Cryptocurrency exchange trading library for market data
- **networkx**: Graph construction and manipulation
- **streamlit**: Interactive web UI framework
- **matplotlib**: Graph visualization (for experiments)
- **pytest**: Unit testing framework

### Exchange APIs

All exchanges are accessed via public APIs (no authentication required):
- Real-time ticker prices
- 24-hour trading volume
- Order book depth (for slippage calculation)
- Market symbols and trading pairs

### Graph Representation

- **Nodes**: `exchange:coin` pairs (e.g., `binance:USDT`)
- **Edges**: 
  - **Blue**: Trades within an exchange
  - **Green**: Transfers between exchanges (blockchain withdrawals)
- **Edge Weights**: Negative profit (minimized by A*)

---

## 🐛 Known Issues

- **TUSD Markets**: h2 and h4 heuristics may fail with TUSD start nodes due to insufficient liquidity
- **Streamlit Cloud**: Some exchanges (Binance, Bybit) may not appear due to IP blocking or rate limits
- **Initial Load Time**: First graph build takes ~1 minute to fetch data from all exchanges

See [STREAMLIT_CLOUD_EXCHANGE_ISSUES.md](docs/STREAMLIT_CLOUD_EXCHANGE_ISSUES.md) for deployment troubleshooting.

---

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

- Additional heuristic functions
- More exchange integrations
- Performance optimizations
- Visualization enhancements
- Documentation improvements

---

## 📝 License

This project is licensed under the MIT License.

---

## 🙏 Acknowledgments

- **CCXT**: For providing unified exchange API access
- **NetworkX**: For graph algorithms and data structures
- **Streamlit**: For the interactive UI framework

---

## 📧 Contact

For questions or issues, please open an issue on the repository.

---

**⚠️ Disclaimer**: This is a research and educational project. It does not execute real trades or transfer funds. Always verify arbitrage opportunities manually and consider transaction costs, slippage, and execution risks before trading.

