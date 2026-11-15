"""Optional compositions of the single component registry, also used by the demo."""

from cyberforge.web.contracts import REGISTRY


def default_component(kind: str, identifier: str) -> dict:
    title, text = "Навчальний портал", "Синтетичні матеріали для навчання."
    action = {"id": "confirm", "label": "Підтвердити"}
    data = dict(id=identifier, type=kind, variant="standard")
    if "title" in REGISTRY[kind].model_fields:
        data["title"] = title
    if "text" in REGISTRY[kind].model_fields:
        data["text"] = text
    if kind == "cards":
        data["items"] = [
            {"title": "Матеріали курсу", "text": "Огляд синтетичного заняття."}
        ]
    if kind == "form":
        data["fields"] = [
            {
                "id": "synthetic_login",
                "label": "Навчальний ідентифікатор",
                "kind": "synthetic_text",
            }
        ]
        action = {"id": "submit_synthetic", "label": "Перевірити навчальну форму"}
    if "actions" in REGISTRY[kind].model_fields:
        data["actions"] = [action]
    return data


def preset_components(preset: str) -> list[dict]:
    kinds = {
        "auto": ("header", "hero", "cards", "notice", "actions", "footer"),
        "login": ("header", "hero", "form", "notice", "footer"),
        "portal": ("header", "hero", "cards", "text", "actions", "footer"),
        "notice": ("header", "notice", "text", "actions", "footer"),
        "document": ("header", "hero", "document", "actions", "footer"),
    }[preset]
    return [default_component(kind, f"{kind}_{i}") for i, kind in enumerate(kinds)]


def wire_component(data: dict) -> dict:
    return dict(title="", text="", items=[], fields=[], actions=[]) | data
