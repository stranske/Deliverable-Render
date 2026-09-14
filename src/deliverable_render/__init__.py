"""Render a structured store into deliverables: deep-linked static HTML hubs, manifest-gated decks, and memos

The two helpers below are the Template's scaffold and are exercised by tests/test_main.py.
They stay until real modules replace them, so the package always has a tested public surface.
"""

from deliverable_render.html import RenderSpec, render_html

__version__ = "0.1.0"
__all__ = ["greet", "add", "RenderSpec", "render_html"]


def greet(name: str) -> str:
    """Return a greeting message.

    Args:
        name: The name to greet.

    Returns:
        A greeting string.
    """
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum of a and b.
    """
    return a + b
