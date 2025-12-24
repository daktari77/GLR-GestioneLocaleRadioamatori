# -*- coding: utf-8 -*-
"""
Test runner for GestioneSoci

Run all tests with: python tests/run_tests.py
Run specific test: python tests/run_tests.py test_database
Run with coverage: python tests/run_tests.py --coverage
"""

import sys
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def run_all_tests(verbosity=2):
    """Run all tests in the tests directory."""
    loader = unittest.TestLoader()
    start_dir = str(Path(__file__).parent)
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_specific_test(test_module, verbosity=2):
    """Run a specific test module."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(test_module)
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def print_usage():
    """Print usage instructions."""
    print("Usage:")
    print("  python tests/run_tests.py              # Run all tests")
    print("  python tests/run_tests.py test_database # Run specific test")
    print("  python tests/run_tests.py --verbose    # Run with verbose output")
    print("")
    print("Available tests:")
    print("  test_database  - Database operations tests")
    print("  test_backup    - Backup and restore tests")
    print("  test_models    - Member model validation tests")
    print("  test_magazzino_manager - Gestione magazzino e prestiti")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg in ['-h', '--help']:
            print_usage()
            sys.exit(0)
        
        if arg == '--verbose':
            success = run_all_tests(verbosity=2)
        elif arg.startswith('test_'):
            success = run_specific_test(arg, verbosity=2)
        else:
            print(f"Unknown argument: {arg}")
            print_usage()
            sys.exit(1)
    else:
        success = run_all_tests(verbosity=2)
    
    sys.exit(0 if success else 1)
