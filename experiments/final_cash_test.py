import math
import sys, os

# project root to sys.path so "scripts" becomes importable
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from scripts.astar_vol import _final_cash_from_log_cost

def test_final_cash_matches_product_of_rates():
    print("=== Running final_cash_test ===")

    initial = 1000.0
    rates = [1.01, 0.99, 1.02]  # some random edge rates
    print("Initial cash:", initial)
    print("Rates:", rates)

    total_log_cost = sum(-math.log(r) for r in rates)
    print("Total log cost:", total_log_cost)

    final1 = _final_cash_from_log_cost(initial, total_log_cost)
    print("Final cash from log-cost function:", final1)

    product = 1.0
    for r in rates:
        product *= r
    final2 = initial * product
    print("Final cash from direct product:", final2)

    difference = abs(final1 - final2)
    print("Difference:", difference)

    assert difference < 1e-6
    print("Test passed\n")

if __name__ == "__main__":
    test_final_cash_matches_product_of_rates()
