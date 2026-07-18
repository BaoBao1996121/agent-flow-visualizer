"""Validated semantics for safely aggregating canonical event measurements."""

from __future__ import annotations

import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MEASUREMENT_EXTENSION_KEY = "anthill.measurements"
MEASUREMENT_SCHEMA_VERSION = "1.0.0"

_REGISTRY = {
    "model_call.input_tokens": ("tokens", "model_call", "sum"),
    "model_call.output_tokens": ("tokens", "model_call", "sum"),
    "model_call.cached_tokens": ("tokens", "model_call", "sum"),
    "model_call.total_tokens": ("tokens", "model_call", "sum"),
    "model_call.duration_ms": ("ms", "model_call", "sum"),
    "model_call.cost_usd": ("usd", "model_call", "sum"),
    "tool.duration_ms": ("ms", "tool_call", "sum"),
    "code_call.duration_ms": ("ms", "code_call", "sum"),
    "compaction.duration_ms": ("ms", "compaction", "sum"),
    "run.elapsed_ms": ("ms", "run", "latest"),
}


class MeasurementSemantics(BaseModel):
    """The ownership and arithmetic contract for one event measurement."""

    model_config = ConfigDict(extra="forbid")

    aggregate_key: str = Field(min_length=1, max_length=128)
    unit: Literal["tokens", "ms", "usd"]
    scope: Literal["model_call", "tool_call", "code_call", "compaction", "run"]
    aggregation: Literal["sum", "latest"]
    temporality: Literal["delta", "cumulative", "unknown"]
    owner_id: str = Field(min_length=1, max_length=256)
    basis: str | None = Field(default=None, min_length=1, max_length=256)
    estimated: bool | None = None

    @field_validator("owner_id")
    @classmethod
    def owner_id_is_stable_text(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("owner_id cannot contain surrounding whitespace")
        if any(unicodedata.category(character) in {"Cc", "Cf"} for character in value):
            raise ValueError("owner_id cannot contain control or format characters")
        return value

    @field_validator("basis")
    @classmethod
    def basis_is_stable_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != value.strip():
            raise ValueError("basis cannot contain surrounding whitespace")
        if any(unicodedata.category(character) in {"Cc", "Cf"} for character in value):
            raise ValueError("basis cannot contain control or format characters")
        return value

    @model_validator(mode="after")
    def matches_registry(self) -> "MeasurementSemantics":
        expected = _REGISTRY.get(self.aggregate_key)
        if expected is None:
            raise ValueError("aggregate_key is not registered")
        if (self.unit, self.scope, self.aggregation) != expected:
            raise ValueError("measurement semantics do not match the aggregate registry")
        if self.aggregate_key == "model_call.cost_usd" and (
            not self.basis or self.estimated is None
        ):
            raise ValueError("model_call.cost_usd requires basis and estimated")
        return self


class MeasurementExtension(BaseModel):
    """Versioned extension envelope; adding it does not alter legacy events."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    items: dict[str, MeasurementSemantics]


def parse_measurement_semantics(
    extensions: dict[str, Any], measurement_key: str
) -> MeasurementSemantics | None:
    """Return validated semantics, or ``None`` for absent/untrusted metadata."""

    raw_extension = extensions.get(MEASUREMENT_EXTENSION_KEY)
    if not isinstance(raw_extension, dict):
        return None
    try:
        parsed = MeasurementExtension.model_validate(raw_extension)
    except ValueError:
        return None
    return parsed.items.get(measurement_key)


def measurement_semantics_extension(
    semantics: dict[str, MeasurementSemantics],
) -> dict[str, Any]:
    """Serialize adapter-owned semantics into the canonical extension envelope."""

    extension = MeasurementExtension(items=semantics)
    return {
        MEASUREMENT_EXTENSION_KEY: extension.model_dump(
            mode="json", exclude_none=True
        )
    }


def describe_measurement_contract() -> dict[str, Any]:
    """Publish the closed aggregation registry without exposing model internals."""

    return {
        "extension_key": MEASUREMENT_EXTENSION_KEY,
        "schema_version": MEASUREMENT_SCHEMA_VERSION,
        "registry": {
            key: {"unit": unit, "scope": scope, "aggregation": aggregation}
            for key, (unit, scope, aggregation) in sorted(_REGISTRY.items())
        },
        "temporalities": ["delta", "cumulative", "unknown"],
        "owner_id_required": True,
        "cost_requires": ["basis", "estimated"],
    }
