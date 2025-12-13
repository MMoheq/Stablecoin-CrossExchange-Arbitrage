"""Test runner for all test suites with parallel execution support."""

import unittest
import sys
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class ThreadSafeTestResult(unittest.TestResult):
    """Thread-safe test result collector."""
    
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        self._failures = []
        self._errors = []
        self._tests_run = 0
    
    def addFailure(self, test, err):
        with self.lock:
            super().addFailure(test, err)
            self._failures.append((test, self._exc_info_to_string(err, test)))
    
    def addError(self, test, err):
        with self.lock:
            super().addError(test, err)
            self._errors.append((test, self._exc_info_to_string(err, test)))
    
    def startTest(self, test):
        with self.lock:
            super().startTest(test)
            self._tests_run += 1


def run_test_suite(suite_name: str, suite: unittest.TestSuite) -> Tuple[str, unittest.TestResult]:
    """Run a test suite in a separate thread."""
    # Create a custom stream that captures output
    from io import StringIO
    stream = StringIO()
    
    # Create runner and run the suite
    runner = unittest.TextTestRunner(verbosity=1, stream=stream)
    result = runner.run(suite)
    
    return suite_name, result


def run_all_tests_parallel(max_workers: int = 4):
    """Run all test suites in parallel using threads."""
    print("="*60)
    print("PARALLEL TEST RUNNER")
    print("="*60)
    print(f"Running tests with {max_workers} parallel threads\n")
    
    # Discover and organize test suites
    loader = unittest.TestLoader()
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(tests_dir)
    
    # Organize test suites by category
    test_suites = {}
    
    # Unit tests
    unit_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'unit'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    if unit_tests.countTestCases() > 0:
        test_suites['unit'] = unit_tests
    
    # Integration tests
    integration_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'integration'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    if integration_tests.countTestCases() > 0:
        test_suites['integration'] = integration_tests
    
    # Validation tests
    validation_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'validation'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    if validation_tests.countTestCases() > 0:
        test_suites['validation'] = validation_tests
    
    # Performance tests
    performance_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'performance'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    if performance_tests.countTestCases() > 0:
        test_suites['performance'] = performance_tests
    
    # Backtesting tests
    backtesting_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'backtesting'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    if backtesting_tests.countTestCases() > 0:
        test_suites['backtesting'] = backtesting_tests
    
    # Monte Carlo tests
    monte_carlo_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'monte_carlo'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    if monte_carlo_tests.countTestCases() > 0:
        test_suites['monte_carlo'] = monte_carlo_tests
    
    if not test_suites:
        print("No test suites found!")
        return False
    
    print(f"Found {len(test_suites)} test suite(s) to run:")
    for name, suite in test_suites.items():
        print(f"  - {name}: {suite.countTestCases()} test(s)")
    print()
    
    # Run test suites in parallel
    start_time = time.time()
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all test suites
        future_to_suite = {
            executor.submit(run_test_suite, name, suite): name
            for name, suite in test_suites.items()
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_suite):
            suite_name = future_to_suite[future]
            try:
                name, result = future.result()
                results[name] = result
                status = "✅ PASSED" if result.wasSuccessful() else "❌ FAILED"
                print(f"{status} {name} ({result.testsRun} tests)")
            except Exception as exc:
                print(f"❌ {suite_name} generated an exception: {exc}")
                results[suite_name] = None
    
    elapsed_time = time.time() - start_time
    
    # Aggregate results
    total_tests = sum(r.testsRun for r in results.values() if r)
    total_failures = sum(len(r.failures) for r in results.values() if r)
    total_errors = sum(len(r.errors) for r in results.values() if r)
    total_skipped = sum(len(r.skipped) for r in results.values() if r)
    
    # Print detailed summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total test suites: {len(test_suites)}")
    print(f"Total tests run: {total_tests}")
    print(f"Failures: {total_failures}")
    print(f"Errors: {total_errors}")
    print(f"Skipped: {total_skipped}")
    if total_tests > 0:
        success_rate = (total_tests - total_failures - total_errors) / total_tests * 100
        print(f"Success rate: {success_rate:.1f}%")
    print(f"Total time: {elapsed_time:.2f} seconds")
    print("="*60)
    
    # Print per-suite breakdown
    print("\nPer-Suite Breakdown:")
    print("-" * 60)
    for name, result in sorted(results.items()):
        if result:
            status = "✅" if result.wasSuccessful() else "❌"
            print(f"{status} {name:15s} - {result.testsRun:3d} tests, "
                  f"{len(result.failures):2d} failures, {len(result.errors):2d} errors")
    
    # Print failures and errors if any
    if total_failures > 0 or total_errors > 0:
        print("\n" + "="*60)
        print("FAILURES AND ERRORS")
        print("="*60)
        for name, result in sorted(results.items()):
            if result and (result.failures or result.errors):
                print(f"\n{name.upper()}:")
                for test, traceback in result.failures:
                    print(f"  FAIL: {test}")
                for test, traceback in result.errors:
                    print(f"  ERROR: {test}")
    
    return total_failures == 0 and total_errors == 0


def run_all_tests():
    """Run all test suites sequentially (original behavior)."""
    # Discover and run all tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Get the tests directory path
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(tests_dir)
    
    # Add unit tests
    unit_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'unit'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    suite.addTests(unit_tests)
    
    # Add integration tests
    integration_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'integration'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    suite.addTests(integration_tests)
    
    # Add validation tests
    validation_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'validation'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    suite.addTests(validation_tests)
    
    # Add performance tests
    performance_tests = loader.discover(
        start_dir=os.path.join(tests_dir, 'performance'),
        pattern='test_*.py',
        top_level_dir=project_root
    )
    suite.addTests(performance_tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run test suites')
    parser.add_argument('--parallel', '-p', action='store_true',
                        help='Run tests in parallel using threads')
    parser.add_argument('--workers', '-w', type=int, default=4,
                        help='Number of parallel workers (default: 4)')
    
    args = parser.parse_args()
    
    if args.parallel:
        success = run_all_tests_parallel(max_workers=args.workers)
    else:
        success = run_all_tests()
    
    sys.exit(0 if success else 1)
    sys.exit(0 if success else 1)

