#!/usr/bin/env python3
"""
Submission Validator for SDET Assessment

This script validates candidate submissions by checking:
1. Required files exist
2. Fixtures are implemented
3. Tests run without errors
4. Bug documentation exists

Usage:
    python scripts/validate_submission.py
"""
import os
import sys
import subprocess
import re
from pathlib import Path


# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def print_status(message: str, status: str):
    """Print colored status message."""
    color = GREEN if status == 'PASS' else RED if status == 'FAIL' else YELLOW
    print(f"{color}[{status}]{RESET} {message}")


def check_file_exists(filepath: str) -> bool:
    """Check if a file exists."""
    return Path(filepath).exists()


def check_todos_completed(filepath: str) -> tuple:
    """Check how many TODOs remain in a file."""
    if not check_file_exists(filepath):
        return (0, 0, False)

    with open(filepath, 'r') as f:
        content = f.read()

    # Count TODO comments
    todos = re.findall(r'#\s*YOUR CODE HERE|#\s*TODO:', content, re.IGNORECASE)
    # Count 'pass' statements that indicate incomplete implementation
    passes = re.findall(r'^\s+pass\s*$', content, re.MULTILINE)

    return (len(todos), len(passes), True)


def run_tests(test_path: str = "tests/") -> tuple:
    """Run pytest and return results."""
    try:
        result = subprocess.run(
            ["pytest", test_path, "-v", "--tb=no", "-q"],
            capture_output=True,
            text=True,
            timeout=120
        )

        # Parse output for pass/fail counts
        output = result.stdout + result.stderr

        # Look for summary line like "10 passed, 2 failed"
        passed = 0
        failed = 0

        passed_match = re.search(r'(\d+) passed', output)
        failed_match = re.search(r'(\d+) failed', output)

        if passed_match:
            passed = int(passed_match.group(1))
        if failed_match:
            failed = int(failed_match.group(1))

        return (passed, failed, result.returncode == 0)

    except subprocess.TimeoutExpired:
        return (0, 0, False)
    except Exception as e:
        print(f"Error running tests: {e}")
        return (0, 0, False)


def validate_bugs_found(filepath: str = "BUGS_FOUND.md") -> int:
    """Count documented bugs."""
    if not check_file_exists(filepath):
        return 0

    with open(filepath, 'r') as f:
        content = f.read()

    # Count bug entries (looking for patterns like "## Bug" or "### BUG")
    bugs = re.findall(r'^#{2,3}\s*(?:Bug|BUG)', content, re.MULTILINE)
    return len(bugs)


def main():
    """Run all validation checks."""
    print("\n" + "=" * 60)
    print("SDET Assessment Submission Validator")
    print("=" * 60 + "\n")

    all_passed = True

    # Check required files
    print("Checking required files...")

    required_files = [
        "tests/conftest.py",
        "tests/test_starter.py",
    ]

    for filepath in required_files:
        exists = check_file_exists(filepath)
        print_status(filepath, 'PASS' if exists else 'FAIL')
        if not exists:
            all_passed = False

    # Check BUGS_FOUND.md
    bugs_found = validate_bugs_found()
    bugs_file_exists = check_file_exists("BUGS_FOUND.md")
    print_status(
        f"BUGS_FOUND.md ({bugs_found} bugs documented)",
        'PASS' if bugs_found >= 2 else 'WARN' if bugs_file_exists else 'FAIL'
    )
    if bugs_found < 2:
        all_passed = False

    print()

    # Check TODO completion
    print("Checking TODO completion...")

    conftest_todos, conftest_passes, _ = check_todos_completed("tests/conftest.py")
    starter_todos, starter_passes, _ = check_todos_completed("tests/test_starter.py")

    print_status(
        f"conftest.py: {conftest_todos} TODOs, {conftest_passes} incomplete",
        'PASS' if conftest_todos == 0 and conftest_passes == 0 else 'WARN'
    )
    print_status(
        f"test_starter.py: {starter_todos} TODOs, {starter_passes} incomplete",
        'PASS' if starter_todos == 0 and starter_passes == 0 else 'WARN'
    )

    print()

    # Run tests
    print("Running tests...")

    passed, failed, success = run_tests("tests/test_starter.py")
    total = passed + failed

    pass_rate = (passed / total * 100) if total > 0 else 0
    status = 'PASS' if pass_rate >= 70 else 'WARN' if pass_rate >= 50 else 'FAIL'

    print_status(
        f"Test results: {passed}/{total} passed ({pass_rate:.1f}%)",
        status
    )

    if pass_rate < 70:
        all_passed = False

    print()

    # Summary
    print("=" * 60)
    if all_passed:
        print(f"{GREEN}SUBMISSION VALID{RESET}")
        print("All minimum requirements met.")
    else:
        print(f"{YELLOW}SUBMISSION INCOMPLETE{RESET}")
        print("Some requirements not met. Review the items above.")

    print("=" * 60)

    # Return exit code
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
