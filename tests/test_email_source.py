"""JSON-only source inspection; native content security lives in UI regressions."""

from cyberforge.ui.email_source import EmailSourceDialog


def test_source_module_has_no_html_projection():
    from cyberforge.ui import email_source

    assert not hasattr(email_source, "render_email_html")
    assert not hasattr(email_source, "HtmlHighlighter")
    assert hasattr(EmailSourceDialog, "clear_sources")
