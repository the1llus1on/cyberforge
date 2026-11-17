"""Explicit new-contract canonical bytes; legacy fingerprints stay unchanged."""

import json
import math
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from pydantic import BaseModel, ValidationInfo

# Binary64 shortest round-trip weights (0 < w <= 10000) need at most 324
# fractional places, including 5e-324. Seven exact contributions need at most
# five integral + 324 fractional digits. These bounds never round a value.
MAX_DECIMAL_PLACES = 324
MAX_DECIMAL_DIGITS = 329
MAX_DECIMAL_TEXT = MAX_DECIMAL_DIGITS + 16  # sign/point/exponent syntax allowance
MAX_TOTAL = 70000


def bounded_decimal(value: Decimal) -> Decimal:
    """Guard compact hostile exponents before formatting/scaling/hashing."""
    if not value.is_finite():
        raise ValueError("nonfinite_decimal")
    _, digits, exponent = value.as_tuple()
    if (
        not -MAX_DECIMAL_PLACES <= exponent <= 4
        or len(digits) > MAX_DECIMAL_DIGITS
        or value.copy_abs() > MAX_TOTAL
    ):
        raise ValueError("decimal_resource_bound")
    return value


def bounded_decimal_input(value, info: ValidationInfo):
    """Preserve Pydantic strict Python/JSON parsing while guarding raw strings."""
    if isinstance(value, str):
        if len(value) > MAX_DECIMAL_TEXT:
            raise ValueError("decimal_resource_bound")
        from decimal import InvalidOperation

        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("invalid_decimal") from exc
        bounded_decimal(parsed)
        if info.mode == "json":
            return parsed
    elif isinstance(value, Decimal):
        bounded_decimal(value)
    return value


def decimal_text(value: Decimal) -> str:
    bounded_decimal(value)
    if value.is_zero():
        return "0"
    return (
        format(value, "f").rstrip("0").rstrip(".")
        if value.as_tuple().exponent < 0
        else format(value, "f")
    )


def percentage_text(value: Decimal) -> str:
    text = decimal_text(value)
    whole, _, fraction = text.partition(".")
    if len(fraction) > 2:
        raise ValueError("percentage_precision")
    return whole + "." + fraction.ljust(2, "0")


def value_tree(value, *, field: str = ""):
    if isinstance(value, BaseModel):
        return {
            name: value_tree(getattr(value, name), field=name)
            for name in type(value).model_fields
        }
    if isinstance(value, Decimal):
        return (
            percentage_text(value) if field == "score_percent" else decimal_text(value)
        )
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive_timestamp")
        return (
            value.astimezone(UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (tuple, list)):
        return [value_tree(v) for v in value]
    if isinstance(value, dict):
        return {k: value_tree(v, field=k) for k, v in value.items()}
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite_float")
    return value


def canonical_bytes(value) -> bytes:
    return json.dumps(
        value_tree(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value, *, exclude: str | None = None) -> str:
    tree = value_tree(value)
    if exclude is not None:
        tree = {k: v for k, v in tree.items() if k != exclude}
    return sha256(canonical_bytes(tree)).hexdigest()


def _unique(pairs):
    result = {}
    for key, val in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = val
    return result


def parse_contract[M: BaseModel](model: type[M], data: str | bytes) -> M:
    """Trust boundary: reject duplicates and noncanonical scalar/byte forms."""
    raw = data.encode() if isinstance(data, str) else data
    json.loads(
        raw,
        object_pairs_hook=_unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")),
    )
    result = model.model_validate_json(raw)
    if canonical_bytes(result) != raw:
        raise ValueError("noncanonical_json")
    return result


def historical_weight(value: float) -> Decimal:
    if type(value) is not float or not math.isfinite(value) or not 0 < value <= 10000:
        raise ValueError("historical_weight")
    return Decimal(str(value))


def reference_arithmetic(items: tuple[tuple[Decimal, int], ...]):
    """Contract-verification oracle only: exact sums and half-even hundredths."""
    if len(items) > 7:
        raise ValueError("arithmetic_criterion_count")
    for weight, score in items:
        bounded_decimal(weight)
        if (
            not weight.is_finite()
            or not 0 < weight <= 10000
            or type(score) is not int
            or score not in (0, 1)
        ):
            raise ValueError("arithmetic_input")
    scale = max((max(0, -w.as_tuple().exponent) for w, _ in items), default=0)
    integers = []
    for weight, score in items:
        _, digits, exponent = weight.as_tuple()
        coefficient = int("".join(map(str, digits)))
        integers.append((coefficient * 10 ** (exponent + scale), score))
    numerator = sum(w * score for w, score in integers)
    denominator = sum(w for w, _ in integers)

    def exact(n):
        # Decimal construction from a tuple does not use the ambient context.
        return Decimal((0, tuple(map(int, str(n))), -scale))

    if denominator == 0:
        return Decimal(0), Decimal(0), None
    q, r = divmod(10000 * numerator, denominator)
    q += int(2 * r > denominator or (2 * r == denominator and q % 2 == 1))
    return (
        exact(numerator),
        exact(denominator),
        Decimal((0, tuple(map(int, str(q))), -2)),
    )
