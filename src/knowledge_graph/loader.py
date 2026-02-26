from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

KG_PATH = Path(__file__).parent / "cloudshare_kg.json"


@dataclass
class CompiledFailurePattern:
    """Pre-compiled failure pattern for efficient regex matching."""

    id: str
    name: str
    infra_layer: str
    category: str
    compiled_patterns: list[re.Pattern]
    description: str


@lru_cache(maxsize=1)
def load_kg() -> dict:
    """Load and validate the CloudShare KG JSON. Cached after first call.

    Raises ValueError if the JSON is missing required fields — never silently
    returns an empty/partial KG, as that would make all correlations return
    empty results with no warning.
    """
    with open(KG_PATH) as f:
        kg = json.load(f)
    _validate_kg(kg)
    return kg


def _validate_kg(kg: dict) -> None:
    """Validate KG JSON schema. Raises ValueError with field path on failure."""
    required_top_keys = {"metadata", "endpoints", "failure_patterns"}
    missing = required_top_keys - kg.keys()
    if missing:
        raise ValueError(f"KG JSON missing required top-level keys: {missing}")

    for ep in kg["endpoints"]:
        for field_name in ("id", "method", "path_pattern", "infra_layer", "async"):
            if field_name not in ep:
                raise ValueError(
                    f"Endpoint entry missing required field '{field_name}': "
                    f"{ep.get('id', 'UNKNOWN')}"
                )
        if not isinstance(ep["infra_layer"], list):
            raise ValueError(
                f"Endpoint '{ep['id']}': infra_layer must be a list, got {type(ep['infra_layer'])}"
            )
        if ep["path_pattern"] != ep["path_pattern"].lower():
            raise ValueError(
                f"Endpoint '{ep['id']}': path_pattern must be lowercase, "
                f"got '{ep['path_pattern']}'"
            )

    for fp in kg["failure_patterns"]:
        for field_name in ("id", "name", "infra_layer", "category", "regex_patterns"):
            if field_name not in fp:
                raise ValueError(
                    f"Failure pattern missing required field '{field_name}': "
                    f"{fp.get('id', 'UNKNOWN')}"
                )
        if not isinstance(fp["regex_patterns"], list) or len(fp["regex_patterns"]) == 0:
            raise ValueError(
                f"Failure pattern '{fp['id']}': regex_patterns must be a non-empty list"
            )


def compile_failure_patterns(kg: dict | None = None) -> list[CompiledFailurePattern]:
    """Pre-compile all failure pattern regexes. Call once at startup.

    Args:
        kg: The KG dict from load_kg(). If None, calls load_kg() automatically.

    Returns:
        List of CompiledFailurePattern with pre-compiled re.Pattern objects.
        Compiling at startup (not per-request) gives 10-50x speedup.
    """
    if kg is None:
        kg = load_kg()
    result = []
    for fp in kg.get("failure_patterns", []):
        compiled = [re.compile(p) for p in fp["regex_patterns"]]
        result.append(CompiledFailurePattern(
            id=fp["id"],
            name=fp["name"],
            infra_layer=fp["infra_layer"],
            category=fp["category"],
            compiled_patterns=compiled,
            description=fp.get("description", ""),
        ))
    return result


__all__ = ["load_kg", "compile_failure_patterns", "CompiledFailurePattern", "KG_PATH"]
