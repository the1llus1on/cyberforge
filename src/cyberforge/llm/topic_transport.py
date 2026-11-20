"""Single-shot stateless transport for the closed D12-10 provider requests."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPException, HTTPSConnection

from pydantic import SecretStr

from cyberforge.analytics.topic_advisory import (
    AssistantTopicInputV1,
    TopicWireRequestV1,
    decode_selection,
)
from cyberforge.llm.config import validate_selection
from cyberforge.llm.contracts import ErrorCategory, GenerationError, Provider
from cyberforge.llm.secret_store import CloudProvider

ENDPOINTS = {
    "groq": ("api.groq.com", "/openai/v1/chat/completions"),
    "gemini": ("generativelanguage.googleapis.com", "/v1/interactions"),
}
MODE = "topic-only-stateless-v1"


@dataclass(frozen=True, slots=True, repr=False)
class TopicProviderRequest:
    provider: CloudProvider
    url: str
    model: str
    body: bytes


def make_topic_request(
    provider: CloudProvider, model: str, request: AssistantTopicInputV1
) -> TopicProviderRequest:
    validate_selection(Provider(provider), model, None)
    host, path = ENDPOINTS[provider]
    wire = TopicWireRequestV1.from_input(request)
    schema = json.loads(wire.response_schema)
    if provider == "groq":
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": wire.instructions},
                {"role": "user", "content": wire.payload},
            ],
            "max_completion_tokens": 2048,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "cyberforge_advisory",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
    else:
        body = {
            "model": model,
            "input": wire.instructions + "\n" + wire.payload,
            "store": False,
            "background": False,
            "stream": False,
            "generation_config": {
                "max_output_tokens": 2048,
                "thinking_summaries": "none",
            },
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            },
        }
    encoded = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return TopicProviderRequest(provider, f"https://{host}{path}", model, encoded)


def _selection_text(provider: CloudProvider, body: bytes) -> str:
    response = json.loads(body)
    if provider == "groq":
        (choice,) = response["choices"]
        if choice["finish_reason"] != "stop" or choice["message"].get("refusal"):
            raise ValueError
        return choice["message"]["content"]
    if response["status"] != "completed":
        raise ValueError
    sections = [
        part["text"]
        for step in response["steps"]
        if step["type"] == "model_output"
        for part in step["content"]
        if part["type"] == "text"
    ]
    (output,) = sections
    return output


def send_topic_request(
    request: AssistantTopicInputV1,
    preview: TopicProviderRequest,
    key: SecretStr,
    admit: Callable[[], bool],
    *,
    connection=HTTPSConnection,
) -> tuple[str, ...]:
    if make_topic_request(preview.provider, preview.model, request) != preview:
        raise GenerationError(ErrorCategory.REQUEST)
    host, path = ENDPOINTS[preview.provider]
    raw_key = key.get_secret_value()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if preview.provider == "groq":
        headers["Authorization"] = "Bearer " + raw_key
    else:
        headers["x-goog-api-key"] = raw_key
    transport = connection(host, timeout=12)
    try:
        if not admit():
            raise GenerationError(ErrorCategory.AUTHORIZATION)
        transport.request("POST", path, preview.body, headers)
        with transport.getresponse() as response:
            if response.status != 200:
                raise GenerationError(ErrorCategory.TRANSPORT)
            body = response.read(65537)
        if len(body) > 65536:
            raise GenerationError(ErrorCategory.VALIDATION)
        return decode_selection(_selection_text(preview.provider, body), request)
    except (TypeError, ValueError, KeyError, OSError, HTTPException):
        raise GenerationError(ErrorCategory.TRANSPORT) from None
    finally:
        transport.close()
