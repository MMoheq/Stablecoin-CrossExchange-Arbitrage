# H2_Slippage Constant Testing Documentation

## Overview

This document describes the test suite for evaluating different constant values in the `h2_slippage` heuristic. The tests systematically vary three key constants to understand their impact on arbitrage path discovery and profitability.

**For detailed test results and analysis, see**: [H2_CONSTANT_TEST_RESULTS.md](./H2_CONSTANT_TEST_RESULTS.md)

## Test Data and Parameters

### Default Test Configuration

| Parameter | Default Value | Description |
|-----------|--------------|-------------|
| **Start Node** | `binance:USDT` | Starting exchange and coin |
| **Initial Capital** | $10,000.00 USD | Amount of capital to arbitrage |
| **Max Depth** | 6 | Maximum path length in the search graph |
| **Max Time** | 1800 seconds (30 min) | Maximum time window for arbitrage |
| **Min Profit** | $0.00 | Minimum profit threshold (finds any profitable path) |

### Test Constants Being Varied

The test suite systematically tests three constants from `h2_slippage.py`:

#### 1. SLIPPAGE_HEURISTIC_WEIGHT (w_slip)
Controls how strongly the heuristic penalizes slippage.

| Config Name | Value | Description |
|-------------|-------|-------------|
| `baseline` | 0.5 | Default value |
| `weight_low` | 0.1 | Minimal penalty (heuristic has little influence) |
| `weight_medium` | 0.25 | Low-medium penalty |
| `weight_high` | 1.0 | High penalty (heuristic has strong influence) |
| `weight_very_high` | 2.0 | Very high penalty (heuristic dominates) |

**Impact**: Higher weights make the heuristic more conservative, potentially avoiding high-slippage paths but may miss profitable opportunities.

#### 2. SLIPPAGE_THRESHOLD_BPS
Acceptable slippage threshold in basis points (1 bps = 0.01%).

| Config Name | Value | Description |
|-------------|-------|-------------|
| `baseline` | 10.0 bps (0.10%) | Default threshold |
| `threshold_low` | 5.0 bps (0.05%) | Very strict (penalizes even small slippage) |
| `threshold_medium` | 20.0 bps (0.20%) | More lenient |
| `threshold_high` | 50.0 bps (0.50%) | Very lenient (only penalizes high slippage) |

**Impact**: Lower thresholds make the heuristic more sensitive to slippage, potentially avoiding markets with any significant slippage.

#### 3. UNKNOWN_SLIPPAGE_PENALTY
Penalty applied when order book data is unavailable.

| Config Name | Value | Description |
|-------------|-------|-------------|
| `baseline` | 50.0 | Default penalty |
| `penalty_low` | 10.0 | Low penalty (less risk-averse) |
| `penalty_medium` | 25.0 | Medium penalty |
| `penalty_high` | 100.0 | High penalty (very risk-averse) |

**Impact**: Higher penalties make the heuristic avoid markets where order book data cannot be fetched, potentially missing opportunities in markets with missing data.

### Combined Configurations

| Config Name | Weight | Threshold | Penalty | Strategy |
|-------------|--------|-----------|---------|----------|
| `aggressive` | 1.0 | 5.0 bps | 100.0 | High weight, strict threshold, high penalty |
| `conservative` | 0.25 | 20.0 bps | 25.0 | Low weight, lenient threshold, low penalty |

## Test Batches

Tests are organized into logical batches for easier execution:

| Batch Name | Configs Included | Purpose |
|------------|-------------------|---------|
| `baseline` | `baseline` | Single baseline configuration |
| `weights` | `weight_low`, `weight_medium`, `weight_high`, `weight_very_high` | Test weight variations |
| `thresholds` | `threshold_low`, `threshold_medium`, `threshold_high` | Test threshold variations |
| `penalties` | `penalty_low`, `penalty_medium`, `penalty_high` | Test penalty variations |
| `combined` | `aggressive`, `conservative` | Test combined strategies |

**Total Configurations**: 13

## How Different Runs Differ

### 1. Different Starting Nodes

**Command**:
```bash
python scripts/test_h2_constants.py --start-node kucoin:USDC
```

**Impact**:
- Different starting liquidity conditions
- Different available paths from the starting point
- May discover different optimal paths
- Heuristic effectiveness may vary based on starting market liquidity

**When to Use**:
- Test robustness across different starting positions
- Evaluate heuristic performance in low-liquidity vs high-liquidity markets
- Understand path discovery from different exchanges

### 2. Different Capital Amounts

**Command**:
```bash
python scripts/test_h2_constants.py --capital 50000
```

**Impact**:
- **Larger orders**: Slippage becomes more significant, making `h2_slippage` more important
- **Smaller orders**: Slippage is less relevant, `h1_liquidity` may be more appropriate
- Different paths may be optimal for different order sizes
- Heuristic weights may need adjustment based on order size

**When to Use**:
- Test scalability (small vs large orders)
- Understand when slippage becomes a dominant factor
- Optimize for specific trading sizes

### 3. Different Search Depths

**Command**:
```bash
python scripts/test_h2_constants.py --max-depth 4
```

**Impact**:
- **Shallow (depth 3-4)**: Faster execution, may miss longer profitable paths
- **Deep (depth 6-8)**: More thorough exploration, higher computation cost
- Heuristic influence varies with depth (more important at shallow depths)
- May discover different optimal paths at different depths

**When to Use**:
- Balance between search thoroughness and execution time
- Test if optimal paths change with depth
- Understand heuristic effectiveness at different exploration levels

### 4. Different Batch Selections

**Command**:
```bash
python scripts/test_h2_constants.py --batch weights thresholds
```

**Impact**:
- Run only specific constant variations
- Faster execution for focused testing
- Can test subsets independently

**When to Use**:
- Quick testing of specific constant types
- Incremental testing approach
- Focus on areas of interest

### 5. Parallel vs Sequential Execution

**Command**:
```bash
python scripts/test_h2_constants.py --parallel --workers 3
```

**Impact**:
- **Sequential**: Safer, no race conditions, slower
- **Parallel**: Faster but may have issues with shared module constants
- Same results, different execution time

**When to Use**:
- Parallel: When speed is critical and you accept potential race conditions
- Sequential: For reliable, reproducible results

## Data Consistency Across Runs

### What Stays the Same

1. **Graph Structure**: The exchange/coin graph is built from the same data sources
2. **Market Data**: Uses live CCXT data at the time of execution
3. **Fee Structure**: Exchange fees and withdrawal costs remain constant
4. **Algorithm**: A* search algorithm implementation is unchanged

### What Changes

1. **Market Conditions**: Live market data (prices, volumes, order books) changes over time
2. **Heuristic Constants**: The three constants being tested vary across configurations
3. **Execution Time**: May vary based on API response times and network conditions

### Reproducibility Considerations

**Not Reproducible**:
- Exact profit values (market prices change)
- Execution times (network/API variability)
- Optimal paths (may change with market conditions)

**Reproducible**:
- Test configurations (same constants tested)
- Test methodology (same algorithm, same parameters)
- Relative comparisons (which config performs better)

## Expected Results

### Typical Observations

1. **Same Optimal Path**: Most configurations find the same optimal path when:
   - Optimal path is clearly dominant
   - Heuristic differences are small relative to actual edge costs
   - Market conditions are stable

2. **Different Intermediate Paths**: Configurations may explore different paths during search:
   - Different heuristic values guide exploration differently
   - Some configs find better intermediate paths earlier
   - Search efficiency varies

3. **Execution Time Variation**: 
   - Different heuristic values affect search order
   - May explore more/fewer nodes before finding optimal
   - Network/API variability

### When Results Differ Significantly

Results may differ more when:
- **Large order sizes**: Slippage becomes more important
- **Thin order books**: `h2_slippage` has more impact
- **Missing data**: Different penalty values matter more
- **Multiple profitable paths**: Heuristic choice determines which is found first
- **Time constraints**: Different heuristic weights affect time-aware decisions

## Logging and Data Collection

### Log Files

All test runs generate timestamped log files in `results/h2_constant_tests/`:

1. **JSON Log** (`h2_test_results_YYYYMMDD_HHMMSS.json`):
   - Machine-readable format
   - Complete test metadata
   - All results with timestamps
   - Batch completion status

2. **Text Log** (`h2_test_results_YYYYMMDD_HHMMSS.txt`):
   - Human-readable format
   - Real-time progress tracking
   - Formatted results

### What Gets Logged

- Test configuration (start node, capital, depth)
- Each test result (profit, path, execution time)
- Batch start/complete timestamps
- Final summary (total configs, successful, failed)

### Resuming After Failure

If a test run fails mid-way:
1. Check JSON log to see which configs completed
2. Check which batches are marked as "pending"
3. Re-run with `--batch` flag to complete remaining batches
4. Results are cumulative (can combine multiple runs)

## Example Test Scenarios

### Scenario 1: Baseline Comparison
```bash
# Test all configurations with default parameters
python scripts/test_h2_constants.py --batch all
```
**Purpose**: Comprehensive comparison of all constant variations

### Scenario 2: Weight Sensitivity Analysis
```bash
# Test only weight variations
python scripts/test_h2_constants.py --batch weights
```
**Purpose**: Understand how heuristic weight affects results

### Scenario 3: Large Order Testing
```bash
# Test with larger capital (slippage more important)
python scripts/test_h2_constants.py --capital 100000 --batch all
```
**Purpose**: See how constants perform with larger orders where slippage matters more

### Scenario 4: Quick Validation
```bash
# Test just baseline and one variation
python scripts/test_h2_constants.py --batch baseline weights --workers 1
```
**Purpose**: Quick check that system is working

### Scenario 5: Different Starting Point
```bash
# Test from a different exchange
python scripts/test_h2_constants.py --start-node kraken:USDC --batch all
```
**Purpose**: Test robustness across different starting conditions

## Interpreting Results

### Key Metrics

1. **Profit**: Final profit in USD and percentage
2. **Path**: The optimal path found
3. **Path Length**: Number of steps in the path
4. **Execution Time**: How long the search took

### Analysis Questions

1. **Do different constants find different paths?**
   - If yes: Constants significantly affect path selection
   - If no: Optimal path is dominant regardless of heuristic

2. **Do different constants find different profits?**
   - If yes: Some constants guide to better paths
   - If no: All constants converge to same optimal solution

3. **Do execution times vary?**
   - Faster: Heuristic guides search more efficiently
   - Slower: Heuristic causes more exploration

4. **Which constant values perform best?**
   - Compare profits across configurations
   - Consider execution time trade-offs
   - Evaluate robustness across different scenarios

## Recommendations

### For Initial Testing
- Start with `--batch baseline` to establish baseline
- Then test individual batches (`weights`, `thresholds`, `penalties`)
- Use sequential execution for reliability

### For Comprehensive Analysis
- Run all batches with default parameters
- Test with different capital amounts
- Test with different starting nodes
- Compare results across scenarios

### For Production Tuning
- Focus on configurations that show profit differences
- Test with realistic order sizes for your use case
- Consider execution time vs profit trade-offs
- Validate across multiple market conditions

## Future Enhancements

Potential improvements to the test suite:
1. **Automated comparison**: Script to compare results across runs
2. **Statistical analysis**: Multiple runs to account for market variability
3. **Visualization**: Charts showing constant impact on results
4. **Resume capability**: Automatically skip completed configs
5. **Parameter sweeps**: Test more granular constant value ranges

---

*Last updated: 2024*
*Test script: `scripts/test_h2_constants.py`*

