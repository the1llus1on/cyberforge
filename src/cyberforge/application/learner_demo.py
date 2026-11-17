"""Explicit offline publication setup through accepted application services."""

import json

from cyberforge.application.accounts import AccountService
from cyberforge.application.email_materials import EmailMaterialService
from cyberforge.application.scenario_integration import ScenarioIntegrationService
from cyberforge.application.scenario_publication import ScenarioPublicationService
from cyberforge.application.scenario_readiness import ScenarioReadinessService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.groups.service import GroupService
from cyberforge.llm.config import GatewayConfig
from cyberforge.llm.factory import create_gateway
from cyberforge.scenario_integration.contracts import criterion
from cyberforge.web.contracts import ACTIONS, Actions, ActionV2, WebDraftV3
from cyberforge.web.presets import default_component


def demo_web_actions(draft: WebDraftV3) -> WebDraftV3:
    """App-owned editable components, validated and saved before publication."""
    from cyberforge.web.contracts import Form

    components = [c for c in draft.page.components if c.type != "actions"]
    if not any(c.type == "form" for c in components):
        components.insert(
            -1,
            Form.model_validate_json(
                json.dumps(default_component("form", "demo_form"))
            ),
        )
    components.insert(
        -1,
        Actions(
            id="learner_actions",
            actions=tuple(
                ActionV2(id=action, label=ACTIONS[action])
                for action in ("inspect_address", "report", "leave", "confirm")
            ),
        ),
    )
    value = draft.model_copy(
        update={"page": draft.page.model_copy(update={"components": tuple(components)})}
    )
    return WebDraftV3.model_validate_json(value.model_dump_json())


def prepare_publication(accounts: AccountService, credentials_path):
    """Called only after successful fresh demo initialization; never cloud APIs."""
    credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
    token = accounts.login("teacher_demo_1", credentials["teacher_demo_1"])
    try:
        scenarios = ScenarioService(accounts)
        emails = EmailMaterialService(
            scenarios, create_gateway(GatewayConfig()), demo=True
        )
        webs = WebMaterialService(emails, demo=True)
        integration = ScenarioIntegrationService(webs)
        readiness = ScenarioReadinessService(integration)
        publications = ScenarioPublicationService(readiness)
        scenario = scenarios.create(
            token,
            dict(
                topic="Навчальний портал: перевірка повідомлення", difficulty="beginner"
            ),
        )
        ew = emails.load(token, scenario)
        emails.save(token, ew, emails.generate(token, ew))
        ww = webs.load(token, scenario)
        webs.save(token, ww, demo_web_actions(webs.generate(token, ww, preset="login")))
        state = integration.inspect(token, scenario)
        integration.save_link(
            token,
            scenario,
            link_label="Відкрити навчальний портал",
            display_url=state.web.page.display_url,
            target_resource_id=state.web.page.internal_resource_id,
            expected_revision=0,
            expected_email_revision=state.checked_sources["email_revision"],
            expected_web_revision=state.checked_sources["web_revision"],
        )
        integration.save_rubric(
            token,
            scenario,
            (
                criterion("email.sender"),
                criterion("transition.safe_decline"),
                criterion("web.address"),
            ),
            expected_revision=0,
        )
        group = next(
            g for g in GroupService(accounts).list_groups(token) if g.name == "Група A"
        )
        report = readiness.evaluate(token, scenario, selected_group_ids=(group.id,))
        receipt = readiness.confirm(
            token,
            scenario,
            review_fingerprint=report.review_fingerprint,
            selected_group_ids=report.selected_group_ids,
            acknowledged_warnings=report.acknowledgement_requirements,
            semantic_review=True,
        )
        return publications.publish(
            token, scenario, confirmation_id=receipt.confirmation_id
        )
    finally:
        accounts.logout(token)
