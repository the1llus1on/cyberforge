"""Register the local scheme before QApplication, never a real network origin."""

from PySide6.QtWebEngineCore import QWebEngineUrlScheme


def register_web_scheme() -> None:
    if bytes(QWebEngineUrlScheme.schemeByName(b"cyberforge").name()):
        return
    scheme = QWebEngineUrlScheme(b"cyberforge")
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme | QWebEngineUrlScheme.Flag.LocalScheme
    )
    QWebEngineUrlScheme.registerScheme(scheme)
