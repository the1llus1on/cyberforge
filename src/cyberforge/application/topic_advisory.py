"""Bind an Instructor's cloud request to fresh Analytics and machine policy."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from threading import Event, RLock
from time import monotonic
from uuid import uuid4

from cyberforge.analytics.advisory_authorization import (
    AdvisoryPolicyEvidenceV1,
    AdvisoryPreviewBinding,
    ProviderPrivacyProfileV1,
)
from cyberforge.analytics.contracts import AnalyticsQueryV1
from cyberforge.analytics.topic_advisory import offline_recommendations
from cyberforge.application.analytics import ScenarioAnalyticsService
from cyberforge.application.provider_settings import ProviderSettings
from cyberforge.domain.accounts import AccessDenied, ApplicationError
from cyberforge.llm.contracts import GenerationError
from cyberforge.llm.gateway import LLMGateway
from cyberforge.llm.topic_transport import (
    MODE,
    TopicProviderRequest,
    make_topic_request,
)


@dataclass(frozen=True, slots=True, repr=False)
class AdvisoryPreview:
    identifier: str | None
    scope_digest: str
    recommendations: tuple[str, ...]
    request: TopicProviderRequest | None


@dataclass(frozen=True, slots=True, repr=False)
class AdvisoryResult:
    cloud: bool
    recommendations: tuple[str, ...]


@dataclass(frozen=True, slots=True, repr=False)
class _Ticket:
    identifier: str
    query: AnalyticsQueryV1
    binding: AdvisoryPreviewBinding
    request: TopicProviderRequest
    expires: float
    cancelled: Event


class TopicAdvisory:
    def __init__(
        self,
        analytics: ScenarioAnalyticsService,
        settings: ProviderSettings,
        policy: Callable[[str, str], AdvisoryPolicyEvidenceV1 | None],
        *,
        gateway=LLMGateway.topic_advisory,
    ) -> None:
        self.analytics, self.settings, self.policy = analytics, settings, policy
        self._send = gateway
        self._lock = RLock()
        self._tickets: dict[str, _Ticket] = {}
        self._active: dict[str, _Ticket] = {}
        self._displayed: dict[str, _Ticket] = {}

    def invalidate(self, token: str | None) -> None:
        if token is None:
            return
        with self._lock:
            for collection in (self._tickets, self._active, self._displayed):
                if ticket := collection.pop(token, None):
                    ticket.cancelled.set()

    def _candidate(self, token, generation, source):
        if source.request is None:
            return None
        try:
            route = self.settings.advisory_key(token)
        except AccessDenied:
            raise
        except ApplicationError:
            return None
        if route is None:
            return None
        profile, provider, model, revision, key = route
        evidence = self.policy(profile, source.scope_digest)
        if evidence is None:
            return None
        prepared = make_topic_request(provider, model, source.request)
        verified = ProviderPrivacyProfileV1(
            profile_id=profile,
            credential_revision=revision,
            provider=provider,
            account_reference=evidence.provider_profile.account_reference,
            endpoint=prepared.url,
            model=model,
            mode=MODE,
        )
        if not evidence.permits(
            scope_digest=source.scope_digest,
            provider_profile=verified,
            data_class="real",
            now=datetime.now(UTC),
        ):
            return None
        binding = AdvisoryPreviewBinding(
            token,
            generation,
            source.scope_digest,
            source.source_digest,
            evidence,
            sha256(prepared.body).hexdigest(),
        )
        return binding, prepared, key

    def preview(
        self, token: str, query: AnalyticsQueryV1, generation: int, cancelled: Event
    ) -> AdvisoryPreview:
        with self._lock:
            self.invalidate(token)
            if cancelled.is_set():
                raise AccessDenied()
            query = self.analytics._query(query)
            source = self.analytics.advisory_source(token, query)
            recommendations = offline_recommendations(source.request)
            candidate = self._candidate(token, generation, source)
            if cancelled.is_set():
                raise AccessDenied()
            if candidate is None:
                return AdvisoryPreview(None, source.scope_digest, recommendations, None)
            binding, request, _ = candidate
            identifier = uuid4().hex
            self._tickets[token] = _Ticket(
                identifier, query, binding, request, monotonic() + 120, Event()
            )
            return AdvisoryPreview(
                identifier, source.scope_digest, recommendations, request
            )

    def _fresh(self, token, ticket):
        source = self.analytics.advisory_source(token, ticket.query)
        candidate = self._candidate(token, ticket.binding.ui_generation, source)
        if candidate is None:
            return source, None
        binding, prepared, key = candidate
        same = binding == ticket.binding and prepared == ticket.request
        return source, key if same else None

    def _check_ticket(self, token, ticket, cancelled):
        if (
            cancelled.is_set()
            or ticket.cancelled.is_set()
            or self._active.get(token) is not ticket
        ):
            raise AccessDenied()

    def dispatch(
        self, token: str, identifier: str, generation: int, cancelled: Event
    ) -> AdvisoryResult:
        with self._lock:
            ticket = self._tickets.get(token)
            if (
                ticket is None
                or ticket.identifier != identifier
                or ticket.binding.ui_generation != generation
            ):
                raise AccessDenied()
            del self._tickets[token]
            self._active[token] = ticket
        try:
            self._check_ticket(token, ticket, cancelled)
            source, key = self._fresh(token, ticket)
            recommendations = None
            admitted = False
            if key is not None and monotonic() < ticket.expires:

                def admit() -> bool:
                    nonlocal admitted
                    with (
                        self._lock,
                        self.settings.guard,
                        self.analytics.accounts.sessions.guard(token),
                    ):
                        self._check_ticket(token, ticket, cancelled)
                        if admitted:
                            return False
                        _, current_key = self._fresh(token, ticket)
                        admitted = (
                            current_key == key
                            and monotonic() < ticket.expires
                            and not cancelled.is_set()
                            and not ticket.cancelled.is_set()
                        )
                        return admitted

                try:
                    recommendations = self._send(
                        source.request,
                        ticket.request,
                        key,
                        admit,
                    )
                except GenerationError:
                    pass
            with self._lock:
                self._check_ticket(token, ticket, cancelled)
                current, current_key = self._fresh(token, ticket)
                if admitted and recommendations is not None and current_key is not None:
                    self._displayed[token] = ticket
                    return AdvisoryResult(True, recommendations)
                return AdvisoryResult(False, offline_recommendations(current.request))
        finally:
            with self._lock:
                if self._active.get(token) is ticket:
                    del self._active[token]

    def check_display(self, token: str) -> bool:
        with self._lock:
            ticket = self._displayed.get(token)
            if ticket is None:
                return False
            _, key = self._fresh(token, ticket)
            if key is None:
                self.invalidate(token)
            return key is not None
