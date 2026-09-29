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
