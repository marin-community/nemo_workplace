# Copyright The Marin Authors
# SPDX-License-Identifier: Apache-2.0

"""Serve one Workplace trial over a bounded JSON-lines transport."""

import asyncio
import json
import sys
from contextlib import redirect_stdout
from typing import Any, BinaryIO

from .provider import (
    ACTION_INTERFACE,
    PROVIDER_REVISION,
    SEED_SHA256,
    TOOLS_SHA256,
    NemoWorkplaceProvider,
)

MAX_LINE_BYTES = 16 * 1024 * 1024


def _object(value: Any, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"Expected object fields: {', '.join(sorted(fields))}")
    return value


def _string(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Expected a nonempty string")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> Any:
    raise ValueError(f"Invalid JSON constant: {value}")


class WorkplaceServer:
    """Own a fresh provider and reject repeated request and action IDs."""

    def __init__(self) -> None:
        self.provider: NemoWorkplaceProvider | None = None
        self.request_ids: set[str] = set()
        self.call_ids: set[str] = set()

    async def dispatch(self, request: dict[str, Any]) -> Any:
        request = _object(request, {"id", "method", "params"})
        request_id = _string(request["id"])
        if request_id in self.request_ids:
            raise ValueError("Request ID has already been used")
        self.request_ids.add(request_id)
        method = _string(request["method"])
        if method == "initialize":
            if self.provider is not None:
                raise ValueError("Provider is already initialized")
            params = _object(
                request["params"],
                {"seed_sha256", "action_interface", "provider_revision"},
            )
            if params != {
                "seed_sha256": SEED_SHA256,
                "action_interface": ACTION_INTERFACE,
                "provider_revision": PROVIDER_REVISION,
            }:
                raise ValueError("Provider identity does not match the requested pins")
            self.provider = NemoWorkplaceProvider(
                seed_sha256=SEED_SHA256, action_interface=ACTION_INTERFACE
            )
            return {
                "action_interface": ACTION_INTERFACE,
                "seed_sha256": SEED_SHA256,
                "provider_revision": PROVIDER_REVISION,
                "tools_sha256": TOOLS_SHA256,
                "tools": await self.provider.native_tool_definitions(),
            }
        if self.provider is None:
            raise ValueError("Provider has not been initialized")
        if method == "tools":
            _object(request["params"], set())
            return await self.provider.native_tool_definitions()
        if method == "state":
            _object(request["params"], set())
            return self.provider.canonical_state()
        if method == "call":
            params = _object(request["params"], {"name", "arguments", "call_id"})
            name = _string(params["name"])
            arguments = _string(params["arguments"])
            call_id = _string(params["call_id"])
            if call_id in self.call_ids:
                raise ValueError("Call ID has already been used")
            self.call_ids.add(call_id)
            return await self.provider.dispatch_action(
                name=name, arguments=arguments, call_id=call_id
            )
        raise ValueError(f"Unknown method: {method}")


async def serve(reader: BinaryIO, writer: BinaryIO) -> None:
    """Read sequential requests; emit only protocol responses on the wire."""
    server = WorkplaceServer()
    while line := reader.readline(MAX_LINE_BYTES + 1):
        if len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
            raise ValueError("Request exceeds line limit or is missing its newline")
        request_id = None
        try:
            request = json.loads(
                line.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            if isinstance(request, dict) and isinstance(request.get("id"), str):
                request_id = request["id"]
            # Upstream diagnostics must never become wire protocol bytes.
            with redirect_stdout(sys.stderr):
                result = await server.dispatch(request)
            response = {"id": request_id, "result": result}
        except (
            Exception
        ) as error:  # noqa: BLE001 - failures must cross the transport as protocol errors
            # Dispatch failures are harness errors, distinct from provider tool observations.
            response = {"id": request_id, "error": {"message": str(error)}}
        encoded = (
            json.dumps(response, separators=(",", ":"), allow_nan=False).encode()
            + b"\n"
        )
        if len(encoded) > MAX_LINE_BYTES:
            raise ValueError("Response exceeds line limit")
        writer.write(encoded)
        writer.flush()


def main() -> None:
    asyncio.run(serve(sys.stdin.buffer, sys.stdout.buffer))


if __name__ == "__main__":
    main()
