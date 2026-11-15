"""Instructor publication UX with isolated synthetic offline materials."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from cyberforge.application.email_materials import EmailMaterialService
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.groups.service import GroupService
from cyberforge.llm.factory import create_gateway
from cyberforge.ui.navigation import View
from cyberforge.ui.scenario_integration import IntegrationDialog
from cyberforge.ui.shell import MainWindow
from cyberforge.ui.theme import apply_theme


@pytest.fixture
def integration_window(qtbot, qapp, scenario_env):
    env = scenario_env
    apply_theme(qapp)
    token = env.tokens["teacher"]
    emails = EmailMaterialService(env.service, create_gateway(), demo=True)
    webs = WebMaterialService(emails, demo=True)
    env.scenario = env.service.create(
        token, dict(topic="Навчальний сценарій", difficulty="beginner")
    )
    ew = emails.load(token, env.scenario)
    emails.save(token, ew, emails.generate(token, ew))
    ww = webs.load(token, env.scenario)
    webs.save(token, ww, webs.generate(token, ww))
    env.group = GroupService(env.accounts).save_group(
        env.tokens["admin"],
        "Група UI",
        instructors=(env.accounts.current(token).id,),
        learners=(),
    )
    window = MainWindow(env.accounts, emails, webs)
    qtbot.addWidget(window, before_close_func=lambda w: w.scenario_page.clear())
    window._authenticated(token)
    window.navigate(View.CONSTRUCTOR)
    window.scenario_page.load(env.scenario, editable=True)
    window.resize(1100, 720)
    window.show()
    window.test_env = env
    return window


def dialog(window, qtbot):
    page = window.scenario_page
    widget = IntegrationDialog(
        page.integration, lambda: window._token, page.scenario, owned=True, parent=page
    )
    qtbot.addWidget(widget, before_close_func=lambda d: d.force_close())
    widget.show()
    return widget


def configure(widget):
    assert widget.save_link()
    widget.criteria["email.sender"][0].setChecked(True)
    widget.criteria["transition.safe_decline"][0].setChecked(True)
    widget.criteria["web.address"][0].setChecked(True)
    assert widget.save_rubric()
    widget.groups.item(0).setCheckState(Qt.CheckState.Checked)
    assert widget.report.technical_ready


def test_editors_readiness_inert_preview_and_cancel(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    d = dialog(window, qtbot)
    assert not d.report.technical_ready
    assert not d.save_rubric()
    assert "Рубрика" in d.message.text()
    configure(d)
    assert d.state.link.display_url in d.mail.body.toPlainText()
    assert d.state.link.link_label in d.mail.body.toPlainText()
    assert "href=" not in d.mail.body.toHtml()
    d.mail.open_message(1)
    assert d.state.link.display_url not in d.mail.body.toPlainText()
    d.mail.open_message(0)
    assert d.state.link.display_url in d.mail.body.toPlainText()
    assert not d.publish()
    assert "підтвердьте" in d.message.text()
    d.ack.setChecked(True)
    monkeypatch.setattr(d, "final_confirmation", lambda: False)
    assert d.publish() is False
    assert window.scenario_page.publications.history(window._token, d.expected.id) == ()
    assert d.ack.isChecked()
    d.groups.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert not d.ack.isChecked()
    d.link_label.setText("Незбережена назва")
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Cancel)
    d.reject()
    assert d.isVisible() and d.dirty
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Discard)
    d.reject()
    assert not d.isVisible()
    state = window.scenario_page.integration.inspect(
        window._token, window.test_env.scenario
    )
    assert state.link.link_label != "Незбережена назва"


def test_explicit_publication_readonly_grants_and_next_draft(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    d = dialog(window, qtbot)
    configure(d)
    d.ack.setChecked(True)
    monkeypatch.setattr(d, "final_confirmation", lambda: True)
    assert d.publish(), d.message.text()
    assert d.expected.status == "published"
    assert not d.save_link_button.isEnabled()
    assert not d.save_rubric_button.isEnabled()
    assert d.link_label.isReadOnly() and d.display_url.isReadOnly()
    assert not d.publish_button.isEnabled()
    assert d.grant_groups.count() == 1
    d.grant_groups.setCurrentRow(0)
    d.change_grant(False)
    assert "revoke" in d.audit_text.toPlainText()
    d.change_grant(True)
    assert len(d.publications.audit(window._token, d.history.currentData())) == 3
    d.reject()
    page = window.scenario_page
    page.load(
        window.scenarios.get(window._token, window.test_env.scenario.id), editable=True
    )
    assert page.new_version_button.isVisible()
    assert "Опубліковано" in page.integration_status.text()
    page.create_next_version()
    assert page.scenario.version == 2 and page.scenario.status == "draft"
    assert not page.new_version_button.isVisible()
    assert page.emails.load(window._token, page.scenario).draft is None
    assert len(page.publications.history(window._token, page.scenario.id)) == 1
    historical = dialog(window, qtbot)
    historical.load_history()
    assert historical.expected.version == 1 and not historical.writable
    assert historical.mail.draft is not None


def test_unsaved_save_remain_guard_and_source_changed_after_review(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    d = dialog(window, qtbot)
    configure(d)
    d.link_label.setText("Явно збережена назва")
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Save)
    d.reject()
    assert not d.isVisible()
    assert (
        window.scenario_page.integration.inspect(
            window._token, window.test_env.scenario
        ).link.link_label
        == "Явно збережена назва"
    )
    d = dialog(window, qtbot)
    d.groups.item(0).setCheckState(Qt.CheckState.Checked)
    d.ack.setChecked(True)
    ew = window.emails.load(window._token, d.expected)
    window.emails.save(window._token, ew, ew.draft)
    monkeypatch.setattr(d, "final_confirmation", lambda: True)
    assert not d.publish()
    assert d.publications.history(window._token, d.expected.id) == ()
    d.check_readiness()
    assert d.report is None and not d.publish_button.isEnabled()


def test_session_change_clears_open_review_and_forbids_old_actions(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    d = dialog(window, qtbot)
    configure(d)
    d.ack.setChecked(True)
    window._authenticated(window.test_env.tokens["other"])
    assert not d.publish()
    assert "Сесію змінено" in d.message.text()
    window.scenario_page.clear()
    assert not d.isVisible() and d.state is None and d.mail.draft is None
    assert d.link_label.text() == d.display_url.text() == ""


def test_compact_page_and_scrollable_dialog(integration_window, qtbot):
    window = integration_window
    page = window.scenario_page
    qtbot.wait(30)
    viewport = window.containers[View.CONSTRUCTOR].viewport()
    for control in (page.save_button, page.integration_button):
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().bottomRight())
        )
    assert page.width() <= viewport.width()
    d = dialog(window, qtbot)
    configure(d)
    assert d.width() <= 1100 and d.height() <= 720
    for index in (0, 1, 4, 5):
        d.tabs.setCurrentIndex(index)
        qtbot.wait(10)
        scroll = d.tabs.widget(index)
        assert scroll.widget().width() <= scroll.viewport().width()
        scroll.ensureWidgetVisible(
            d.publish_button
            if index == 4
            else d.save_rubric_button
            if index == 1
            else d.save_link_button
            if index == 0
            else d.audit_text
        )
    assert d.rect().contains(
        d.close_buttons.mapTo(d, d.close_buttons.rect().bottomRight())
    )


def test_published_weight_precision_and_explicit_invalid_weight(
    integration_window, qtbot
):
    d = dialog(integration_window, qtbot)
    d.criteria["email.sender"][0].setChecked(True)
    d.criteria["email.sender"][1].setText("0.000000000123")
    assert d.save_rubric()
    assert d.state.rubric.criteria[0].weight == 0.000000000123
    d.criteria["email.sender"][1].setText("nan")
    assert not d.save_rubric()
    assert "Вага" in d.message.text()


def test_actual_web_review_and_repeated_close(integration_window, qtbot):
    d = dialog(integration_window, qtbot)
    configure(d)
    d.tabs.setCurrentIndex(3)
    assert d.browser is not None
    qtbot.waitUntil(
        lambda: d.browser.view.url().scheme() == "cyberforge", timeout=10000
    )
    assert d.browser.rendered is not None
    assert d.browser.profile.isOffTheRecord()
    d.reject()
    assert d.browser is None
    d.force_close()
    assert d.state is None
