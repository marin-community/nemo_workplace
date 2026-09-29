# Copyright The Marin Authors
# SPDX-License-Identifier: Apache-2.0

"""Pinned NeMo Workplace provider for one isolated Harbor trial."""

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .tools import CASE_SENSITIVE_COLUMNS, get_tools, source_state

ACTION_INTERFACE = "workplace:v1"
SEED_SHA256 = "abcfd3d4727c66b6dfc145b59f720b819ac9de1b65df285cd30bc80bc10b3b8b"
PROVIDER_REVISION = "1e668906d2e69a9e8ee9aaafc60050a4025d9688"
TOOLS_SHA256 = "16126f168b1cc4c3dde3eb90721f28acf2bdf47a2d887457fc4f38cd54470516"
REQUEST_TEMPERATURE = 1.0
REQUEST_PARALLEL_TOOL_CALLS = False


def _seed_digest() -> str:
    root = Path(__file__).parent / "vendor/csv_data"
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.csv")):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _tool_definitions(schemas: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema.get("description"),
                "parameters": schema["parameters"],
                "strict": schema.get("strict", False),
            },
        }
        for schema in schemas
    )


def _json_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Cannot encode {type(value).__name__}")


def state_snapshot(tool_env: dict[str, Any]) -> dict[str, Any]:
    """Normalize the mutable tables as the upstream state comparator does."""
    snapshot = {}
    for name, original in source_state(tool_env).items():
        frame = original.copy(deep=True)
        for column in frame.columns:
            if column not in CASE_SENSITIVE_COLUMNS:
                frame[column] = frame[column].str.lower()
        snapshot[name] = json.loads(frame.to_json(orient="split"))
    return snapshot


def expected_state_json(gold: list[dict[str, str]]) -> str:
    """Return the canonical state target for a source action sequence."""
    environment = get_tools()
    for action in gold:
        arguments = json.loads(action["arguments"])
        if not isinstance(arguments, dict):
            raise ValueError("Workplace ground truth arguments must be an object")
        environment["functions"][action["name"]](**arguments)
    return json.dumps(state_snapshot(environment), sort_keys=True, separators=(",", ":"))


# The source schema list is immutable package data; each trial constructs its own tool state.
TOOL_DEFINITIONS = _tool_definitions(get_tools()["schemas"])


@dataclass(frozen=True)
class ToolTrace:
    call_id: str
    name: str
    arguments: str
    output: str


class NemoWorkplaceProvider:
    """One fresh copy of the upstream mutable Workplace tools per Harbor trial."""

    ACTION_INTERFACE = ACTION_INTERFACE
    SEED_SHA256 = SEED_SHA256
    PROVIDER_REVISION = PROVIDER_REVISION
    TOOLS_SHA256 = TOOLS_SHA256
    TOOL_DEFINITIONS = TOOL_DEFINITIONS
    REQUEST_TEMPERATURE = REQUEST_TEMPERATURE
    REQUEST_PARALLEL_TOOL_CALLS = REQUEST_PARALLEL_TOOL_CALLS
    SUPPORTS_AGENT_FILES = False

    def __init__(
        self,
        seed_sha256: str,
        action_interface: str = ACTION_INTERFACE,
    ) -> None:
        if action_interface != ACTION_INTERFACE:
            raise ValueError("NeMo Workplace action interface does not match its provider")
        if seed_sha256 != SEED_SHA256 or _seed_digest() != SEED_SHA256:
            raise ValueError("NeMo Workplace seed does not match its pinned digest")
        if _json_digest(TOOL_DEFINITIONS) != TOOLS_SHA256:
            raise ValueError("NeMo Workplace tools do not match their pinned schemas")
        self.tool_env = get_tools()
        self.trace: list[ToolTrace] = []

    async def native_tool_definitions(self) -> list[dict[str, Any]]:
        return deepcopy(list(self.TOOL_DEFINITIONS))

    async def dispatch_action(self, name: str, arguments: str, call_id: str) -> str:
        try:
            payload = json.loads(arguments)
            if not isinstance(payload, dict):
                raise ValueError("Tool arguments must be a JSON object")
            output = self.tool_env["functions"][name](**payload)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            output = f"Error executing tool '{name}': {error}"
        encoded = json.dumps({"output": output}, default=_json_default, separators=(",", ":"))
        self.trace.append(ToolTrace(call_id=call_id, name=name, arguments=arguments, output=encoded))
        return encoded

    def canonical_state(self) -> dict[str, Any]:
        """Export the authoritative tables with upstream comparison normalization."""
        return state_snapshot(self.tool_env)
