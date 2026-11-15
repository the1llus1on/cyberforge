"""Owner-initiated two-request Groq acceptance; no database or content logging."""

import argparse
import json
import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import SecretStr

from cyberforge.agents.contracts import EmailInputV1
from cyberforge.agents.specialized import EmailScenarioAgent
from cyberforge.domain.nist_cues import NistCueId
from cyberforge.domain.scenarios import ScenarioParameters
from cyberforge.llm.config import GatewayConfig
from cyberforge.llm.contracts import GenerationParameters, Provider, ScenarioContextV1
from cyberforge.llm.factory import create_gateway


def acceptance_source() -> EmailInputV1:
    return EmailInputV1(
        synthetic=True,
        scenario_id=1,
        scenario_version=1,
        parameters=ScenarioParameters(
            topic="Перевірка повідомлення про оновлення навчального порталу",
            difficulty="intermediate",
            audience="Синтетична група слухачів",
            description=(
                "Навчальна організація пропонує перевірити підозріле повідомлення."
            ),
            learning_objective=(
                "Перевіряти адресу відправника та внутрішнє призначення посилання."
            ),
            tactics=("Терміновість",),
            nist_cues=(NistCueId.SENDER_IDENTITY, NistCueId.URGENCY),
        ),
        context=ScenarioContextV1(
            schema_version="scenario-context-v1",
            organization="Навчальна організація",
            sender_name="Навчальна служба",
            premise="Оновлення навчального порталу",
            internal_resource_id="acceptance_1_v1",
        ),
    )


def run_check(gateway, emit=print) -> bool:
    """At most two agent calls; no retries/corrections/fallback permitted."""
    if (
        gateway.config.max_retries
        or gateway.config.backup is not None
        or gateway.config.fallback_to_groq
    ):
        raise ValueError("Acceptance requires zero retries and no fallback")
    source = acceptance_source()
    previous = None
    for stage in ("initial", "refinement"):
        if previous is not None:
            source = EmailInputV1(
                **source.model_dump(
                    exclude={"previous", "refinement", "refinement_scope"}
                ),
                previous=previous,
                refinement=(
                    "Скороти лише текст основного листа. Збережи "
                    "тему і всі фонові листи."
                ),
                refinement_scope="main_body",
            )
        result = EmailScenarioAgent(gateway, max_corrections=0).run(source)
        protected = None
        if previous is not None and result.draft is not None:
            before, after = previous.slots.model_dump(), result.draft.slots.model_dump()
            before.pop("context_token")
            after.pop("context_token")
            before["main"].pop("body_text")
            after["main"].pop("body_text")
            protected = (
                before == after and previous.provenance == result.draft.provenance
            )
        emit(
            json.dumps(
                {
                    "stage": stage,
                    "status": result.status,
                    "error": result.error,
                    "contract_valid": result.draft is not None,
                    "protected_fields_preserved": protected,
                    "telemetry": [
                        t.model_dump(
                            mode="json",
                            include={
                                "requested_provider",
                                "requested_model",
                                "provider",
                                "effective_model",
                                "actual_model",
                                "error",
                                "status",
                                "local_validation",
                                "schema_version",
                                "elapsed_seconds",
                                "usage",
                                "provider_diagnostics",
                            },
                        )
                        for t in result.telemetry
                    ],
                },
                ensure_ascii=False,
            )
        )
        if result.draft is None or protected is False:
            return False
        previous = result.draft
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Opt in to at most two paid Groq requests"
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=None,
        help="Optional explicit provider output limit; omitted by default",
    )
    args = parser.parse_args(argv)
    if args.max_output_tokens is not None and args.max_output_tokens < 1:
        parser.error("--max-output-tokens must be positive")
    if not args.live:
        parser.error("Explicit --live required; no requests were made")
    values = dotenv_values(Path(".env"), interpolate=False)
    key = os.environ.get("GROQ_API_KEY", values.get("GROQ_API_KEY"))
    if not key:
        print('{"status":"error","error":"missing_credentials"}')
        return 1
    config = GatewayConfig(
        provider=Provider.GROQ,
        model="openai/gpt-oss-120b",
        groq_api_key=SecretStr(key),
        max_retries=0,
        backup=None,
        fallback_to_groq=False,
        parameters=GenerationParameters(
            thinking="low", timeout_seconds=60, max_output_tokens=args.max_output_tokens
        ),
    )
    try:
        return 0 if run_check(create_gateway(config)) else 1
    except Exception:
        print('{"status":"error","error":"invalid_request"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
