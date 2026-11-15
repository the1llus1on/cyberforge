"""The actual inspected HTML/CSS are deterministic controlled rendering inputs."""

import json
from html.parser import HTMLParser

import pytest

from cyberforge.web.contracts import COMPONENTS, THEMES, WebPageV2
from cyberforge.web.presets import default_component
from cyberforge.web.renderer import CSP, render_page


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_all_components_deterministic_escaped_no_external_resources(theme, mode):
    components = [default_component(kind, f"c{i}") for i, kind in enumerate(COMPONENTS)]
    components[1]["text"] = 'Синтетичний текст & "лапки"'
    page = WebPageV2.model_validate_json(
        json.dumps(
            dict(
                tab_title="Навчальний сайт",
                display_url="https://portal.example/",
                internal_resource_id="test",
                theme=theme,
                color_mode=mode,
                components=components,
            )
        )
    )
    result = render_page(page)
    assert result == render_page(page)
    assert result.css in result.html
    assert "&amp;" in result.html and "&quot;" in result.html
    assert "https://portal.example/" not in result.html
    parser = Tags()
    parser.feed(result.html)
    assert {"script", "iframe", "form", "object", "img", "link"}.isdisjoint(
        tag for tag, _ in parser.tags
    )
    for tag, attrs in parser.tags:
        assert not any(k.startswith("on") for k in attrs)
        if "href" in attrs:
            assert attrs["href"].startswith("cyberforge://action/inspection/")
        if tag == "input":
            assert "readonly" in attrs and attrs["value"] == "demo-student"
            assert "name" not in attrs
    assert "form-action 'none'" in CSP and "script-src 'none'" in CSP


def test_mutated_model_cannot_bypass_renderer_validation():
    page = WebPageV2.model_construct(tab_title="<script>", display_url="file:///x")
    with pytest.raises((ValueError, AttributeError)):
        render_page(page)
