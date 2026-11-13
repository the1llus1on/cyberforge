"""Small stateless LangGraph, one optional content correction, no publication."""

from hashlib import sha256
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from pydantic import BaseModel, Field, ValidationError

from cyberforge.agents.prompts import build_prompt
from cyberforge.llm.contracts import (
    Contract,
    ErrorCategory,
    GenerationError,
    GenerationTelemetry,
)
from cyberforge.llm.factory import configured_request
from cyberforge.llm.gateway import LLMGateway
from cyberforge.llm.runnable import GatewayRunnable


class AgentResult[T: BaseModel](Contract):
    schema_version: Literal["agent-result-v1"] = "agent-result-v1"
    status: Literal["pending_review", "failed"]
    draft: T | None = Field(default=None, repr=False, exclude=True)
    error: ErrorCategory | None = None
    generation_count: int = Field(ge=0, le=2)
    prompt_version: str
    telemetry: tuple[GenerationTelemetry, ...] = ()
    # This state is not an interactive approval/checkpoint protocol.
    publication_allowed: Literal[False] = False


class State(TypedDict):
    source: BaseModel
    candidate: BaseModel | None
    draft: BaseModel | None
    count: int
    error: ErrorCategory | None
    repairable: bool
    telemetry: tuple[GenerationTelemetry, ...]


class SpecializedAgent:
    kind: str
    input_type: type[BaseModel]
    slots_type: type[BaseModel]

    def __init__(self, gateway: LLMGateway, *, max_corrections: int = 0) -> None:
        if type(max_corrections) is not int or max_corrections not in (0, 1):
            raise ValueError("max_corrections must be 0 or 1")
        self._gateway = gateway
        self._max_corrections = max_corrections
        self._runnable = GatewayRunnable(gateway, self.slots_type)
        builder = StateGraph(State)
        builder.add_node("generate", self._generate)
        builder.add_node("validate", self._validate)
        builder.add_edge(START, "generate")
        builder.add_edge("generate", "validate")
        builder.add_conditional_edges(
            "validate", self._route, {"generate": "generate", "end": END}
        )
        self._graph = builder.compile(checkpointer=False)

    @property
    def prompt_version(self) -> str:
        return f"{self.kind}-prompt-v1"

    @staticmethod
    def context_token(source: BaseModel) -> str:
        # Binds parameter/version/context identity independently of model claims.
        from cyberforge.agents.prompts import task_data

        data = task_data(source)
        data.pop("previous", None)
        import json

        return sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    def _generate(self, state: State) -> dict:
        try:
            prompt = build_prompt(
                self.kind,
                state["source"],
                self.context_token(state["source"]),
                state["count"] > 0,
            )
            request = configured_request(
                self._gateway.config,
                prompt=prompt,
                synthetic=True,
                operation="structured",
                prompt_version=self.prompt_version,
                schema_version=self.slots_type.model_fields[
                    "schema_version"
                ].annotation.__args__[0],
            )
            response = self._runnable.invoke(request)
            return {
                "candidate": response.structured,
                "error": None,
                "repairable": False,
                "count": state["count"] + 1,
                "telemetry": (*state["telemetry"], response.telemetry),
            }
        except GenerationError as exc:
            return {
                "candidate": None,
                "error": exc.category,
                "repairable": exc.category == ErrorCategory.VALIDATION,
                "count": state["count"] + 1,
                "telemetry": (
                    (*state["telemetry"], exc.telemetry)
                    if hasattr(exc, "telemetry")
                    else state["telemetry"]
                ),
            }
        except (ValidationError, ValueError, TypeError):
            return {
                "candidate": None,
                "error": ErrorCategory.REQUEST,
                "repairable": False,
                "count": state["count"],
            }

    def _validate(self, state: State) -> dict:
        if state["error"] is not None:
            return {"draft": None}
        try:
            candidate = self.slots_type.model_validate_json(
                state["candidate"].model_dump_json()
            )
            return {
                "draft": self.validate_output(state["source"], candidate),
                "error": None,
            }
        except GenerationError as exc:
            return {"draft": None, "error": exc.category, "repairable": False}
        except (ValidationError, ValueError, TypeError, AttributeError):
            return {
                "draft": None,
                "error": ErrorCategory.VALIDATION,
                "repairable": True,
            }

    def _route(self, state: State) -> str:
        if (
            state["error"]
            and state["repairable"]
            and state["count"] <= self._max_corrections
        ):
            return "generate"
        return "end"

    def validate_output(self, source, candidate):
        raise NotImplementedError

    def run(self, source: BaseModel) -> AgentResult:
        # Revalidate deep copies, including model_construct/model_copy inputs.
        # No external callbacks/config accepted, including process tracing defaults.
        with tracing_context(enabled=False):
            try:
                if type(source) is not self.input_type:
                    raise ValueError("input_type")
                source = self.input_type.model_validate_json(source.model_dump_json())
            except (ValidationError, ValueError, TypeError, GenerationError):
                return AgentResult(
                    status="failed",
                    error=ErrorCategory.REQUEST,
                    generation_count=0,
                    prompt_version=self.prompt_version,
                )
            result = self._graph.invoke(
                {
                    "source": source,
                    "candidate": None,
                    "draft": None,
                    "count": 0,
                    "error": None,
                    "repairable": False,
                    "telemetry": (),
                },
                config={"recursion_limit": 6, "callbacks": []},
            )
            return AgentResult(
                status="failed" if result["error"] else "pending_review",
                draft=result["draft"],
                error=result["error"],
                generation_count=result["count"],
                prompt_version=self.prompt_version,
                telemetry=result["telemetry"],
            )
