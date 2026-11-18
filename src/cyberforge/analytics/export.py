"""UTF-8 export of the authorized table projection and its manifest."""

import csv
import json
import os
import tempfile
import unicodedata
from pathlib import Path

from cyberforge.analytics.contracts import AnalyticsExportManifestV1, display_percent
from cyberforge.domain.accounts import ApplicationError

CSV_FIELDS = (
    "record_type",
    "manifest",
    "schema_version",
    "learner_id",
    "name",
    "username",
    "groups",
    "current",
    "historical",
    "activity",
    "attempts",
    "last_activity",
    "score",
    "result_status",
    "coverage",
    "email",
    "web",
    "web_not_applicable",
    "observations",
)


def safe_cell(value: str) -> str:
    # Skip leading Unicode formatting/spacing, while treating control line
    # separators as dangerous even if a spreadsheet trims them first.
    for character in value:
        if character in "=+-@\t\r\n":
            return "'" + value
        if not (character.isspace() or unicodedata.category(character).startswith("C")):
            break
    return value


def _manifest(snapshot, rows):
    query = snapshot.query
    value = AnalyticsExportManifestV1(
        captured_at=snapshot.captured_at,
        scenario_id=query.scenario_id,
        publication_id=query.publication_id,
        group_id=query.group_id,
        publications=tuple(
            p.id
            for p in snapshot.scope.publications
            if query.publication_id in (None, p.id)
        ),
        groups=tuple(
            g.id for g in snapshot.scope.groups if query.group_id in (None, g.id)
        ),
        started_from=query.started_from,
        started_to=query.started_to,
        status=query.status,
        aggregation=query.aggregation,
        search_applied=bool(query.search),
        sort=query.sort,
        direction=query.direction,
        row_count=len(rows),
        metrics=snapshot.metrics,
        criteria=snapshot.criteria,
        quality=snapshot.quality,
    )
    manifest = value.model_dump(mode="json")
    manifest["metrics"]["mean_score"] = display_percent(snapshot.metrics.mean_score)
    return manifest


def _row(value):
    row = value.model_dump(mode="json")
    row["score"] = display_percent(value.score)
    return row


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _write_csv(output, manifest, rows):
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerow({"record_type": "manifest", "manifest": safe_cell(_json(manifest))})
    for value in rows:
        cells = {}
        for field, cell in _row(value).items():
            if cell is None:
                cells[field] = ""
            elif isinstance(cell, str):
                cells[field] = safe_cell(cell)
            else:
                cells[field] = safe_cell(_json(cell))
        writer.writerow({"record_type": "learner", **cells})


def _write_json(output, manifest, rows):
    output.write('{"manifest":')
    output.write(_json(manifest))
    output.write(',"rows":[')
    for index, value in enumerate(rows):
        if index:
            output.write(",")
        output.write(_json(_row(value)))
    output.write("]}\n")


def write_export(snapshot, rows, path, kind, authorized):
    destination = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            newline="",
            mode="w",
            dir=destination.parent,
            prefix=".cyberforge-",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            writer = _write_json if kind == "json" else _write_csv
            writer(output, _manifest(snapshot, rows), rows)
        with authorized():
            os.replace(temporary, destination)
    except OSError:
        raise ApplicationError("Не вдалося зберегти файл аналітики.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
