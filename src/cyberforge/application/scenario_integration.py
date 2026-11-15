"""Deterministic integration of persisted materials, without generation/network."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.orm import Session

from cyberforge.agents.contracts import EmailDraftV2
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.domain.accounts import ApplicationError, Role
from cyberforge.domain.scenarios import Scenario
from cyberforge.llm.contracts import GenerationError
from cyberforge.persistence.models import (
    EmailMaterial,
    RubricDefinitionRecord,
    ScenarioLinkRecord,
    ScenarioVersion,
    WebMaterial,
)
from cyberforge.scenario_integration.contracts import (
    ReadinessCheckV1,
    ReviewedSourcesV1,
    RubricCriterionV1,
    RubricDefinitionV1,
    ScenarioLinkV1,
)
from cyberforge.web.contracts import WebDraftV3, fingerprint

INVALID = (ValidationError, GenerationError, ValueError, TypeError, AttributeError)


def decoded(contract, payload):
    # JSON roundtrip revalidates nested mutable payloads and enums.
    return contract.model_validate_json(json.dumps(payload, allow_nan=False))


@dataclass(frozen=True)
class IntegrationState:
    scenario: Scenario
    version_id: int
    email: EmailDraftV2 | None
    web: WebDraftV3 | None
    link: ScenarioLinkV1 | None
    rubric: RubricDefinitionV1 | None
    checks: tuple[ReadinessCheckV1, ...]
    checked_sources: dict[str, int | str | None]
    snapshot: ReviewedSourcesV1 | None


def check(identifier, passed, explanation, correction):
    return ReadinessCheckV1(
        check_id=identifier,
        status="PASS" if passed else "BLOCKED",
        explanation=explanation if passed else correction,
        correction="Додаткові дії не потрібні." if passed else correction,
    )


def linkage(email, web, email_revision, web_revision):
    return fingerprint(
        dict(
            scenario_id=web.scenario_id,
            scenario_version=web.scenario_version,
            email_revision=email_revision,
            email_digest=web.email_binding.digest,
            web_revision=web_revision,
            web_digest=fingerprint(web.model_dump(mode="json")),
            context=email.artifact.context.model_dump(mode="json"),
            source_message_identifier="main",
            target_resource_id=web.page.internal_resource_id,
            allowed_action="open_internal",
        )
    )


class ScenarioIntegrationService:
    def __init__(self, webs: WebMaterialService):
        self.webs = webs
        self.emails, self.scenarios, self.accounts = (
            webs.emails,
            webs.scenarios,
            webs.accounts,
        )

    def inspect(self, token, expected: Scenario) -> IntegrationState:
        with self.accounts.transaction() as db:
            return self._load(db, token, expected)

    def _load(
        self, db: Session, token, expected: Scenario, *, write=False
    ) -> IntegrationState:
        current, version = self.emails._current(db, token, expected, write=write)
        return self._state(db, current, version)

    def _state(
        self, db: Session, current: Scenario, version: ScenarioVersion
    ) -> IntegrationState:
        email_row = db.get(EmailMaterial, version.id)
        web_row = db.get(WebMaterial, version.id)
        link_row = db.get(ScenarioLinkRecord, version.id)
        rubric_row = db.get(RubricDefinitionRecord, version.id)
        email, binding = self.webs._email(db, version, current)
        checks = [
            check(
                "email",
                email is not None,
                "Збережений Email валідний.",
                "Збережіть валідний лист для актуальних параметрів сценарію.",
            )
        ]
        web = link = rubric = None
        if web_row is not None:
            try:
                value = decoded(WebDraftV3, web_row.payload)
                self.webs._validated(value, current, email, binding)
                if (
                    web_row.scenario_revision != current.revision
                    or web_row.schema_version != value.schema_version
                    or web_row.email_revision != binding.revision
                    or web_row.email_digest != binding.digest
                    or web_row.source_digest != value.source_digest
                ):
                    raise ValueError("web_metadata")
                web = value
            except INVALID:
                pass
        checks.append(
            check(
                "web",
                web is not None,
                "Web прив’язано до точного збереженого Email.",
                "Збережіть сайт з актуальним джерелом Email; застарілий сайт "
                "потребує регенерації.",
            )
        )
        if link_row is not None and web is not None:
            try:
                value = decoded(ScenarioLinkV1, link_row.payload)
                if (
                    value.scenario_id != current.id
                    or value.scenario_version != current.version
                    or value.revision != link_row.revision
                    or value.source_email_revision != binding.revision
                    or value.source_email_digest != binding.digest
                    or value.target_web_revision != web_row.revision
                    or value.target_web_digest
                    != fingerprint(web.model_dump(mode="json"))
                    or value.target_resource_id != web.page.internal_resource_id
                    or value.target_resource_id != email.slots.internal_resource_id
                    or value.linkage_provenance
                    != linkage(email, web, email_row.revision, web_row.revision)
                ):
                    raise ValueError("link_source")
                link = value
            except INVALID:
                pass
        checks.append(
            check(
                "link",
                link is not None,
                "Main Email → поточний внутрішній Web; URL лише для показу.",
                "Налаштуйте зв’язок main Email → збережений Web цієї версії; "
                "перевірте HTTPS URL та внутрішню ціль.",
            )
        )
        if rubric_row is not None:
            try:
                value = decoded(RubricDefinitionV1, rubric_row.payload)
                if (
                    value.scenario_id != current.id
                    or value.scenario_version != current.version
                    or value.rubric_revision != rubric_row.revision
                    or value.rubric_id != f"scenario_{current.id}_v{current.version}"
                    or value.author_id != current.owner_id
                ):
                    raise ValueError("rubric_source")
                rubric = value
            except INVALID:
                pass
        checks.append(
            check(
                "rubric",
                rubric is not None,
                "Рубрика валідна; Web-критерії застосовні лише після відвідування Web.",
                "Збережіть рубрику з додатними вагами та хоча б одним "
                "критерієм безпечного шляху без Web.",
            )
        )
        if link and web and link.display_url != web.page.display_url:
            checks.append(
                ReadinessCheckV1(
                    check_id="display_url_mismatch",
                    status="WARNING",
                    explanation="Видима адреса Email відрізняється від адреси "
                    "Web. Підтвердьте, що це навмисна навчальна "
                    "ознака.",
                    correction="Перевірте обидві адреси; виправте зв’язок або "
                    "явно підтвердьте відмінність.",
                )
            )
        checks.append(
            check(
                "security",
                email is not None and web is not None and link is not None,
                "Closed schemas/renderer підтримуються; дозволено лише "
                "внутрішнє призначення.",
                "Виправте матеріали та зв’язок; зовнішню навігацію й довільний "
                "код заборонено.",
            )
        )
        checks.append(
            ReadinessCheckV1(
                check_id="semantic_review",
                status="WARNING",
                explanation="Викладач має перевірити зміст, організацію, "
                "відправника, навчальну мету та ознаки листа. "
                "Структурна перевірка не доводить педагогічну "
                "узгодженість.",
                correction="Перегляньте точні Email/Web, зв’язок та рубрику й "
                "підтвердьте змістову узгодженість.",
            )
        )
        checked = dict(
            scenario_revision=current.revision,
            archive_revision=current.archive_revision,
        )
        for name, row in (
            ("email", email_row),
            ("web", web_row),
            ("link", link_row),
            ("rubric", rubric_row),
        ):
            checked[f"{name}_revision"] = row.revision if row else None
            checked[f"{name}_digest"] = fingerprint(row.payload) if row else None
        snapshot = None
        if all((email, web, link, rubric)):
            snapshot = ReviewedSourcesV1(
                scenario_id=current.id,
                scenario_version=current.version,
                scenario_revision=current.revision,
                scenario_digest=fingerprint(current.parameters.model_dump(mode="json")),
                archive_revision=current.archive_revision,
                email_revision=email_row.revision,
                email_digest=binding.digest,
                web_revision=web_row.revision,
                web_digest=fingerprint(web.model_dump(mode="json")),
                link_revision=link_row.revision,
                link_digest=fingerprint(link.model_dump(mode="json")),
                rubric_revision=rubric_row.revision,
                rubric_digest=rubric.content_digest,
            )
        return IntegrationState(
            current,
            version.id,
            email,
            web,
            link,
            rubric,
            tuple(checks),
            checked,
            snapshot,
        )

    def save_link(
        self,
        token,
        expected: Scenario,
        *,
        link_label: str,
        display_url: str,
        target_resource_id: str,
        expected_revision: int,
        expected_email_revision: int,
        expected_web_revision: int,
    ) -> ScenarioLinkV1:
        with self.accounts.transaction(write=True) as db:
            state = self._load(db, token, expected, write=True)
            row = db.get(ScenarioLinkRecord, state.version_id)
            email_row = db.get(EmailMaterial, state.version_id)
            web_row = db.get(WebMaterial, state.version_id)
            if state.email is None or state.web is None:
                raise ApplicationError("Спочатку збережіть актуальні Email і Web.")
            if ((row.revision if row else 0), email_row.revision, web_row.revision) != (
                expected_revision,
                expected_email_revision,
                expected_web_revision,
            ):
                raise ApplicationError(
                    "Джерела або зв’язок уже змінено. Відкрийте редактор повторно."
                )
            if target_resource_id != state.web.page.internal_resource_id:
                raise ApplicationError(
                    "Ціль зв’язку не відповідає поточному збереженому Web."
                )
            try:
                value = ScenarioLinkV1(
                    scenario_id=expected.id,
                    scenario_version=expected.version,
                    revision=expected_revision + 1,
                    source_email_revision=email_row.revision,
                    source_email_digest=state.web.email_binding.digest,
                    target_web_revision=web_row.revision,
                    target_web_digest=fingerprint(state.web.model_dump(mode="json")),
                    link_label=link_label,
                    display_url=display_url,
                    target_resource_id=target_resource_id,
                    linkage_provenance=linkage(
                        state.email, state.web, email_row.revision, web_row.revision
                    ),
                )
            except INVALID:
                raise ApplicationError(
                    "Перевірте назву посилання (1–200 символів звичайного "
                    "тексту) та безпечну HTTPS адресу без credentials або коду."
                ) from None
            if row is None:
                row = ScenarioLinkRecord(version_id=state.version_id)
                db.add(row)
            row.revision, row.payload = value.revision, value.model_dump(mode="json")
            db.flush()
        return value

    def save_rubric(
        self,
        token,
        expected: Scenario,
        criteria: tuple[RubricCriterionV1, ...],
        *,
        expected_revision: int,
    ) -> RubricDefinitionV1:
        with self.accounts.transaction(write=True) as db:
            current, version = self.emails._current(db, token, expected, write=True)
            actor = self.accounts.require(
                db, token, Role.INSTRUCTOR, Role.ADMINISTRATOR
            )
            row = db.get(RubricDefinitionRecord, version.id)
            if (row.revision if row else 0) != expected_revision:
                raise ApplicationError(
                    "Рубрику вже змінено. Відкрийте редактор повторно."
                )
            try:
                content = dict(
                    rubric_schema_version="rubric-definition-v1",
                    registry_version="criterion-registry-v1",
                    semantics_version="rubric-declarations-v1",
                    rubric_id=f"scenario_{current.id}_v{current.version}",
                    rubric_revision=expected_revision + 1,
                    scenario_id=current.id,
                    scenario_version=current.version,
                    criteria=[
                        c.model_dump(mode="json", warnings=False) for c in criteria
                    ],
                    author_id=actor.id,
                    saved_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                )
                value = decoded(
                    RubricDefinitionV1,
                    content | {"content_digest": fingerprint(content)},
                )
            except INVALID:
                raise ApplicationError(
                    "Рубрика невалідна: оберіть унікальні критерії з каталогу, "
                    "додатні ваги та дозволену застосовність. Додайте non-Web "
                    "критерій для безпечної відмови."
                ) from None
            if row is None:
                row = RubricDefinitionRecord(version_id=version.id)
                db.add(row)
            row.revision, row.payload = (
                value.rubric_revision,
                value.model_dump(mode="json"),
            )
            db.flush()
        return value
