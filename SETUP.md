# Setup Guide

This guide provides detailed setup instructions for the NOS SDET Assessment.

## System Requirements

- **Operating System**: Linux, macOS, or Windows (with WSL recommended)
- **Python**: 3.9, 3.10, or 3.11
- **Memory**: 4GB RAM minimum
- **Disk**: 500MB free space

## Installation Steps

### 1. Clone the Repository

```bash
git clone <repository-url>
cd test-sdet-networking
```

### 2. Create Virtual Environment

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### 3. Install Dependencies

```bash
# Upgrade pip first
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt

# Install the mock_nos package in development mode
pip install -e .
```

### 4. Verify Installation

```bash
# Check Python version
python --version  # Should be 3.9+

# Check pytest is installed
pytest --version

# Run example tests to verify everything works
pytest tests/examples/ -v
```

Expected output:
```
========================= test session starts ==========================
collected X items

tests/examples/test_patterns.py::test_example_fixture PASSED
tests/examples/test_patterns.py::test_example_parametrize PASSED
...
========================= X passed in 0.XXs ============================
```

## IDE Setup (Optional)

### VS Code

1. Install the Python extension
2. Select your virtual environment interpreter (Ctrl+Shift+P > "Python: Select Interpreter")
3. Install recommended extensions: Python, Pylance, Python Test Explorer

**settings.json:**
```json
{
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"],
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true
}
```

### PyCharm

1. Open the project directory
2. Configure the Python interpreter (Settings > Project > Python Interpreter)
3. Mark the `tests` directory as "Test Sources Root"

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError: No module named 'mock_nos'`:

```bash
# Make sure you're in the virtual environment
source venv/bin/activate  # or equivalent for your OS

# Reinstall in development mode
pip install -e .
```

### pytest Not Found

```bash
pip install pytest pytest-cov pytest-timeout
```

### Permission Errors (Linux/macOS)

```bash
# If you get permission errors
pip install --user -r requirements.txt
pip install --user -e .
```

### Windows Path Issues

If you encounter path-related issues on Windows:

1. Use forward slashes in Python code
2. Run commands from the project root directory
3. Consider using WSL for a more Linux-like environment

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=mock_nos --cov-report=html
# Open htmlcov/index.html in browser to view report

# Run specific test file
pytest tests/test_starter.py -v

# Run specific test class
pytest tests/test_starter.py::TestBGPBasic -v

# Run specific test method
pytest tests/test_starter.py::TestBGPBasic::test_bgp_session_creation -v

# Run only bonus tests
pytest tests/ -v -m "bonus"

# Skip bonus tests
pytest tests/ -v -m "not bonus"
```

### Useful pytest Flags

```bash
# Show print statements
pytest -v -s

# Stop on first failure
pytest -v -x

# Run last failed tests
pytest -v --lf

# Show local variables in tracebacks
pytest -v --showlocals

# Set timeout (60 seconds)
pytest -v --timeout=60
```

## Project Structure Reference

```
test-sdet-networking/
├── mock_nos/                # Mock NOS package (read-only for candidates)
│   ├── __init__.py
│   ├── errors.py            # Custom exceptions
│   ├── database/            # Database layer
│   │   ├── redis_mock.py    # In-memory key-value store
│   │   ├── config_db.py     # Configuration database
│   │   └── state_db.py      # State database
│   ├── protocols/           # Protocol implementations
│   │   ├── bgp.py           # BGP state machine
│   │   └── ospf.py          # OSPF implementation
│   ├── containers/          # Container mocks
│   │   ├── base_container.py
│   │   ├── bgp_container.py
│   │   └── swss_container.py
│   ├── hal/                 # Hardware abstraction
│   │   ├── port_manager.py
│   │   └── route_manager.py
│   └── topology/            # Topology utilities
│       ├── device.py
│       └── topology_builder.py
├── data/                    # Test data
│   ├── topologies/          # Topology definitions
│   └── configs/             # Configuration files
├── tests/                   # Your test files
│   ├── conftest.py          # Fixtures (complete TODOs)
│   ├── test_starter.py      # Tests (complete TODOs)
│   └── examples/            # Reference examples
├── docs/                    # Documentation
└── scripts/                 # Utility scripts
```

## Next Steps

1. Read the main [README.md](README.md) for assessment overview
2. Review your track's task document in `docs/`
3. Study the example tests in `tests/examples/`
4. Review `docs/ARCHITECTURE.md` for system understanding
5. Check `docs/PROTOCOL_REFERENCE.md` for networking concepts
6. Start implementing your tests!
