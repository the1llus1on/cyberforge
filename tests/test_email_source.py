"""The inspected HTML is a deterministic content projection, never executable UI."""

from html.parser import HTMLParser

import pytest

from cyberforge.agents.demo import email_input, email_payload, scripted_gateway
from cyberforge.agents.specialized import EmailScenarioAgent
from cyberforge.ui.email_source import render_email_html


@pytest.fixture
def draft():
    source = email_input()
    gateway, _ = scripted_gateway(email_payload(source))
    result = EmailScenarioAgent(gateway).run(source)
    assert result.draft is not None
    return result.draft


class ProjectionParser(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tags = []
        self.attributes = []
        self.data = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)

    def handle_data(self, data):
        self.data.append(data)


@pytest.mark.parametrize("index", [0, 1])
def test_content_projection_matches_selected_message_and_keeps_canonical(draft, index):
    before = draft.model_dump_json()
    html = render_email_html(draft, index)
    parsed = ProjectionParser(html)
    message = [draft.slots.main, *draft.slots.background][index]
    text = "\n".join(parsed.data)
    assert message.subject in text
    assert message.sender_name in text and message.sender_address in text
    assert message.body_text in text
    assert "participant@training.invalid" in text
    assert ("09:30" if index == 0 else "09:25") in text
    assert {"article", "header", "h1", "dl", "section", "footer"} <= set(parsed.tags)
    assert set(parsed.tags) <= {
        "html",
        "head",
        "meta",
        "title",
        "body",
        "article",
        "header",
        "h1",
        "dl",
        "dt",
        "dd",
        "p",
        "section",
        "br",
        "footer",
    }
    assert {name for name, _ in parsed.attributes} <= {"lang", "charset", "aria-label"}
    assert html == render_email_html(draft, index)
    assert draft.model_dump_json() == before


def test_projection_escapes_fields_even_when_validation_is_bypassed(draft):
    injected = '</h1><script>run()</script><img src="https://outside.invalid/x"> & "'
    message = draft.slots.main.model_copy(
        update={
            "subject": injected,
            "sender_name": injected,
            "sender_address": injected,
            "body_text": injected,
        }
    )
    tampered = draft.model_copy(
        update={
            "slots": draft.slots.model_copy(
                update={
                    "main": message,
                    "internal_resource_id": injected,
                }
            )
        }
    )
    html = render_email_html(tampered)
    parsed = ProjectionParser(html)
    assert "script" not in parsed.tags and "img" not in parsed.tags
    assert all(
        name not in {"src", "href", "style", "onerror"} for name, _ in parsed.attributes
    )
    assert "&lt;script&gt;" in html and "&amp;" in html and "&quot;" in html
    assert injected in "\n".join(parsed.data)


@pytest.mark.parametrize("index", [-1, 9])
def test_projection_rejects_unknown_message(draft, index):
    with pytest.raises(ValueError):
        render_email_html(draft, index)
