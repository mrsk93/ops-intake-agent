from dataclasses import dataclass

import pytest

from packages.providers.model import OpenAIResponsesProvider
from packages.providers.ports import ModelConfig


@dataclass
class FakeResponseContent:
    type: str
    refusal: str | None = None


@dataclass
class FakeResponseMessage:
    content: list[FakeResponseContent]


@dataclass
class FakeResponse:
    output_text: str
    output: list[FakeResponseMessage]
    status: str = "completed"
    id: str = "resp_fixture"
    usage: dict[str, int] | None = None


class FakeResponses:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.responses = FakeResponses(response)


@pytest.mark.asyncio
async def test_openai_adapter_uses_strict_responses_schema_and_disables_storage() -> None:
    client = FakeClient(
        FakeResponse(
            '{"schema_version":"1.0","fields":[]} ',
            [],
            usage={"input_tokens": 12, "output_tokens": 8},
        )
    )
    provider = OpenAIResponsesProvider(
        api_key="synthetic-key",
        model="synthetic-model",
        client=client,
    )
    result = await provider.extract(
        tenant_id="tenant-a",
        evidence=[],
        schema_version="1.0",
        prompt_version="prompt-1",
        output_schema={"type": "object", "additionalProperties": False},
        model_config=ModelConfig(model="synthetic-model"),
    )

    assert result["schema_version"] == "1.0"
    assert client.responses.kwargs["store"] is False
    assert client.responses.kwargs["text"]["format"]["type"] == "json_schema"
    assert "tools" not in client.responses.kwargs
    assert provider.last_usage.input_tokens == 12


@pytest.mark.asyncio
async def test_openai_adapter_routes_refusal_without_accepting_schema_data() -> None:
    client = FakeClient(
        FakeResponse(
            "",
            [FakeResponseMessage([FakeResponseContent("refusal", "synthetic refusal")])],
        )
    )
    provider = OpenAIResponsesProvider(
        api_key="synthetic-key", model="synthetic-model", client=client
    )
    with pytest.raises(Exception, match="refused"):
        await provider.extract(
            tenant_id="tenant-a", evidence=[], schema_version="1.0", prompt_version="prompt-1"
        )
