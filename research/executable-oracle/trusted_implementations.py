"""Trusted reference implementations for the executable oracle pilot.

These callables are checked-in fixtures, not model- or agent-generated code.
The oracle intentionally executes them in-process; generated code remains
outside the execution boundary until a separately reviewed sandbox exists.
"""

from __future__ import annotations

from typing import Any


def correct_reference(value: Any, *, allowed: frozenset[str]) -> None:
    """Independent implementation of the pinned applicable-axes contract."""
    if value is None:
        return
    if not isinstance(value, list) or not value or not all(isinstance(axis, str) and axis.strip() for axis in value):
        raise ValueError("applicable_axes must be a non-empty array of strings")
    if len(set(value)) != len(value):
        raise ValueError("applicable_axes must not contain duplicate rubric axes")
    unknown = [axis for axis in value if axis not in allowed]
    if unknown:
        raise ValueError(f"applicable_axes contains unknown rubric axis: {unknown[0]!r}")


def accepts_duplicates(value: Any, *, allowed: frozenset[str]) -> None:
    """Defective reference: forgets the duplicate-axis invariant."""
    if value is None:
        return
    if not isinstance(value, list) or not value or not all(isinstance(axis, str) and axis.strip() for axis in value):
        raise ValueError("applicable_axes must be a non-empty array of strings")
    unknown = [axis for axis in value if axis not in allowed]
    if unknown:
        raise ValueError(f"applicable_axes contains unknown rubric axis: {unknown[0]!r}")


def accepts_unknown(value: Any, *, allowed: frozenset[str]) -> None:
    """Defective reference: forgets the allowed-axis invariant."""
    if value is None:
        return
    if not isinstance(value, list) or not value or not all(isinstance(axis, str) and axis.strip() for axis in value):
        raise ValueError("applicable_axes must be a non-empty array of strings")
    if len(set(value)) != len(value):
        raise ValueError("applicable_axes must not contain duplicate rubric axes")


def rejects_optional_none(value: Any, *, allowed: frozenset[str]) -> None:
    """Defective reference: treats the optional null value as invalid."""
    if value is None:
        raise ValueError("applicable_axes is required")
    correct_reference(value, allowed=allowed)


def incomplete_reference(value: Any, *, allowed: frozenset[str]) -> None:
    """Defective reference: recognizes only the first positive examples."""
    if value is None or value == ["technical_correctness"]:
        return
    raise ValueError("unsupported applicable_axes example")


def runtime_error_on_rejection(value: Any, *, allowed: frozenset[str]) -> None:
    """Defective reference: raises an unexpected error for invalid inputs."""
    if value is None or value == ["technical_correctness"]:
        return
    raise RuntimeError("candidate execution failed while rejecting input")
