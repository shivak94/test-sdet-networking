"""
Example Test Patterns

This file demonstrates pytest patterns and best practices that you can
use as reference for implementing your tests.

These tests are meant to be educational - study the patterns here and
apply them to your implementations in test_starter.py and conftest.py.
"""
import pytest
import time
from typing import List
from unittest.mock import Mock, patch


# =============================================================================
# BASIC TEST PATTERNS
# =============================================================================

class TestBasicPatterns:
    """Basic pytest patterns."""

    def test_simple_assertion(self):
        """Simple assertion test."""
        result = 2 + 2
        assert result == 4

    def test_multiple_assertions(self):
        """Test with multiple assertions."""
        data = {"name": "test", "value": 42}

        assert "name" in data
        assert "value" in data
        assert data["name"] == "test"
        assert data["value"] == 42

    def test_exception_handling(self):
        """Test that exceptions are raised correctly."""
        with pytest.raises(ValueError):
            int("not a number")

    def test_exception_message(self):
        """Test exception message content."""
        with pytest.raises(ValueError) as exc_info:
            raise ValueError("specific error message")

        assert "specific" in str(exc_info.value)


# =============================================================================
# FIXTURE PATTERNS
# =============================================================================

@pytest.fixture
def sample_list() -> List[int]:
    """Simple fixture returning a list."""
    return [1, 2, 3, 4, 5]


@pytest.fixture
def sample_dict() -> dict:
    """Simple fixture returning a dict."""
    return {"key1": "value1", "key2": "value2"}


class TestFixturePatterns:
    """Patterns for using fixtures."""

    def test_using_fixture(self, sample_list: List[int]):
        """Test using a simple fixture."""
        assert len(sample_list) == 5
        assert sum(sample_list) == 15

    def test_multiple_fixtures(self, sample_list: List[int], sample_dict: dict):
        """Test using multiple fixtures."""
        assert len(sample_list) == 5
        assert "key1" in sample_dict


# =============================================================================
# FIXTURE WITH SETUP/TEARDOWN
# =============================================================================

@pytest.fixture
def resource_with_cleanup():
    """
    Fixture demonstrating setup and teardown pattern.

    The code before 'yield' runs during setup.
    The code after 'yield' runs during teardown.
    """
    # Setup
    resource = {"status": "initialized", "data": []}
    resource["status"] = "ready"

    yield resource  # Test runs here

    # Teardown
    resource["data"].clear()
    resource["status"] = "cleaned"


class TestSetupTeardown:
    """Tests demonstrating setup/teardown patterns."""

    def test_resource_usage(self, resource_with_cleanup):
        """Test that uses resource with cleanup."""
        assert resource_with_cleanup["status"] == "ready"
        resource_with_cleanup["data"].append("test_item")
        assert len(resource_with_cleanup["data"]) == 1


# =============================================================================
# PARAMETERIZED TESTS
# =============================================================================

class TestParameterization:
    """Patterns for parameterized tests."""

    @pytest.mark.parametrize("input_val,expected", [
        (1, 1),
        (2, 4),
        (3, 9),
        (4, 16),
    ])
    def test_square(self, input_val: int, expected: int):
        """Parameterized test for square function."""
        result = input_val ** 2
        assert result == expected

    @pytest.mark.parametrize("name,age,expected_adult", [
        ("Alice", 25, True),
        ("Bob", 17, False),
        ("Charlie", 18, True),
    ])
    def test_multiple_params(self, name: str, age: int, expected_adult: bool):
        """Parameterized test with multiple parameters."""
        is_adult = age >= 18
        assert is_adult == expected_adult

    @pytest.mark.parametrize("invalid_input", [
        None,
        "",
        [],
        {},
    ])
    def test_invalid_inputs(self, invalid_input):
        """Test multiple invalid inputs."""
        # Example: testing that various falsy values are handled
        assert not invalid_input


# =============================================================================
# FIXTURE FACTORY PATTERN
# =============================================================================

@pytest.fixture
def make_user():
    """
    Factory fixture that returns a function to create users.

    This pattern is useful when you need to create multiple instances
    with different configurations in the same test.
    """
    created_users = []

    def _make_user(name: str, role: str = "user"):
        user = {"name": name, "role": role, "id": len(created_users) + 1}
        created_users.append(user)
        return user

    yield _make_user

    # Cleanup all created users
    created_users.clear()


class TestFactoryPattern:
    """Tests using the factory fixture pattern."""

    def test_create_single_user(self, make_user):
        """Create a single user."""
        user = make_user("Alice")
        assert user["name"] == "Alice"
        assert user["role"] == "user"

    def test_create_multiple_users(self, make_user):
        """Create multiple users with factory."""
        admin = make_user("Admin", role="admin")
        user1 = make_user("User1")
        user2 = make_user("User2")

        assert admin["role"] == "admin"
        assert user1["id"] != user2["id"]


# =============================================================================
# MARKERS
# =============================================================================

class TestMarkers:
    """Patterns for using pytest markers."""

    @pytest.mark.slow
    def test_slow_operation(self):
        """This test is marked as slow."""
        time.sleep(0.1)  # Simulate slow operation
        assert True

    @pytest.mark.skip(reason="Not implemented yet")
    def test_not_implemented(self):
        """This test is skipped."""
        pass

    @pytest.mark.skipif(True, reason="Condition met")
    def test_conditional_skip(self):
        """This test is conditionally skipped."""
        pass

    @pytest.mark.xfail(reason="Known bug")
    def test_expected_failure(self):
        """This test is expected to fail."""
        assert False  # This won't cause test failure


# =============================================================================
# MOCKING PATTERNS
# =============================================================================

class TestMocking:
    """Patterns for mocking in tests."""

    def test_simple_mock(self):
        """Test with a simple mock object."""
        mock_obj = Mock()
        mock_obj.method.return_value = 42

        result = mock_obj.method()

        assert result == 42
        mock_obj.method.assert_called_once()

    def test_mock_with_side_effect(self):
        """Test mock that raises an exception."""
        mock_obj = Mock()
        mock_obj.dangerous_method.side_effect = RuntimeError("Error!")

        with pytest.raises(RuntimeError):
            mock_obj.dangerous_method()

    @patch("time.sleep")
    def test_patch_decorator(self, mock_sleep):
        """Test using patch decorator."""
        time.sleep(1000)  # Won't actually sleep

        mock_sleep.assert_called_once_with(1000)


# =============================================================================
# ASSERTION PATTERNS
# =============================================================================

class TestAssertionPatterns:
    """Various assertion patterns."""

    def test_approximate_equality(self):
        """Test floating point approximate equality."""
        result = 0.1 + 0.2
        assert result == pytest.approx(0.3)

    def test_container_membership(self):
        """Test container membership."""
        items = [1, 2, 3, 4, 5]

        assert 3 in items
        assert 6 not in items

    def test_string_patterns(self):
        """Test string assertions."""
        message = "Hello, World!"

        assert message.startswith("Hello")
        assert message.endswith("!")
        assert "World" in message

    def test_dict_subset(self):
        """Test dictionary contains expected items."""
        data = {"a": 1, "b": 2, "c": 3}
        expected = {"a": 1, "b": 2}

        assert expected.items() <= data.items()


# =============================================================================
# BEST PRACTICES DEMONSTRATION
# =============================================================================

class TestBestPractices:
    """Demonstrating testing best practices."""

    def test_single_responsibility(self):
        """
        Each test should test ONE thing.

        This test only verifies string uppercase conversion.
        """
        input_str = "hello"
        result = input_str.upper()
        assert result == "HELLO"

    def test_descriptive_name_shows_expected_behavior(self):
        """Test names should describe expected behavior."""
        numbers = [3, 1, 4, 1, 5]
        sorted_numbers = sorted(numbers)
        assert sorted_numbers == [1, 1, 3, 4, 5]

    def test_arrange_act_assert(self):
        """
        Follow the Arrange-Act-Assert pattern.

        This makes tests clear and readable.
        """
        # Arrange
        items = ["apple", "banana", "cherry"]

        # Act
        result = ", ".join(items)

        # Assert
        assert result == "apple, banana, cherry"

    def test_independent_test(self):
        """
        Tests should be independent.

        They should not depend on other tests or shared state.
        """
        # This test is self-contained
        data = []
        data.append(1)
        data.append(2)
        assert data == [1, 2]
