"""Behavior tests for the public API of synthetic_data."""

from __future__ import annotations

import pytest

import synthetic_data


def test_normalize_trims_and_lowercases() -> None:
    assert synthetic_data.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        synthetic_data.normalize(value)


def test_version_is_semver() -> None:
    parts = synthetic_data.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
