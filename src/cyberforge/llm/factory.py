"""Composition root; construction never opens clients or makes API calls."""

from cyberforge.llm.config import GatewayConfig
from cyberforge.llm.contracts import GenerationRequest, Provider
from cyberforge.llm.gateway import LLMGateway
from cyberforge.llm.gemini_provider import GeminiProvider
from cyberforge.llm.groq_provider import GroqProvider
from cyberforge.llm.mock import MockLLMProvider


def create_gateway(config: GatewayConfig | None = None) -> LLMGateway:
    config = config or GatewayConfig()
    return LLMGateway(
        config,
        {
            Provider.MOCK: MockLLMProvider(),
            Provider.GEMINI: GeminiProvider(config.google_api_key),
            Provider.GROQ: GroqProvider(config.groq_api_key),
        },
    )


def configured_request(config: GatewayConfig, **kwargs) -> GenerationRequest:
    """Use config defaults while keeping each gateway request fully explicit."""
    return GenerationRequest(
        provider=config.provider,
        model=config.model,
        parameters=config.parameters,
        **kwargs,
    )
