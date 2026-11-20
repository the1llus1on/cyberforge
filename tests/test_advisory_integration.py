"""D12-09/10 through authorized A11 and exact mock transport captures."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import pytest
from pydantic import SecretStr

from cyberforge.analytics.advisory_authorization import (
    AdvisoryPolicyEvidenceV1,
    ProviderPrivacyProfileV1,
)
from cyberforge.analytics.topic_advisory import RECOMMENDATION_CATALOG
from cyberforge.application.policy_evidence import trusted_registry_dacl
from cyberforge.application.provider_settings import ProviderSettings
from cyberforge.application.topic_advisory import TopicAdvisory
from cyberforge.domain.accounts import AccessDenied
from cyberforge.llm.contracts import ErrorCategory, GenerationError, Provider
from cyberforge.llm.topic_transport import ENDPOINTS, MODE, send_topic_request
from cyberforge.llm.windows_credentials import WindowsCredentialStore
from cyberforge.persistence.profile import PrivateProfile
from tests.test_analytics import change_groups, complete, setup_services, table_state
from tests.test_scenario_integration import publication_env, publish  # noqa: F401

SAMPLE = "synthetic-credential-for-transport-test"


class InMemoryStore:
    def __init__(self):
        self.values = {}

    def read(self, provider):
        return self.values.get(provider)

    def write(self, provider, key):
        self.values[provider] = key

    def delete(self, provider):
        self.values.pop(provider, None)


class Response:
    status = 200

    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, limit):
        return self.body[:limit]


@pytest.fixture(params=["groq", "gemini"])
def workflow(request, publication_env, tmp_path):  # noqa: F811
    env = publication_env
    publish(env)
    ev, analytics, query = setup_services(env)
    attempt = complete(ev, env.tokens["learner"], env.scenario.id, inspect=True)
    result = ev.evaluate(env.tokens["learner"], attempt.attempt_id)
    provider = request.param
    model = "openai/gpt-oss-120b" if provider == "groq" else "gemini-4-hydrogen"
    source = analytics.advisory_source(env.token, query)
    assert source.request is not None
    assert len(analytics.summary(env.token, query).rows) == 1

    vault = InMemoryStore()
    profile = PrivateProfile(tmp_path / "protected")
    settings = ProviderSettings(env.accounts, profile, lambda _: vault)
    admin = env.tokens["admin"]
    assert settings.active_route()[0] is Provider.MOCK
    settings.replace_key(admin, provider, SecretStr(SAMPLE))
    assert settings.active_route()[0] is Provider.MOCK
    settings.activate(admin, provider, model)
    profile_id, _, _, revision, _ = settings.advisory_key(env.token)
    host, path = ENDPOINTS[provider]
    now = datetime.now(UTC)
    policy = [
        AdvisoryPolicyEvidenceV1(
            schema_version="advisory-policy-evidence-v1",
            purpose="instructor-topic-advisory",
            data_class="real",
            scope_digest=source.scope_digest,
            provider_profile=ProviderPrivacyProfileV1(
                profile_id=profile_id,
                credential_revision=revision,
                provider=provider,
                account_reference="verified-test-account",
                endpoint=f"https://{host}{path}",
                mode=MODE,
                model=model,
            ),
            organization_decision="test-approval",
            provider_privacy_review="test-account-review",
            responsible_party="Synthetic",
            assessed_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(minutes=1),
            revoked=False,
            residual_linkability_accepted=True,
        )
    ]
    topic = source.request.topics[-1]
    recommendation = next(
        code for code, value in RECOMMENDATION_CATALOG.items() if value[0] == topic
    )
    content = json.dumps(
        {
            "schema_version": "assistant-topic-selection-v1",
            "recommendations": [{"topic": topic, "recommendation_id": recommendation}],
        }
    )
    capture = []
    expected = [None]

    class Capture:
        def __init__(self, outgoing_host, *, timeout):
            assert outgoing_host == host
            assert timeout > 0

        def request(self, verb, outgoing_path, body, headers):
            assert verb == "POST" and outgoing_path == path
            assert body == expected[0]
            capture.append((body, headers))

        def getresponse(self):
            if provider == "groq":
                value = {
                    "choices": [
                        {"finish_reason": "stop", "message": {"content": content}}
                    ]
                }
            else:
                value = {
                    "status": "completed",
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [{"type": "text", "text": content}],
                        }
                    ],
                }
            return Response(value)

        def close(self):
            pass

    service = TopicAdvisory(
        analytics,
        settings,
        lambda *_: policy[0],
        gateway=lambda *args: send_topic_request(*args, connection=Capture),
    )
    return (
        env,
        settings,
        service,
        query,
        policy,
        expected,
        capture,
        result,
        recommendation,
    )


def test_one_learner_confirmed_once_with_exact_payload_and_no_database_writes(workflow):
    env, settings, advisory, query, _, expected, capture, result, recommendation = (
        workflow
    )
    previous = table_state(env)
    cancelled = Event()
    preview = advisory.preview(env.token, query, 7, cancelled)
    assert preview.identifier
    expected[0] = preview.request.body
    answer = advisory.dispatch(env.token, preview.identifier, 7, cancelled)
    assert answer.cloud and answer.recommendations == (
        RECOMMENDATION_CATALOG[recommendation][1],
    )
    with pytest.raises(AccessDenied):
        advisory.dispatch(env.token, preview.identifier, 7, cancelled)
    ((body, headers),) = capture
    provider = preview.request.provider
    outer = json.loads(body)
    if provider == "groq":
        payload = outer["messages"][1]["content"]
        assert headers["Authorization"] == "Bearer " + SAMPLE
    else:
        payload = outer["input"].splitlines()[-1]
        assert headers["x-goog-api-key"] == SAMPLE
        assert outer["store"] is outer["background"] is outer["stream"] is False
    assert set(json.loads(payload)) == {"schema_version", "topics"}
    for item in (
        SAMPLE,
        env.password,
        str(result.result_id),
        "learner",
        "score_percent",
    ):
        assert item.encode() not in body
    assert SAMPLE not in settings.path.read_text()
    assert table_state(env) == previous


def test_preview_rejects_other_roles_and_without_current_policy(workflow):
    env, settings, advisory, query, policy, _, capture, _, _ = workflow
    for token in (
        None,
        env.tokens["learner"],
        env.tokens["admin"],
        env.tokens["other"],
    ):
        with pytest.raises(AccessDenied):
            advisory.preview(token, query, 1, Event())
    for token in (env.token, env.tokens["learner"]):
        with pytest.raises(AccessDenied):
            settings.replace_key(token, "groq", None)
    policy[0] = None
    offline = advisory.preview(env.token, query, 1, Event())
    assert offline.identifier is None and offline.recommendations
    assert not capture


def test_changed_policy_credential_or_authorization_blocks_dispatch(workflow):
    env, settings, advisory, query, policy, _, capture, _, _ = workflow
    cancelled = Event()
    preview = advisory.preview(env.token, query, 1, cancelled)
    original = policy[0]
    policy[0] = original.model_copy(update={"revoked": True})
    assert not advisory.dispatch(env.token, preview.identifier, 1, cancelled).cloud
    policy[0] = original
    preview = advisory.preview(env.token, query, 2, cancelled)
    provider = preview.request.provider
    settings.replace_key(env.tokens["admin"], provider, SecretStr(SAMPLE + "changed"))
    settings.activate(env.tokens["admin"], provider, preview.request.model)
    assert not advisory.dispatch(env.token, preview.identifier, 2, cancelled).cloud
    assert not capture


def test_replay_concurrency_and_response_revocation(workflow):
    env, _, advisory, query, policy, _, capture, _, _ = workflow
    started, release = Event(), Event()
    call_count = []

    def in_flight(request, prepared, key, admit):
        assert admit()
        call_count.append(True)
        started.set()
        assert release.wait(5)
        return ("Відкладена порада",)

    advisory._send = in_flight
    cancelled = Event()
    preview = advisory.preview(env.token, query, 1, cancelled)
    with ThreadPoolExecutor() as executor:
        running = executor.submit(
            advisory.dispatch, env.token, preview.identifier, 1, cancelled
        )
        try:
            assert started.wait(5)
            with pytest.raises(AccessDenied):
                advisory.dispatch(env.token, preview.identifier, 1, cancelled)
            policy[0] = None
        finally:
            release.set()
        assert not running.result(timeout=5).cloud
    assert call_count == [True]
    assert not capture


def test_failure_is_deterministic_and_has_no_retry(workflow):
    env, _, advisory, query, _, _, _, _, _ = workflow
    calls = []

    def failed(request, prepared, key, admit):
        assert admit()
        assert not admit()
        calls.append(prepared.provider)
        raise GenerationError(ErrorCategory.TIMEOUT)

    advisory._send = failed
    cancellation = Event()
    preview = advisory.preview(env.token, query, 1, cancellation)
    result = advisory.dispatch(env.token, preview.identifier, 1, cancellation)
    assert not result.cloud
    assert result.recommendations == preview.recommendations
    assert calls == [preview.request.provider]


def test_historical_authorization_and_generation_are_revalidated(workflow):
    env, _, advisory, query, policy, _, capture, _, _ = workflow
    cancelled = Event()
    query = query.model_copy(update={"group_id": env.group.id})
    source = advisory.analytics.advisory_source(env.token, query)
    policy[0] = policy[0].model_copy(update={"scope_digest": source.scope_digest})
    preview = advisory.preview(env.token, query, 1, cancelled)
    with pytest.raises(AccessDenied):
        advisory.dispatch(env.token, preview.identifier, 2, cancelled)
    change_groups(env, env.group, learners=(env.learner_id,))
    with pytest.raises(AccessDenied):
        advisory.dispatch(env.token, preview.identifier, 1, cancelled)
    assert not capture


def test_registry_policy_dacl_requires_independent_authority():
    trusted = "O:BAD:P(A;;KA;;;BA)(A;;KA;;;SY)(A;;KR;;;BU)"
    assert trusted_registry_dacl(trusted)
    assert not trusted_registry_dacl(trusted.replace("KR", "KW"))
    assert not trusted_registry_dacl(trusted.replace("O:BA", "O:BU"))
    assert not trusted_registry_dacl("O:BAD:NO_ACCESS_CONTROL")


@pytest.mark.skipif(sys.platform != "win32", reason="uses native Credential Manager")
def test_native_vault_isolation_replace_and_delete():
    first = WindowsCredentialStore("test", uuid4().hex)
    second = WindowsCredentialStore("test", uuid4().hex)
    try:
        assert first.read("groq") is second.read("groq") is None
        first.write("groq", SecretStr(SAMPLE))
        assert first.read("groq") == SecretStr(SAMPLE)
        assert first.read("gemini") is second.read("groq") is None
        first.write("groq", SecretStr(SAMPLE + "replacement"))
        assert first.read("groq") == SecretStr(SAMPLE + "replacement")
    finally:
        first.delete("groq")
    assert first.read("groq") is None
