"""Explicit synthetic offline Web demonstration, never a cloud fallback."""

import json

from cyberforge.agents.web import WebScenarioAgentV2
from cyberforge.llm.config import GatewayConfig
from cyberforge.llm.contracts import Provider, ProviderResponse
from cyberforge.llm.gateway import LLMGateway
from cyberforge.llm.mock import MockLLMProvider
from cyberforge.web.contracts import WebInputV2
from cyberforge.web.presets import preset_components, wire_component


def demo_gateway(source: WebInputV2) -> LLMGateway:
    components = (
        source.previous.page.model_dump(mode="json")["components"]
        if source.previous
        else preset_components(source.preset)
    )
    if source.previous is None:
        components[0]["title"] = source.context.organization[:200]
        for c in components:
            if c["type"] == "hero":
                c["title"] = source.parameters.topic[:200]
                c["text"] = source.email.slots.main.body_text[:3000]
    if source.refinement:
        for c in components:
            if "text" in c and (
                source.refinement_scope != "component"
                or c["id"] == source.selected_component
            ):
                c["text"] = (
                    c["text"][:900] + "\nІнструкція офлайн-демо: " + source.refinement
                )[:3000]
                break
    page = source.previous.page if source.previous else None
    payload = dict(
        schema_version="web-slots-v2",
        context_token=WebScenarioAgentV2.context_token(source),
        internal_resource_id=source.context.internal_resource_id,
        tab_title=page.tab_title if page else "Навчальний портал",
        display_url=page.display_url
        if page
        else "https://portal.osvita.example/learning",
        theme=source.theme,
        color_mode=page.color_mode if page else "light",
        layout=page.layout if page else "standard",
        components=[wire_component(c) for c in components],
    )
    return LLMGateway(
        GatewayConfig(),
        {
            Provider.MOCK: MockLLMProvider(
                [ProviderResponse(text=json.dumps(payload, ensure_ascii=False))]
            )
        },
    )
