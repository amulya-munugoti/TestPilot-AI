"""A real passing case and a real, intentional demo failure."""


def add(left: int, right: int) -> int:
    return left + right


def test_add_positive_numbers():
    assert add(2, 3) == 5


def test_add_demo_failure():
    # Intentionally incorrect expected value to show a genuine pytest traceback.
    assert add(2, 2) == 5

