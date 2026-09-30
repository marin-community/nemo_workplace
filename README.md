# NeMo Workplace tool provider

This package exposes the 27 NeMo Workplace Assistant tools through
`nemo_workplace.provider:NemoWorkplaceProvider`. Each provider instance starts
from the same six CSV seed files and keeps its mutable tables in memory. A trial
can dispatch actions through `dispatch_action` and read normalized,
JSON-compatible authoritative state through `canonical_state`. Grading compares
that state with an independently constructed private expected state.

Install from a full Git commit so code, schemas, and seed data resolve together:

```sh
uv pip install 'git+https://github.com/marin-community/nemo_workplace.git@<commit>'
```

Construct a provider with the pinned `SEED_SHA256` from
`nemo_workplace.provider`. The provider checks the seed and tool schema digests
before serving tools. The immutable source revision is
`1e668906d2e69a9e8ee9aaafc60050a4025d9688` of
[NVIDIA-NeMo/Gym](https://github.com/NVIDIA-NeMo/Gym/tree/1e668906d2e69a9e8ee9aaafc60050a4025d9688/resources_servers/workplace_assistant).
`UPSTREAM_PROVENANCE.json` records the copied files, Git blob IDs, and SHA256
digests. `LICENSE` and `NOTICE` preserve the upstream Apache 2.0 attribution.

The source example row and its private gold action belong to the TaskCompendium
importer. This package only supplies the tools and their initial data. The
Hugging Face dataset card at revision
`c86a908379e0a361a573c395e175d3c1aa128e6c` declares CC BY 4.0;
that dataset is separate from this pinned Gym implementation.

## Container service

Build the service before launching a trial. The Dockerfile pins its Python base
by digest and installs the hashed dependency export from `uv.lock`:

```sh
docker buildx build --load --provenance=false -t nemo-workplace:service .
docker image inspect nemo-workplace:service --format '{{.Id}}'
```

Use the resulting immutable image identifier (or a published registry manifest
digest) for the trial. No registry image is published by this repository. Each
process owns fresh mutable state, retained until its stdin closes:

```sh
docker run --rm --pull never --network none --read-only --tmpfs /tmp \
  --cap-drop ALL --security-opt no-new-privileges --user 65532:65532 \
  -i <image-id> python -m nemo_workplace.server
```

The service needs no host mounts, workspace handle, Docker socket, or network.
The image includes the provider code, schemas, initial CSV data, and upstream
license/provenance files. It excludes dataset examples and gold action lists.

Requests are UTF-8 JSON objects on individual newline-terminated lines:
`{"id":"request-1","method":"state","params":{}}`. Responses contain
the same `id` and either `result` or `error: {"message": ...}`. The protocol
provides four methods:

| Method | Parameters | Result |
| --- | --- | --- |
| `initialize` | `action_interface`, `seed_sha256`, `provider_revision` | The checked identity, `tools_sha256`, and `tools` |
| `tools` | Empty object | OpenAI function definitions |
| `call` | `name`, `arguments` (JSON string), `call_id` | Provider observation (JSON string) |
| `state` | Empty object | Canonical JSON-compatible tables |

Initialize once with the exported pins before calling other methods. Request
and action IDs are nonempty strings and cannot be reused within the process.
Repeated IDs are rejected before executing a tool. Invalid tool arguments are
ordinary observations; service failures use the protocol error response.
Harnesses must treat protocol errors, unavailable state, and broken transports
as infrastructure failures. A valid state differing from the expected state is
a grading failure.

Objects require exactly their documented fields. Duplicate JSON keys and
nonstandard JSON constants are rejected. Request and response lines are limited
to 16 MiB, including their newline; exceeding that limit terminates the service.
Stdout carries protocol responses only; diagnostics go to stderr. This is a
small stdio transport, not an implementation of MCP.

Run the process suite locally or against an already-built image:

```sh
uv run --with pytest pytest
uv run --with pytest pytest --container-image <image-id>
```

Regenerate the dependency export after changing the lock:
`uv export --frozen --no-dev --no-emit-project --output-file requirements-container.txt`.
