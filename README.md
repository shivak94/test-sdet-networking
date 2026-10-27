# NOS SDET Technical Assessment

Welcome to the Network Operating System (NOS) SDET technical assessment. This repository contains a mock NOS environment designed to evaluate your skills in test automation, Python development, and networking fundamentals.

## Assessment Overview

You will work with a simulated NOS environment inspired by modern network operating systems like SONiC and VyOS. Your task is to complete test fixtures, implement test cases, and identify bugs in the mock implementation.

**Time Estimate**: 2-4 hours (depending on track)

## Quick Start

### Prerequisites

- Python 3.9 or higher
- pip or pipenv
- Git

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd test-sdet-networking

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the mock_nos package in development mode
pip install -e .

# Verify installation
pytest tests/examples/ -v
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=mock_nos --cov-report=html

# Run only non-bonus tests
pytest tests/ -v -m "not bonus"

# Run specific test file
pytest tests/test_starter.py -v
```

## Repository Structure

```
test-sdet-networking/
├── mock_nos/           # Mock NOS Python package (DO NOT MODIFY for bug fixes)
│   ├── database/       # Database layer (CONFIG_DB, STATE_DB)
│   ├── protocols/      # Protocol implementations (BGP, OSPF)
│   ├── containers/     # Container mocks (BGP, SWSS)
│   ├── hal/            # Hardware Abstraction Layer
│   └── topology/       # Network topology utilities
├── data/               # Sample configurations and topologies
├── tests/              # Test files (YOUR WORK GOES HERE)
│   ├── conftest.py     # Shared fixtures - complete the TODOs
│   ├── test_starter.py # Main test file - complete the TODOs
│   └── examples/       # Example test patterns for reference
├── docs/               # Documentation
│   ├── ARCHITECTURE.md # System architecture overview
│   └── PROTOCOL_REFERENCE.md  # BGP/OSPF reference guide
└── scripts/            # Utility scripts
```

## Your Tasks

Please refer to the task document for your specific track:

- **SDET Track**: [docs/TASK_SDET.md](docs/TASK_SDET.md)
- **Senior SDET Track**: [docs/TASK_SENIOR_SDET.md](docs/TASK_SENIOR_SDET.md)
- **Team Lead Track**: [docs/TASK_TEAM_LEAD.md](docs/TASK_TEAM_LEAD.md)

### Summary of Tasks

1. **Complete Fixtures** (`tests/conftest.py`): Implement the TODO fixtures
2. **Implement Tests** (`tests/test_starter.py`): Complete the TODO test cases
3. **Find Bugs**: The mock_nos module contains intentional bugs - find and document them
4. **Document Findings**: Create a `BUGS_FOUND.md` file listing discovered bugs

## Important Notes

- **DO NOT** modify files in `mock_nos/` to fix bugs - document them instead
- **DO** complete all TODO items in `tests/conftest.py` and `tests/test_starter.py`
- **DO** create additional test files if needed
- Use the `docs/PROTOCOL_REFERENCE.md` for networking protocol information
- Review `tests/examples/test_patterns.py` for pytest patterns and best practices

## Submission

When complete:

1. Ensure all your tests pass (except those testing buggy behavior)
2. Create `BUGS_FOUND.md` documenting discovered bugs
3. Push your changes to a branch named `submission/<your-name>`
4. Create a pull request to the `main` branch

## Evaluation Criteria

Your submission will be evaluated on:

- **Correctness**: Tests work and correctly validate behavior
- **pytest Skills**: Proper use of fixtures, parametrization, markers
- **Bug Detection**: Identification of planted bugs in mock_nos
- **Code Quality**: Clean, readable, well-documented code
- **Protocol Understanding**: Correct interpretation of BGP/OSPF concepts

## Getting Help

- Review the documentation in `docs/`
- Check the example tests in `tests/examples/`
- For networking concepts, refer to `docs/PROTOCOL_REFERENCE.md`

Good luck!
