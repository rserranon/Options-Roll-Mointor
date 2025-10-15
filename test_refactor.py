#!/usr/bin/env python3
"""
Simple smoke tests to verify the refactored modules work correctly.
"""

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        import utils
        import ib_connection
        import market_data
        import portfolio
        import options_finder
        import display
        print("  ✓ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False


def test_utils():
    """Test utils module functions."""
    print("\nTesting utils module...")
    from utils import dte, FALLBACK_EXCHANGES
    from datetime import datetime, timezone
    
    # Test DTE calculation
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    result = dte(today)
    assert result == 0, f"Expected 0 DTE for today, got {result}"
    print(f"  ✓ dte('{today}') = {result}")
    
    # Test FALLBACK_EXCHANGES
    assert isinstance(FALLBACK_EXCHANGES, list), "FALLBACK_EXCHANGES should be a list"
    assert len(FALLBACK_EXCHANGES) > 0, "FALLBACK_EXCHANGES should not be empty"
    print(f"  ✓ FALLBACK_EXCHANGES = {FALLBACK_EXCHANGES}")
    
    return True


def test_module_functions():
    """Test that expected functions exist in each module."""
    print("\nTesting module functions exist...")
    
    tests = [
        ("ib_connection", ["connect_ib", "disconnect_ib"]),
        ("market_data", ["safe_mark", "wait_for_greeks", "get_option_quote", "get_stock_price"]),
        ("portfolio", ["get_current_positions"]),
        ("options_finder", ["get_next_weekly_expiry", "find_strikes_by_delta", "find_roll_options"]),
        ("display", ["print_roll_options", "print_positions_summary"]),
    ]
    
    for module_name, functions in tests:
        module = __import__(module_name)
        for func_name in functions:
            assert hasattr(module, func_name), f"{module_name}.{func_name} not found"
            assert callable(getattr(module, func_name)), f"{module_name}.{func_name} is not callable"
        print(f"  ✓ {module_name}: {', '.join(functions)}")
    
    return True


def test_main_script():
    """Test that main script can be imported."""
    print("\nTesting main script...")
    try:
        import roll_monitor
        assert hasattr(roll_monitor, "main"), "main() function not found in roll_monitor"
        print("  ✓ roll_monitor.main() exists")
        return True
    except ImportError as e:
        print(f"  ✗ Failed to import roll_monitor: {e}")
        return False


def run_all_tests():
    """Run all tests."""
    print("="*60)
    print("REFACTORING SMOKE TESTS")
    print("="*60)
    
    tests = [
        test_imports,
        test_utils,
        test_module_functions,
        test_main_script,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    if all(results):
        print(f"✓ ALL TESTS PASSED ({passed}/{total})")
        print("="*60)
        return 0
    else:
        print(f"✗ SOME TESTS FAILED ({passed}/{total} passed)")
        print("="*60)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(run_all_tests())
