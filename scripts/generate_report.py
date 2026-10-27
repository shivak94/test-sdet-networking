#!/usr/bin/env python3
"""
Report Generator for SDET Assessment

Generates a summary report of a candidate's submission.

Usage:
    python scripts/generate_report.py > submission_report.md
"""
import os
import sys
import subprocess
import re
from pathlib import Path
from datetime import datetime


def get_git_info():
    """Get git branch and commit info."""
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True
        ).stdout.strip()

        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True
        ).stdout.strip()

        return branch, commit
    except Exception:
        return "unknown", "unknown"


def count_fixtures_implemented(filepath: str) -> tuple:
    """Count implemented vs total fixtures."""
    if not Path(filepath).exists():
        return 0, 0

    with open(filepath, 'r') as f:
        content = f.read()

    # Count fixture definitions
    total_fixtures = len(re.findall(r'@pytest\.fixture', content))

    # Count incomplete (have 'pass' or 'YOUR CODE HERE')
    incomplete = len(re.findall(r'#\s*YOUR CODE HERE', content, re.IGNORECASE))

    return total_fixtures - incomplete, total_fixtures


def count_tests_implemented(filepath: str) -> tuple:
    """Count implemented vs total tests."""
    if not Path(filepath).exists():
        return 0, 0

    with open(filepath, 'r') as f:
        content = f.read()

    # Count test methods
    total_tests = len(re.findall(r'def test_\w+', content))

    # Count incomplete (have 'pass' as only body)
    incomplete = len(re.findall(r'def test_\w+.*\n\s+""".*?"""\n\s+#\s*YOUR CODE HERE\n\s+pass',
                                 content, re.DOTALL))

    return total_tests - incomplete, total_tests


def count_bugs_documented() -> int:
    """Count bugs in BUGS_FOUND.md."""
    filepath = "BUGS_FOUND.md"
    if not Path(filepath).exists():
        return 0

    with open(filepath, 'r') as f:
        content = f.read()

    # Count bug sections
    bugs = re.findall(r'^#{2,3}\s*(?:Bug|BUG)', content, re.MULTILINE)
    return len(bugs)


def run_tests_with_coverage() -> dict:
    """Run tests and get coverage data."""
    try:
        result = subprocess.run(
            ["pytest", "tests/test_starter.py", "-v", "--tb=no", "-q",
             "--cov=mock_nos", "--cov-report=term-missing"],
            capture_output=True,
            text=True,
            timeout=120
        )

        output = result.stdout + result.stderr

        # Parse results
        passed = 0
        failed = 0
        coverage = 0

        passed_match = re.search(r'(\d+) passed', output)
        failed_match = re.search(r'(\d+) failed', output)
        coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', output)

        if passed_match:
            passed = int(passed_match.group(1))
        if failed_match:
            failed = int(failed_match.group(1))
        if coverage_match:
            coverage = int(coverage_match.group(1))

        return {
            "passed": passed,
            "failed": failed,
            "total": passed + failed,
            "coverage": coverage,
            "success": result.returncode == 0
        }

    except Exception as e:
        return {
            "passed": 0,
            "failed": 0,
            "total": 0,
            "coverage": 0,
            "success": False,
            "error": str(e)
        }


def main():
    """Generate the report."""
    branch, commit = get_git_info()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Gather data
    fixtures_impl, fixtures_total = count_fixtures_implemented("tests/conftest.py")
    tests_impl, tests_total = count_tests_implemented("tests/test_starter.py")
    bugs_found = count_bugs_documented()
    test_results = run_tests_with_coverage()

    # Calculate scores
    fixture_score = (fixtures_impl / fixtures_total * 100) if fixtures_total > 0 else 0
    test_impl_score = (tests_impl / tests_total * 100) if tests_total > 0 else 0
    test_pass_rate = (test_results["passed"] / test_results["total"] * 100) if test_results["total"] > 0 else 0

    # Generate report
    report = f"""# SDET Assessment Submission Report

**Generated**: {timestamp}
**Branch**: {branch}
**Commit**: {commit}

---

## Summary

| Metric | Value | Score |
|--------|-------|-------|
| Fixtures Implemented | {fixtures_impl}/{fixtures_total} | {fixture_score:.0f}% |
| Tests Implemented | {tests_impl}/{tests_total} | {test_impl_score:.0f}% |
| Tests Passing | {test_results['passed']}/{test_results['total']} | {test_pass_rate:.0f}% |
| Code Coverage | {test_results['coverage']}% | - |
| Bugs Documented | {bugs_found} | {'Pass' if bugs_found >= 2 else 'Needs More'} |

---

## Fixtures Status

| Fixture | Status |
|---------|--------|
| databases | {'Implemented' if fixture_score > 0 else 'Not Started'} |
| bgp_session_with_neighbor | - |
| established_bgp_neighbor | - |
| ospf_instance | - |
| swss_container | - |
| port_manager_with_ports | - |
| small_topology | - |
| wait_for_bgp_convergence | - |

---

## Test Results

**Total Tests**: {test_results['total']}
**Passed**: {test_results['passed']}
**Failed**: {test_results['failed']}
**Pass Rate**: {test_pass_rate:.1f}%

---

## Bug Detection

**Bugs Documented**: {bugs_found}
**Minimum Required**: 2

---

## Evaluation Notes

_(To be filled by reviewer)_

### Strengths


### Areas for Improvement


### Overall Assessment


---

## Files Reviewed

- [ ] tests/conftest.py
- [ ] tests/test_starter.py
- [ ] BUGS_FOUND.md
"""

    print(report)


if __name__ == "__main__":
    main()
