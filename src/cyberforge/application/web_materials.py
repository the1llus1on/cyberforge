"""Authorized generation/editing and explicit transactional Web persistence."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select, update

from cyberforge.agents.contracts import EmailDraftV2
from cyberforge.agents.web import WebScenarioAgentV2
from cyberforge.application.email_materials import EmailMaterialService, MaterialState
from cyberforge.domain.accounts import ApplicationError, Role
from cyberforge.domain.scenarios import Scenario
from cyberforge.llm.contracts import ErrorCategory, GenerationError, Provider
from cyberforge.persistence.models import EmailMaterial, WebMaterial
from cyberforge.web.contracts import (
    EmailBindingV2,
    Preset,
    Scope,
    Theme,
    WebDraftV3,
    WebInputV2,
    WebPageV2,
    email_digest,
    source_digest,
)

STALE_MESSAGE = (
    "Збережений лист або параметри змінилися. Сайт збережено для перегляду, "
    "але він потребує нової генерації. Попередні матеріали не перезаписано."
)


@dataclass(frozen=True)
class WebWorkspace:
    scenario: Scenario
    revision: int = 0
    state: MaterialState = MaterialState.EMPTY
    draft: WebDraftV3 | None = field(default=None, repr=False)
    email: EmailDraftV2 | None = field(default=None, repr=False)
    email_binding: EmailBindingV2 | None = None


class WebMaterialService:
    def __init__(self, emails: EmailMaterialService, *, demo: bool = False):
        self.emails = emails
        self.scenarios, self.accounts, self.gateway = (
            emails.scenarios,
            emails.accounts,
            emails.gateway,
        )
        self.demo = demo

    @property
    def available(self) -> bool:
        return self.demo or self.gateway.config.provider != Provider.MOCK

    @property
    def provider_label(self) -> str:
        if self.demo:
            return "Офлайн-демо · синтетична композиція, без AI та мережі"
        if not self.available:
            return "Офлайн: AI не налаштовано. Демо: --web-demo."
        return f"{self.gateway.config.provider.value} / {self.gateway.config.model}"

    def _email(self, db, version, scenario):
        row = db.get(EmailMaterial, version.id)
        if row is None:
            return None, None
        try:
            email = self.emails._validated(
                EmailDraftV2.model_validate_json(json.dumps(row.payload)), scenario
            )
            if (
                row.scenario_revision != scenario.revision
                or row.schema_version != email.schema_version
                or row.source_digest != email.provenance.source_digest
                or row.context != email.artifact.context.model_dump(mode="json")
            ):
                raise ValueError("stale_email")
            return email, EmailBindingV2(
                revision=row.revision, digest=email_digest(email)
            )
        except (
            ValidationError,
            GenerationError,
            ValueError,
            TypeError,
            AttributeError,
        ):
            return None, None

    @staticmethod
    def _revision(db, version_id):
        return (
            db.scalar(
                select(WebMaterial.revision).where(WebMaterial.version_id == version_id)
            )
            or 0
        )

    @staticmethod
    def _validated(draft, scenario, email, binding) -> WebDraftV3:
        value = WebDraftV3.model_validate_json(draft.model_dump_json(warnings=False))
        if (
            email is None
            or binding is None
            or value.scenario_id != scenario.id
            or value.scenario_version != scenario.version
            or value.parameters != scenario.parameters
            or value.context != email.artifact.context
            or value.email_binding != binding
            or value.source_digest
            != source_digest(
                scenario.id,
                scenario.version,
                scenario.parameters,
                email.artifact.context,
                binding,
            )
        ):
            raise ValueError("web_source")
        return value

    def load(self, token, expected: Scenario) -> WebWorkspace:
        with self.accounts.transaction() as db:
            current, version = self.emails._current(db, token, expected, write=False)
            email, binding = self._email(db, version, current)
            row = db.get(WebMaterial, version.id)
            if row is None:
                return WebWorkspace(current, email=email, email_binding=binding)
            value = None
            try:
                value = WebDraftV3.model_validate_json(json.dumps(row.payload))
                # Never expose even stale content from a different resource/version.
                if (
                    value.scenario_id != current.id
                    or value.scenario_version != current.version
                ):
                    value = None
                    raise ValueError("identity")
                self._validated(value, current, email, binding)
                if (
                    row.scenario_revision != current.revision
                    or row.email_revision != binding.revision
                    or row.email_digest != binding.digest
                    or row.source_digest != value.source_digest
                    or row.schema_version != value.schema_version
                ):
                    raise ValueError("stale_web")
            except (
                ValidationError,
                GenerationError,
                ValueError,
                TypeError,
                AttributeError,
            ):
                return WebWorkspace(
                    current, row.revision, MaterialState.REVIEW, value, email, binding
                )
            return WebWorkspace(
                current, row.revision, MaterialState.SAVED, value, email, binding
            )

    def _check(self, db, token, workspace, *, write):
        current, version = self.emails._current(
            db, token, workspace.scenario, write=write
        )
        if self._revision(db, version.id) != workspace.revision:
            raise ApplicationError(
                "Сайт змінено в іншому редакторі. Чернетку залишено."
            )
        email, binding = self._email(db, version, current)
        if email is None or binding is None:
            raise ApplicationError(
                "Спочатку збережіть валідний лист цієї версії сценарію."
            )
        if workspace.email_binding != binding:
            raise ApplicationError(STALE_MESSAGE)
        return current, version, email, binding

    def check(self, token, workspace, *, write=True):
        with self.accounts.transaction() as db:
            current, _, _, _ = self._check(db, token, workspace, write=write)
            return current

    def generate(
        self,
        token,
        workspace,
        *,
        previous=None,
        refinement=None,
        refinement_scope: Scope = "page",
        selected_component=None,
        preset: Preset = "auto",
        theme: Theme = "academic",
    ) -> WebDraftV3:
        with self.accounts.transaction() as db:
            current, _, email, binding = self._check(db, token, workspace, write=True)
        if not self.available:
            raise ApplicationError(self.provider_label)
        try:
            if previous is not None:
                previous = self._validated(previous, current, email, binding)
            source = WebInputV2(
                synthetic=True,
                scenario_id=current.id,
                scenario_version=current.version,
                parameters=current.parameters,
                context=email.artifact.context,
                email=email,
                email_binding=binding,
                previous=previous,
                refinement=refinement or None,
                refinement_scope=refinement_scope,
                selected_component=selected_component,
                preset=preset,
                theme=theme,
            )
            if self.demo:
                from cyberforge.application.web_demo import demo_gateway

                gateway = demo_gateway(source)
            else:
                gateway = self.gateway
            result = WebScenarioAgentV2(gateway).run(source)
            if result.draft is None or result.status != "pending_review":
                raise GenerationError(result.error or ErrorCategory.VALIDATION)
            value = self._validated(result.draft, current, email, binding)
        except (ValidationError, ValueError, TypeError):
            raise ApplicationError(
                "Дані сайту або межі змін не пройшли перевірку. "
                "Використовуйте синтетичний текст і дозволені компоненти."
            ) from None
        self.check(token, workspace)
        return value

    def edit(self, token, workspace, draft, page: WebPageV2) -> WebDraftV3:
        with self.accounts.transaction() as db:
            current, _, email, binding = self._check(db, token, workspace, write=True)
            try:
                value = self._validated(draft, current, email, binding)
                candidate = WebDraftV3.model_validate_json(
                    json.dumps(
                        value.model_dump(mode="json")
                        | {"page": page.model_dump(mode="json")}
                    )
                )
                return self._validated(candidate, current, email, binding)
            except (ValidationError, ValueError, TypeError, AttributeError):
                raise ApplicationError(
                    "Неприпустима композиція або властивості сайту."
                ) from None

    def save(self, token, workspace, draft) -> WebWorkspace:
        with self.accounts.transaction(write=True) as db:
            current, version, email, binding = self._check(
                db, token, workspace, write=True
            )
            try:
                value = self._validated(draft, current, email, binding)
            except (ValidationError, ValueError, TypeError, AttributeError):
                raise ApplicationError(STALE_MESSAGE) from None
            now = datetime.now(UTC).replace(tzinfo=None)
            values = dict(
                revision=workspace.revision + 1,
                scenario_revision=current.revision,
                email_revision=binding.revision,
                email_digest=binding.digest,
                source_digest=value.source_digest,
                schema_version=value.schema_version,
                payload=value.model_dump(mode="json"),
                updated_at=now,
            )
            if workspace.revision == 0:
                actor = self.accounts.require(
                    db, token, Role.INSTRUCTOR, Role.ADMINISTRATOR
                )
                db.add(
                    WebMaterial(
                        version_id=version.id,
                        created_by=actor.id,
                        created_at=now,
                        **values,
                    )
                )
            else:
                result = db.execute(
                    update(WebMaterial)
                    .where(
                        WebMaterial.version_id == version.id,
                        WebMaterial.revision == workspace.revision,
                    )
                    .values(**values)
                )
                if result.rowcount != 1:
                    raise ApplicationError("Сайт уже змінено в іншому редакторі.")
            db.flush()
            saved = WebWorkspace(
                current, values["revision"], MaterialState.SAVED, value, email, binding
            )
        return saved
