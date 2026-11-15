"""Compact provider slots and richer canonical components; no executable data."""

import json
import re
import unicodedata
from hashlib import sha256
from typing import Annotated, Literal, Self
from urllib.parse import unquote, urlsplit

from pydantic import ConfigDict, Field, model_validator

from cyberforge.agents.contracts import EmailDraftV2, ScenarioInputV1, resource_id
from cyberforge.domain.scenarios import ScenarioParameters
from cyberforge.llm.contracts import Contract, ScenarioContextV1

ComponentType = Literal[
    "header", "hero", "text", "cards", "notice", "form", "actions", "document", "footer"
]
Preset = Literal["auto", "login", "portal", "notice", "document"]
Theme = Literal["academic", "corporate", "service"]
Variant = Literal["standard", "compact", "emphasis"]
Layout = Literal["standard", "wide", "centered"]
ActionId = Literal["inspect_address", "leave", "report", "confirm", "submit_synthetic"]
Scope = Literal["text", "component", "page"]
COMPONENTS = (
    "header",
    "hero",
    "text",
    "cards",
    "notice",
    "form",
    "actions",
    "document",
    "footer",
)
PRESETS = {
    "auto": "Автоматично",
    "login": "Авторизація",
    "portal": "Портал",
    "notice": "Повідомлення",
    "document": "Документ",
}
THEMES = {"academic": "Академічна", "corporate": "Корпоративна", "service": "Сервісна"}
ACTIONS = {
    "inspect_address": "Перевірити адресу",
    "leave": "Залишити сторінку",
    "report": "Повідомити",
    "confirm": "Підтвердити",
    "submit_synthetic": "Перевірити навчальну форму",
}
COMPONENT_LABELS = dict(
    zip(
        COMPONENTS,
        (
            "Шапка",
            "Головний блок",
            "Текст",
            "Картки",
            "Повідомлення",
            "Форма",
            "Дії",
            "Документ",
            "Підвал",
        ),
        strict=True,
    )
)


class ComponentPolicy(Contract):
    min_components: int = Field(default=3, ge=1, le=12)
    max_components: int = Field(default=12, ge=3, le=24)
    max_cards: int = Field(default=6, ge=1, le=12)
    max_fields: int = Field(default=3, ge=1, le=6)
    max_actions: int = Field(default=5, ge=1, le=5)
    max_payload: int = Field(default=24000, ge=1000, le=50000)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.min_components > self.max_components:
            raise ValueError("policy_order")
        return self


POLICY = ComponentPolicy()


def text_data(value: str, *, empty: bool = False, limit: int = 3000) -> None:
    # Text is escaped by the renderer even after this mandatory local gate.
    if (not empty and not value.strip()) or len(value) > limit:
        raise ValueError("text_bounds")
    if re.search(
        r"[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]|javascript:|data:|file:|"
        r"\b(?:sk-|gsk_)[a-zA-Z0-9_-]{12,}|AIza[a-zA-Z0-9_-]{20,}|"
        r"(?:api[_ -]?key|password|token)\s*[=:]\s*\S+|\$\(|```|"
        r"\b(?:eval|exec|os\.system|subprocess\.\w+)\s*\(",
        value,
        re.I,
    ):
        raise ValueError("unsafe_text")


def display_address(value: str) -> None:
    if (
        len(value) > 512
        or re.search(r"[\s\\\x00-\x1f\x7f]", value)
        or re.search(r"[\x00-\x20\x7f\\]", unquote(value))
        or any(unicodedata.category(c).startswith("C") for c in unquote(value))
    ):
        raise ValueError("display_url_syntax")
    try:
        url = urlsplit(value)
        host = (url.hostname or "").encode("idna").decode("ascii")
        if (
            url.scheme != "https"
            or not host
            or url.username is not None
            or url.password is not None
            or (url.port is not None and not 1 <= url.port <= 65535)
            or len(host) > 253
            or len(host.split(".")) < 2
            or any(
                not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", s)
                for s in host.split(".")
            )
            or re.search(r'[<>"{}|^`]', value)
        ):
            raise ValueError("display_url_syntax")
    except (ValueError, UnicodeError):
        raise ValueError("display_url_syntax") from None


class Data(Contract):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    @model_validator(mode="after")
    def bounded(self) -> Self:
        def walk(value):
            if isinstance(value, str):
                text_data(value, empty=True)
            elif isinstance(value, (list, tuple)):
                if len(value) > 24:
                    raise ValueError("collection_bounds")
                for item in value:
                    walk(item)
            elif isinstance(value, dict):
                for key, item in value.items():
                    if key != "display_url":
                        walk(item)

        walk(self.model_dump(mode="json"))
        return self


class CardV2(Data):
    title: str
    text: str

    @model_validator(mode="after")
    def required(self) -> Self:
        text_data(self.title, limit=200)
        text_data(self.text)
        return self


class FieldV2(Data):
    id: Literal["synthetic_login", "synthetic_code", "synthetic_confirmation"]
    label: str
    kind: Literal["synthetic_text", "confirmation"]

    @model_validator(mode="after")
    def required(self) -> Self:
        text_data(self.label, limit=200)
        if (self.id == "synthetic_confirmation") != (self.kind == "confirmation"):
            raise ValueError("field_kind")
        return self


class ActionV2(Data):
    id: ActionId
    label: str

    @model_validator(mode="after")
    def required(self) -> Self:
        text_data(self.label, limit=100)
        return self


class WebComponentSlotV2(Data):
    """All fields required, no unions/defaults/constraints in provider schema.

    Unused collections/text MUST be empty. Canonical conversion enforces exact
    type-specific properties instead of discarding unsupported model fields.
    """

    id: str
    type: ComponentType
    variant: Variant
    title: str
    text: str
    items: list[CardV2]
    fields: list[FieldV2]
    actions: list[ActionV2]


class WebSlotsV2(Data):
    schema_version: Literal["web-slots-v2"]
    context_token: str
    internal_resource_id: str
    tab_title: str
    display_url: str
    theme: Theme
    color_mode: Literal["light", "dark"]
    layout: Layout
    components: list[WebComponentSlotV2]

    @model_validator(mode="after")
    def canonical_check(self) -> Self:
        canonical_page(self)
        return self


class Component(Data):
    id: str
    variant: Variant = "standard"

    @model_validator(mode="after")
    def identifier(self) -> Self:
        resource_id(self.id)
        return self


class Header(Component):
    type: Literal["header"] = "header"
    title: str
    text: str


class Hero(Component):
    type: Literal["hero"] = "hero"
    title: str
    text: str
    actions: tuple[ActionV2, ...] = ()


class Text(Component):
    type: Literal["text"] = "text"
    title: str
    text: str


class Cards(Component):
    type: Literal["cards"] = "cards"
    title: str
    items: tuple[CardV2, ...]


class Notice(Component):
    type: Literal["notice"] = "notice"
    title: str
    text: str


class Form(Component):
    type: Literal["form"] = "form"
    title: str
    text: str
    fields: tuple[FieldV2, ...]
    actions: tuple[ActionV2, ...]


class Actions(Component):
    type: Literal["actions"] = "actions"
    actions: tuple[ActionV2, ...]


class Document(Component):
    type: Literal["document"] = "document"
    title: str
    text: str
    actions: tuple[ActionV2, ...] = ()


class Footer(Component):
    type: Literal["footer"] = "footer"
    text: str


REGISTRY = {
    c.model_fields["type"].default: c
    for c in (Header, Hero, Text, Cards, Notice, Form, Actions, Document, Footer)
}
WebComponentV2 = Annotated[
    Header | Hero | Text | Cards | Notice | Form | Actions | Document | Footer,
    Field(discriminator="type"),
]


class WebPageV2(Data):
    schema_version: Literal["web-page-v2"] = "web-page-v2"
    tab_title: str
    display_url: str
    internal_resource_id: str
    theme: Theme
    color_mode: Literal["light", "dark"] = "light"
    layout: Layout = "standard"
    components: tuple[WebComponentV2, ...]

    @model_validator(mode="after")
    def composition(self) -> Self:
        display_address(self.display_url)
        text_data(self.tab_title, limit=150)
        resource_id(self.internal_resource_id)
        if not POLICY.min_components <= len(self.components) <= POLICY.max_components:
            raise ValueError("component_count")
        if len({c.id for c in self.components}) != len(self.components):
            raise ValueError("duplicate_component_id")
        types = [c.type for c in self.components]
        if (
            types.count("header") > 1
            or types.count("footer") > 1
            or ("header" in types and types[0] != "header")
            or ("footer" in types and types[-1] != "footer")
        ):
            raise ValueError("component_order")
        for c in self.components:
            for name in ("title", "text"):
                if hasattr(c, name):
                    text_data(getattr(c, name), limit=200 if name == "title" else 3000)
            actions = getattr(c, "actions", ())
            if len(actions) > POLICY.max_actions or len({a.id for a in actions}) != len(
                actions
            ):
                raise ValueError("action_bounds")
            if c.type == "actions" and not actions:
                raise ValueError("actions_required")
            if isinstance(c, Cards) and not 1 <= len(c.items) <= POLICY.max_cards:
                raise ValueError("card_bounds")
            if isinstance(c, Form):
                if (
                    not 1 <= len(c.fields) <= POLICY.max_fields
                    or not actions
                    or len({f.id for f in c.fields}) != len(c.fields)
                    or "submit_synthetic" not in {a.id for a in actions}
                ):
                    raise ValueError("form_contract")
        if len(self.model_dump_json()) > POLICY.max_payload:
            raise ValueError("page_bounds")
        return self


def canonical_page(slots: WebSlotsV2) -> WebPageV2:
    components = []
    for slot in slots.components:
        data = slot.model_dump(mode="json")
        model = REGISTRY[slot.type]
        for key in ("title", "text", "items", "fields", "actions"):
            if key not in model.model_fields:
                if data.pop(key):
                    raise ValueError("incompatible_component_property")
        components.append(data)
    return WebPageV2.model_validate_json(
        json.dumps(
            {
                **slots.model_dump(
                    mode="json",
                    exclude={"schema_version", "context_token", "components"},
                ),
                "components": components,
            }
        )
    )


def fingerprint(value: dict) -> str:
    return sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def email_digest(email: EmailDraftV2) -> str:
    payload = email.model_dump(mode="json")
    payload["slots"].pop("context_token", None)
    return fingerprint(payload)


class EmailBindingV2(Contract):
    revision: int = Field(ge=1)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")


def source_digest(
    scenario_id: int,
    scenario_version: int,
    parameters: ScenarioParameters,
    context: ScenarioContextV1,
    email: EmailBindingV2,
) -> str:
    return fingerprint(
        dict(
            scenario_id=scenario_id,
            scenario_version=scenario_version,
            parameters=parameters.model_dump(mode="json"),
            context=context.model_dump(mode="json"),
            email=email.model_dump(mode="json"),
        )
    )


class WebDraftV3(Contract):
    schema_version: Literal["web-draft-v3"] = "web-draft-v3"
    renderer_version: Literal["web-renderer-v1"] = "web-renderer-v1"
    scenario_id: int = Field(ge=1)
    scenario_version: int = Field(ge=1)
    parameters: ScenarioParameters
    context: ScenarioContextV1
    email_binding: EmailBindingV2
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    preset: Preset
    page: WebPageV2

    @model_validator(mode="after")
    def bound(self) -> Self:
        if (
            self.page.internal_resource_id != self.context.internal_resource_id
            or self.source_digest
            != source_digest(
                self.scenario_id,
                self.scenario_version,
                self.parameters,
                self.context,
                self.email_binding,
            )
        ):
            raise ValueError("web_source_binding")
        return self


class WebInputV2(ScenarioInputV1):
    schema_version: Literal["web-input-v2"] = "web-input-v2"
    scenario_id: int = Field(ge=1)
    scenario_version: int = Field(ge=1)
    email: EmailDraftV2
    email_binding: EmailBindingV2
    preset: Preset = "auto"
    theme: Theme = "academic"
    previous: WebDraftV3 | None = Field(default=None, repr=False)
    refinement_scope: Scope = "page"
    selected_component: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        # V2 permits realistic display addresses in instructions. Keep the
        # legacy .invalid-only source validation unchanged for V1 callers.
        self.parameters.bounded_payload()
        resource_id(self.context.internal_resource_id)
        for value in (
            self.parameters.topic,
            self.parameters.audience,
            self.parameters.description,
            self.parameters.learning_objective,
            *self.parameters.tactics,
            self.context.organization,
            self.context.sender_name,
            self.context.premise,
            self.refinement,
        ):
            if value:
                text_data(value, limit=10000)
        if len(self.context.model_dump_json()) > 6000:
            raise ValueError("context_bounds")
        return self

    @model_validator(mode="after")
    def linkage(self) -> Self:
        if (
            self.email.scenario_id != self.scenario_id
            or self.email.scenario_version != self.scenario_version
            or self.email.parameters != self.parameters
            or self.email.artifact.context != self.context
            or self.email.provenance is None
            or email_digest(self.email) != self.email_binding.digest
        ):
            raise ValueError("saved_email_binding")
        if self.previous is not None:
            draft = WebDraftV3.model_validate_json(self.previous.model_dump_json())
            if draft.source_digest != source_digest(
                self.scenario_id,
                self.scenario_version,
                self.parameters,
                self.context,
                self.email_binding,
            ):
                raise ValueError("stale_web_source")
            if self.refinement_scope == "component" and self.selected_component not in {
                c.id for c in draft.page.components
            }:
                raise ValueError("selected_component_required")
        elif self.refinement_scope != "page":
            raise ValueError("previous_required")
        return self
