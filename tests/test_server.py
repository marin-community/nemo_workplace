# Copyright The Marin Authors
# SPDX-License-Identifier: Apache-2.0

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from nemo_workplace.provider import (
    ACTION_INTERFACE,
    PROVIDER_REVISION,
    SEED_SHA256,
    NemoWorkplaceProvider,
    expected_state_json,
)

PINS = {
    "action_interface": ACTION_INTERFACE,
    "provider_revision": PROVIDER_REVISION,
    "seed_sha256": SEED_SHA256,
}
REPLY = {
    "email_id": "00000057",
    "body": "Thanks for the update - I will get back to you tomorrow.",
}


def request(request_id, method, params):
    return {"id": request_id, "method": method, "params": params}


def run_server(requests, container_image):
    command = [sys.executable, "-m", "nemo_workplace.server"]
    if container_image:
        command = [
            "docker",
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65532:65532",
            "-i",
            container_image,
            "python",
            "-m",
            "nemo_workplace.server",
        ]
    wire = "".join(
        (item if isinstance(item, str) else json.dumps(item)) + "\n"
        for item in requests
    )
    completed = subprocess.run(
        command, input=wire, text=True, capture_output=True, timeout=30, check=True
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(responses) == len(requests)
    return responses


@pytest.mark.parametrize("body", [REPLY["body"], "A different reply", None])
def test_server_state_tracks_success_wrong_and_noop_submissions(body, container_image):
    actions = (
        []
        if body is None
        else [
            request(
                "reply",
                "call",
                {
                    "name": "email_reply_email",
                    "arguments": json.dumps({**REPLY, "body": body}),
                    "call_id": "reply-1",
                },
            )
        ]
    )
    responses = run_server(
        [request("init", "initialize", PINS), *actions, request("state", "state", {})],
        container_image,
    )
    expected = json.loads(
        expected_state_json(
            [{"name": "email_reply_email", "arguments": json.dumps(REPLY)}]
        )
    )
    assert responses[0]["result"]["tools"][0]["type"] == "function"
    assert len(responses[0]["result"]["tools"]) == 27
    assert (responses[-1]["result"] == expected) == (body == REPLY["body"])
    if body is None:
        assert (
            responses[-1]["result"]
            == NemoWorkplaceProvider(seed_sha256=SEED_SHA256).canonical_state()
        )


def test_server_recovers_tool_error_and_never_replays_call(container_image):
    reply = {
        "name": "email_reply_email",
        "arguments": json.dumps(REPLY),
        "call_id": "reply-1",
    }
    responses = run_server(
        [
            request("init", "initialize", PINS),
            request(
                "bad", "call", {**reply, "arguments": "broken-json", "call_id": "bad-1"}
            ),
            request("error-state", "state", {}),
            request("reply", "call", reply),
            request("before", "state", {}),
            request("duplicate-call", "call", reply),
            request("reply", "call", {**reply, "call_id": "new-id"}),
            request("after", "state", {}),
        ],
        container_image,
    )
    assert isinstance(json.loads(responses[1]["result"])["output"], str)
    assert (
        responses[2]["result"]
        == NemoWorkplaceProvider(seed_sha256=SEED_SHA256).canonical_state()
    )
    assert "error" not in responses[3]
    assert "error" in responses[5] and "error" in responses[6]
    assert responses[4]["result"] == responses[7]["result"]
    assert (
        responses[4]["result"]
        != NemoWorkplaceProvider(seed_sha256=SEED_SHA256).canonical_state()
    )


def test_server_processes_are_fresh_and_concurrently_isolated(container_image):
    base = [request("init", "initialize", PINS)]
    mutated = [
        *base,
        request(
            "call",
            "call",
            {
                "name": "email_reply_email",
                "arguments": json.dumps(REPLY),
                "call_id": "1",
            },
        ),
        request("state", "state", {}),
    ]
    untouched = [*base, request("state", "state", {})]
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(
            pool.map(
                lambda requests: run_server(requests, container_image),
                [mutated, untouched],
            )
        )
    fresh = run_server(untouched, container_image)
    assert first[-1]["result"] != second[-1]["result"]
    assert second[-1]["result"] == fresh[-1]["result"]


def test_server_rejects_bad_identity_and_protocol_without_dispatch(container_image):
    responses = run_server(
        [
            request("bad-init", "initialize", {**PINS, "seed_sha256": "0" * 64}),
            request("state-before-init", "state", {}),
            request("init", "initialize", PINS),
            '{"id":"duplicate-key","method":"state","params":{},"params":{}}',
            request("second-init", "initialize", PINS),
            request("state", "state", {}),
        ],
        container_image,
    )
    assert all("error" in responses[i] for i in [0, 1, 3, 4])
    assert (
        responses[-1]["result"]
        == NemoWorkplaceProvider(seed_sha256=SEED_SHA256).canonical_state()
    )
