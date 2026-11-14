"""Authorized Email generation and explicit transactional persistence.

Provenance proves consistency, not permission. Identity/parameters always come
from ScenarioService and the shared database, never from model metadata.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from cyberforge.agents.contracts import (
    EmailDraftV2,
    EmailInputV1,
    MessageV1,
    source_provenance,
)
from cyberforge.agents.specialized import EmailScenarioAgent
from cyberforge.application.scenarios import ScenarioService
from cyberforge.domain.accounts import ApplicationError, Role
from cyberforge.domain.scenarios import Scenario, ScenarioStatus
from cyberforge.llm.contracts import (
    ErrorCategory,
    GenerationError,
    Provider,
    ScenarioContextV1,
)
from cyberforge.llm.gateway import LLMGateway
from cyberforge.persistence.models import EmailMaterial, ScenarioVersion


class MaterialState(StrEnum):
    EMPTY = "Не створено"
    GENERATING = "Генерується"
    UNSAVED = "Згенеровано, але не збережено"
    SAVED = "Збережено"
    REVIEW = "Потребує перевірки"


@dataclass(frozen=True)
class EmailWorkspace:
    scenario: Scenario
    revision: int = 0
    state: MaterialState = MaterialState.EMPTY
    draft: EmailDraftV2 | None = field(default=None, repr=False)


def synthetic_context(scenario: Scenario) -> ScenarioContextV1:
    """Stable v1 convention, independent of refinement and parameter revisions."""
    return ScenarioContextV1(
        schema_version="scenario-context-v1",
        organization=f"Навчальна організація {scenario.id}",
        sender_name="Навчальна служба",
        premise="Синтетичне навчальне повідомлення",
        internal_resource_id=f"scenario_{scenario.id}_v{scenario.version}",
    )


def email_source(
    scenario: Scenario,
    *,
    previous: EmailDraftV2 | None = None,
    refinement: str | None = None,
    refinement_scope: Literal["all", "main_body"] = "all",
) -> EmailInputV1:
    context = synthetic_context(scenario)
    if previous is not None and previous.instructor_sender_name is not None:
        context = ScenarioContextV1.model_validate(
            context.model_dump() | {"sender_name": previous.instructor_sender_name}
        )
    return EmailInputV1(
        synthetic=True,
        scenario_id=scenario.id,
        scenario_version=scenario.version,
        parameters=scenario.parameters,
        context=context,
        previous=previous,
        refinement=refinement or None,
        refinement_scope=refinement_scope,
    )


class EmailMaterialService:
    def __init__(
        self, scenarios: ScenarioService, gateway: LLMGateway, *, demo: bool = False
    ) -> None:
        self.scenarios = scenarios
        self.accounts = scenarios.accounts
        self.gateway = gateway
        self.demo = demo

    @property
    def available(self) -> bool:
        return self.demo or self.gateway.config.provider != Provider.MOCK

    @property
    def provider_label(self) -> str:
        if self.demo:
            return (
                "Офлайн-демо · MockLLMProvider · синтетичний шаблон, без AI та мережі"
            )
        if not self.available:
            return "Офлайн: генерацію не налаштовано. Для демонстрації: --email-demo."
        config = self.gateway.config
        return f"Хмарна генерація · {config.provider.value} / {config.model}"

    @staticmethod
    def _validated(draft: EmailDraftV2, scenario: Scenario) -> EmailDraftV2:
        # JSON round trip also validates mutable nested slots and strict enums.
        value = EmailDraftV2.model_validate_json(draft.model_dump_json())
        source = email_source(scenario, previous=value)
        if (
            value.parameters != source.parameters
            or value.artifact.context != source.context
            or value.scenario_id != scenario.id
            or value.scenario_version != scenario.version
            or value.provenance != source_provenance(source)
        ):
            raise ValueError("email_binding")
        return value

    def _current(
        self, db: Session, token: str | None, expected: Scenario, *, write: bool
    ) -> tuple[Scenario, ScenarioVersion]:
        actor = self.accounts.require(db, token, Role.INSTRUCTOR, Role.ADMINISTRATOR)
        record = self.scenarios._record(db, actor, expected.id, write=write)
        row = (
            self.scenarios._latest(db, record.id)
            if write
            else db.scalar(
                select(ScenarioVersion).where(
                    ScenarioVersion.scenario_id == record.id,
                    ScenarioVersion.number == expected.version,
                )
            )
        )
        if row is None:
            raise ApplicationError("Версію сценарію не знайдено.")
        current = self.scenarios._value(record, row)
        if (current.version, current.revision, current.archive_revision) != (
            expected.version,
            expected.revision,
            expected.archive_revision,
        ):
            raise ApplicationError(
                "Сценарій уже змінено. Чернетку залишено; "
                "повторно відкрийте актуальну версію."
            )
        if write and (current.archived or current.status != ScenarioStatus.DRAFT):
            raise ApplicationError("Матеріал цієї версії доступний лише для перегляду.")
        return current, row

    def load(self, token: str | None, expected: Scenario) -> EmailWorkspace:
        with self.accounts.transaction() as db:
            current, version = self._current(db, token, expected, write=False)
            revision = self._revision(db, version.id)
            if revision == 0:
                return EmailWorkspace(current)
            try:
                row = db.get(EmailMaterial, version.id)
                draft = EmailDraftV2.model_validate_json(json.dumps(row.payload))
                draft = self._validated(draft, current)
                if (
                    row.scenario_revision != current.revision
                    or row.source_digest != draft.provenance.source_digest
                    or row.context != draft.artifact.context.model_dump(mode="json")
                    or row.schema_version != draft.schema_version
                ):
                    raise ValueError("stale_material")
            except (
                ValidationError,
                GenerationError,
                ValueError,
                TypeError,
                AttributeError,
            ):
                return EmailWorkspace(current, revision, MaterialState.REVIEW)
            return EmailWorkspace(current, row.revision, MaterialState.SAVED, draft)

    @staticmethod
    def _revision(db: Session, version_id: int) -> int:
        return (
            db.scalar(
                select(EmailMaterial.revision).where(
                    EmailMaterial.version_id == version_id
                )
            )
            or 0
        )

    def check(
        self, token: str | None, workspace: EmailWorkspace, *, write: bool = True
    ) -> Scenario:
        with self.accounts.transaction() as db:
            current, version = self._current(db, token, workspace.scenario, write=write)
            if self._revision(db, version.id) != workspace.revision:
                raise ApplicationError(
                    "Лист уже змінено в іншому редакторі. "
                    "Чернетку залишено без перезапису."
                )
            return current

    def generate(
        self,
        token: str | None,
        workspace: EmailWorkspace,
        *,
        previous: EmailDraftV2 | None = None,
        refinement: str | None = None,
        refinement_scope: Literal["all", "main_body"] = "all",
    ) -> EmailDraftV2:
        current = self.check(token, workspace)
        if not self.available:
            raise ApplicationError(self.provider_label)
        try:
            if previous is not None:
                previous = self._validated(previous, current)
            source = email_source(
                current,
                previous=previous,
                refinement=refinement,
                refinement_scope=refinement_scope,
            )
            # Demo is an explicitly selected offline mechanism, never a cloud fallback.
            if self.demo:
                from cyberforge.application.email_demo import demo_gateway

                gateway = demo_gateway(source)
            else:
                gateway = self.gateway
            result = EmailScenarioAgent(gateway).run(source)
            if result.draft is None or result.status != "pending_review":
                raise GenerationError(result.error or ErrorCategory.VALIDATION)
            payload = result.draft.model_dump(mode="json")
            payload["instructor_sender_name"] = (
                previous.instructor_sender_name if previous else None
            )
            draft = self._validated(
                EmailDraftV2.model_validate_json(json.dumps(payload)), current
            )
        except (ValidationError, ValueError, TypeError):
            raise ApplicationError(
                "Дані листа або інструкція не пройшли перевірку. "
                "Використовуйте лише синтетичні дані."
            ) from None
        self.check(token, workspace)
        return draft

    def edit(
        self,
        token: str | None,
        workspace: EmailWorkspace,
        draft: EmailDraftV2,
        *,
        index: int,
        message: MessageV1 | None = None,
        action: Literal["replace", "add", "remove"] = "replace",
    ) -> EmailDraftV2:
        """Apply validated local changes only; never writes material persistence."""
        current = self.check(token, workspace)
        try:
            value = self._validated(draft, current)
            data = value.model_dump(mode="json")
            slots = data["slots"]
            count = len(slots["background"])
            if action == "remove":
                if not 1 <= index <= count or count <= 1:
                    raise ValueError("background_bounds")
                del slots["background"][index - 1]
            else:
                if message is None:
                    raise ValueError("message_required")
                entry = MessageV1.model_validate_json(message.model_dump_json())
                if (
                    len(entry.sender_name) > 200
                    or len(entry.sender_address) > 254
                    or len(entry.subject) > 300
                ):
                    raise ValueError("editor_bounds")
                if action == "add":
                    if count >= 8:
                        raise ValueError("background_bounds")
                    slots["background"].append(entry.model_dump(mode="json"))
                elif action == "replace" and 0 <= index <= count:
                    if index == 0:
                        slots["main"] = entry.model_dump(mode="json")
                        data["artifact"]["subject"] = entry.subject
                        data["artifact"]["body_text"] = entry.body_text
                        data["artifact"]["context"]["sender_name"] = entry.sender_name
                        data["instructor_sender_name"] = entry.sender_name
                    else:
                        slots["background"][index - 1] = entry.model_dump(mode="json")
                else:
                    raise ValueError("message_index")
            source = EmailInputV1(
                synthetic=True,
                scenario_id=current.id,
                scenario_version=current.version,
                parameters=current.parameters,
                context=data["artifact"]["context"],
            )
            data["provenance"] = source_provenance(source).model_dump(mode="json")
            slots["context_token"] = EmailScenarioAgent.context_token(source)
            result = self._validated(
                EmailDraftV2.model_validate_json(json.dumps(data)), current
            )
        except (
            ValidationError,
            GenerationError,
            ValueError,
            TypeError,
            AttributeError,
        ):
            raise ApplicationError(
                "Зміни не пройшли перевірку. Використовуйте "
                "синтетичну адресу .invalid, "
                "звичайний текст без коду та зовнішніх "
                "ресурсів; перевірте довжину полів."
            ) from None
        self.check(token, workspace)
        return result

    def save(
        self, token: str | None, workspace: EmailWorkspace, draft: EmailDraftV2
    ) -> EmailWorkspace:
        with self.accounts.transaction(write=True) as db:
            current, version = self._current(db, token, workspace.scenario, write=True)
            revision = self._revision(db, version.id)
            if revision != workspace.revision:
                raise ApplicationError(
                    "Лист уже змінено. Незбережену чернетку залишено у вікні."
                )
            try:
                value = self._validated(draft, current)
            except (
                ValidationError,
                GenerationError,
                ValueError,
                TypeError,
                AttributeError,
            ):
                raise ApplicationError(
                    "Чернетка не відповідає цій версії та параметрам сценарію."
                ) from None
            now = datetime.now(UTC).replace(tzinfo=None)
            values = dict(
                revision=revision + 1,
                scenario_revision=current.revision,
                source_digest=value.provenance.source_digest,
                schema_version=value.schema_version,
                context=value.artifact.context.model_dump(mode="json"),
                payload=value.model_dump(mode="json"),
                updated_at=now,
            )
            if revision == 0:
                actor = self.accounts.require(
                    db, token, Role.INSTRUCTOR, Role.ADMINISTRATOR
                )
                db.add(
                    EmailMaterial(
                        version_id=version.id,
                        created_by=actor.id,
                        created_at=now,
                        **values,
                    )
                )
            else:
                result = db.execute(
                    update(EmailMaterial)
                    .where(
                        EmailMaterial.version_id == version.id,
                        EmailMaterial.revision == revision,
                    )
                    .values(**values)
                )
                if result.rowcount != 1:
                    raise ApplicationError("Лист уже змінено іншим редактором.")
            db.flush()
            saved = EmailWorkspace(current, revision + 1, MaterialState.SAVED, value)
        # Return only after the context manager has committed successfully.
        return saved
