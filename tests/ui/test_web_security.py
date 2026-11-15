"""Actual Chromium isolation with controlled local HTTP instrumentation."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings

from cyberforge.ui.web_browser import WebBrowser


@pytest.fixture
def browser(qtbot):
    view = WebBrowser()
    qtbot.addWidget(view)
    view.resize(900, 600)
    view.show()
    return view


def load_html(browser, qtbot, html):
    browser.store.url = f"cyberforge://page/{uuid4().hex}/index"
    browser.store.html = html.encode()
    with qtbot.waitSignal(browser.page.loadFinished, timeout=15000) as done:
        browser.page.setUrl(QUrl(browser.store.url))
    assert done.args == [True]


def test_real_engine_load_and_profile(browser, qtbot):
    load_html(browser, qtbot, "<!doctype html><html><body>Local preview</body></html>")
    content = []
    browser.page.toPlainText(content.append)
    qtbot.waitUntil(lambda: bool(content))
    assert content == ["Local preview"]
    assert browser.profile.isOffTheRecord()
    for attribute in (
        "JavascriptEnabled",
        "LocalStorageEnabled",
        "LocalContentCanAccessRemoteUrls",
        "LocalContentCanAccessFileUrls",
        "DnsPrefetchEnabled",
    ):
        assert not browser.page.settings().testAttribute(
            getattr(QWebEngineSettings.WebAttribute, attribute)
        )
    assert (
        browser.page.createWindow(browser.page.WebWindowType.WebBrowserWindow) is None
    )
    assert browser.page.chooseFiles(None, [], []) == []


def test_actual_engine_external_resources_redirects_and_forms(browser, qtbot, tmp_path):
    hits = []

    class Endpoint(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/redirect-target")
            self.end_headers()

        def do_POST(self):
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    secret_file = tmp_path / "private.txt"
    secret_file.write_text("SYNTHETIC_PRIVATE_FILE")
    try:
        # Relax only this independent browser gate to exercise the interceptor.
        browser.page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        # Omit CSP deliberately to exercise independent request/navigation gates.
        html = f'''<!doctype html><html><head>
        <link rel="stylesheet" href="{url}/style.css">
        <script src="{url}/script.js"></script>
        <meta http-equiv="refresh" content="0;url={url}/redirect">
        </head><body><img src="{url}/image.png">
        <img src="https://127.0.0.1:{server.server_port}/tls-image">
        <iframe src="{secret_file.as_uri()}"></iframe>
        <a href="{url}/link">External</a>
        <form action="{url}/submit" method="POST"><input name="x" value="synthetic">
        <button type="submit">Send</button></form></body></html>'''
        load_html(browser, qtbot, html)
        qtbot.wait(500)
        assert hits == []
        assert browser.page.url().toString() == browser.store.url
        assert "http" in browser.gate.blocked
        for target in (
            url + "/navigation",
            secret_file.as_uri(),
            "https://example.com/",
            "data:text/html,external",
        ):
            with qtbot.waitSignal(browser.page.loadFinished, timeout=10000):
                browser.page.setUrl(QUrl(target))
        qtbot.wait(100)
        assert hits == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_actual_clicks_form_popup_download_and_disabled_script(browser, qtbot):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWebEngineCore import QWebEnginePage

    target = "http://127.0.0.1:9/forbidden"
    # JS disabled even without CSP. No submit/open/download reaches the network.
    html = f'''<!doctype html><html><head><title>Inert</title>
    <script>document.title='EXECUTED';window.open('{target}');</script>
    <style>body{{margin:0}}a,button{{display:block;position:absolute;left:0;width:180px;height:40px}}
    </style></head><body>
    <a style="top:0" target="_blank" href="{target}">Popup</a>
    <a style="top:50px" download href="{target}">Download</a>
    <form action="{target}" method="POST"><input type="hidden" value="synthetic">
    <button style="top:100px" type="submit">Submit</button></form>
    <a style="top:150px" href="cyberforge://action/fixture/confirm">Confirm</a>
    </body></html>'''
    browser.store.actions = {"cyberforge://action/fixture/confirm": "confirm"}
    events = []
    browser.page.action_requested.connect(events.append)
    load_html(browser, qtbot, html)
    assert browser.page.title() == "Inert"
    original = browser.store.url
    for y in (20, 70, 120):
        qtbot.mouseClick(
            browser.view.focusProxy(), Qt.MouseButton.LeftButton, pos=QPoint(70, y)
        )
        qtbot.wait(80)
        assert browser.page.url().toString() == original
    qtbot.mouseClick(
        browser.view.focusProxy(), Qt.MouseButton.LeftButton, pos=QPoint(70, 170)
    )
    qtbot.waitUntil(lambda: events == ["confirm"], timeout=3000)
    assert browser.page.url().toString() == original
    assert browser.page.createWindow(QWebEnginePage.WebWindowType.WebBrowserTab) is None
