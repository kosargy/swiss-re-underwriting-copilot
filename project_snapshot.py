from __future__ import annotations

import json
from typing import Any, Collection, Mapping


SCHEMA = "swiss-re-underwriting-project"
VERSION = 1
MAX_FILE_SIZE = 1_000_000
Primitive = str | int | float | bool


def build_project_snapshot(
    *,
    strategy: str,
    project_name: str,
    widget_values: Mapping[str, Primitive],
) -> bytes:
    payload = {
        "schema": SCHEMA,
        "version": VERSION,
        "strategy": strategy,
        "project_name": project_name,
        "widget_values": dict(widget_values),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def parse_project_snapshot(
    data: bytes,
    *,
    expected_strategy: str,
    allowed_keys: Collection[str],
) -> dict[str, Any]:
    if len(data) > MAX_FILE_SIZE:
        raise ValueError("Project file is larger than 1 MB")

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Project file is not valid JSON") from error

    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("Unsupported project-file schema")
    if payload.get("version") != VERSION:
        raise ValueError("Unsupported project-file version")
    if payload.get("strategy") != expected_strategy:
        raise ValueError(
            f"This file belongs to {payload.get('strategy', 'another workflow')}"
        )

    widget_values = payload.get("widget_values")
    if not isinstance(widget_values, dict):
        raise ValueError("Project assumptions are missing")

    allowed = set(allowed_keys)
    safe_values = {
        key: value
        for key, value in widget_values.items()
        if key in allowed
        and isinstance(key, str)
        and isinstance(value, (str, int, float, bool))
    }
    if not safe_values:
        raise ValueError("No compatible assumptions were found")

    project_name = payload.get("project_name")
    return {
        "strategy": expected_strategy,
        "project_name": (
            project_name if isinstance(project_name, str) else "Imported project"
        ),
        "widget_values": safe_values,
    }
