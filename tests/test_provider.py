import asyncio
import json

from nemo_workplace.provider import SEED_SHA256, NemoWorkplaceProvider, state_snapshot


def test_provider_state_is_fresh_and_actions_are_isolated():
    first = NemoWorkplaceProvider(seed_sha256=SEED_SHA256)
    second = NemoWorkplaceProvider(seed_sha256=SEED_SHA256)
    initial_state = json.dumps(state_snapshot(second.tool_env))
    action = {"email_id": "00000057", "body": "Thanks for the update - I will get back to you tomorrow."}

    async def exercise():
        definitions = await first.native_tool_definitions()
        output = await first.dispatch_action("email_reply_email", json.dumps(action), "call-1")
        return definitions, output

    definitions, output = asyncio.run(exercise())
    assert len(definitions) == 27
    assert "output" in json.loads(output)
    assert first.grade_state(initial_state) == 0.0
    assert second.grade_state(initial_state) == 1.0
