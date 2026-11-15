"""Opt-in synthetic connectivity diagnostic; never imported by application startup."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from time import monotonic

from cyberforge.llm.config import APPROVED_MODELS, load_config
from cyberforge.llm.contracts import (
    GenerationError,
    GenerationParameters,
    GenerationRequest,
    Provider,
)
from cyberforge.llm.factory import create_gateway
from cyberforge.llm.gateway import GenerationFailure


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CyberForge: діагностика LLM")
    parser.add_argument("--live", action="store_true", help="Явно дозволити API-запит")
    parser.add_argument("--provider", choices=["gemini", "groq"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)
    if not args.live:
        parser.error(
            "Live-виклик вимкнено. Потрібен явний --live після дозволу власника."
        )
    provider = Provider(args.provider)
    if args.model not in APPROVED_MODELS[provider]:
        parser.error("Модель не входить до дозволеного переліку Phase 4.")
    started = monotonic()
    try:
        config = load_config(args.env_file).model_copy(
            update={"max_retries": 0, "fallback_to_groq": False, "backup": None}
        )
        request = GenerationRequest(
            prompt="Synthetic connectivity check. Reply only OK.",
            synthetic=True,
            provider=provider,
            model=args.model,
            parameters=GenerationParameters(
                thinking="minimal" if args.model == "gemini-3.5-flash-lite" else "low",
                max_output_tokens=config.parameters.max_output_tokens,
                timeout_seconds=20,
            ),
        )
        telemetry = create_gateway(config).generate(request).telemetry
        outcome = telemetry.status
        usage = telemetry.usage.model_dump()
        elapsed = telemetry.elapsed_seconds
        exit_code = 0
    except GenerationError as exc:
        outcome = exc.category.value
        usage = (
            exc.telemetry.usage.model_dump()
            if isinstance(exc, GenerationFailure)
            else None
        )
        elapsed = monotonic() - started
        exit_code = 1
    print(
        json.dumps(
            {
                "provider": provider.value,
                "model": args.model,
                "outcome": outcome,
                "elapsed_seconds": round(elapsed, 3),
                "usage": usage,
            }
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
