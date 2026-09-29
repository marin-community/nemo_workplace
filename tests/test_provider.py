import asyncio
import importlib
import importlib.util
import json
import sys
from pathlib import Path

from nemo_workplace.provider import SEED_SHA256, NemoWorkplaceProvider


def test_provider_state_is_fresh_and_actions_are_isolated():
    first = NemoWorkplaceProvider(seed_sha256=SEED_SHA256)
    second = NemoWorkplaceProvider(seed_sha256=SEED_SHA256)
    initial_state = second.canonical_state()
    action = {"email_id": "00000057", "body": "Thanks for the update - I will get back to you tomorrow."}

    async def exercise():
        definitions = await first.native_tool_definitions()
        output = await first.dispatch_action("email_reply_email", json.dumps(action), "call-1")
        return definitions, output

    definitions, output = asyncio.run(exercise())
    assert len(definitions) == 27
    assert "output" in json.loads(output)
    assert first.canonical_state() != initial_state
    assert second.canonical_state() == initial_state
    assert json.loads(json.dumps(first.canonical_state())) == first.canonical_state()


def test_canonical_state_preserves_source_normalization_and_is_detached():
    provider = NemoWorkplaceProvider(seed_sha256=SEED_SHA256)
    snapshot = provider.canonical_state()
    email = snapshot["email"]
    subject = email["data"][0][email["columns"].index("subject")]
    projects = snapshot["project_management"]
    list_name = projects["data"][0][projects["columns"].index("list_name")]
    crm = snapshot["customer_relationship_manager"]
    status = crm["data"][0][crm["columns"].index("status")]

    assert subject == "task update on develop prototype for payment gateway"
    assert list_name == "Backlog"
    assert status == "Lost"
    email["data"][0][email["columns"].index("subject")] = "changed"
    assert provider.canonical_state()["email"]["data"][0][email["columns"].index("subject")] == subject


def test_provider_loads_under_an_isolated_package_name(monkeypatch):
    package_path = Path(__file__).resolve().parents[1] / "src/nemo_workplace"
    package_name = "isolated_nemo_workplace"
    spec = importlib.util.spec_from_file_location(
        package_name,
        package_path / "__init__.py",
        submodule_search_locations=[str(package_path)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, package_name, package)
    spec.loader.exec_module(package)

    provider_module = importlib.import_module(f"{package_name}.provider")
    provider = provider_module.NemoWorkplaceProvider(seed_sha256=SEED_SHA256)
    assert provider.__class__.__module__ == f"{package_name}.provider"
    assert len(provider.TOOL_DEFINITIONS) == 27
