"""Bounded, explicit Groq strict subset; canonical validation remains Pydantic."""

from copy import deepcopy

from cyberforge.llm.contracts import ErrorCategory, GenerationError


def groq_strict_schema(schema: dict) -> dict:
    definitions = schema.get("$defs", {})

    def visit(node: dict, seen: frozenset[str] = frozenset(), depth: int = 0) -> dict:
        if depth > 12:
            raise GenerationError(ErrorCategory.SCHEMA)
        node = deepcopy(node)
        node.pop("title", None)
        node.pop("description", None)
        node.pop("$defs", None)
        if "$ref" in node:
            ref = node.pop("$ref")
            if (
                node
                or not ref.startswith("#/$defs/")
                or ref in seen
                or ref[8:] not in definitions
            ):
                raise GenerationError(ErrorCategory.SCHEMA)
            return visit(definitions[ref[8:]], seen | {ref}, depth + 1)
        if "const" in node:
            node["enum"] = [node.pop("const")]
        kind = node.get("type")
        if kind == "object":
            properties = node.get("properties", {})
            if (
                node.get("additionalProperties") is not False
                or set(node.get("required", [])) != set(properties)
                or set(node)
                - {"type", "properties", "required", "additionalProperties"}
            ):
                raise GenerationError(ErrorCategory.SCHEMA)
            node["properties"] = {
                key: visit(value, seen, depth + 1) for key, value in properties.items()
            }
        elif kind == "array":
            if set(node) != {"type", "items"}:
                raise GenerationError(ErrorCategory.SCHEMA)
            node["items"] = visit(node["items"], seen, depth + 1)
        elif kind in {"string", "integer", "number", "boolean", "null"}:
            if set(node) - {"type", "enum"}:
                raise GenerationError(ErrorCategory.SCHEMA)
        else:
            raise GenerationError(ErrorCategory.SCHEMA)
        return node

    if schema.get("type") != "object":
        raise GenerationError(ErrorCategory.SCHEMA)
    return visit(schema)
