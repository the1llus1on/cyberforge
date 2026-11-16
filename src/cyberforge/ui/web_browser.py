"""Isolated single-page browser with deny-by-default networking and navigation."""

import logging
from uuid import uuid4

from PySide6.QtCore import QBuffer, QIODevice, QObject, Qt, QUrl, Signal
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInterceptor,
    QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)
from shiboken6 import delete, isValid

from cyberforge.web.contracts import WebDraftV3
from cyberforge.web.renderer import RenderedPage, action_url, render_page


def release_engine(view, page, profile) -> None:
    if isValid(view):
        delete(view)
    if isValid(page):
        delete(page)
    if isValid(profile):
        delete(profile)


class ResourceStore(QObject):
    """Only one approved document per browser; references swapped on the GUI thread."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.url = ""
        self.html = b""
        self.actions: dict[str, str] = {}


class RequestGate(QWebEngineUrlRequestInterceptor):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.blocked: list[str] = []

    def interceptRequest(self, info) -> None:
        allowed = (
            info.requestUrl().toString() == self.store.url
            and bytes(info.requestMethod()) == b"GET"
            and info.resourceType() == info.ResourceType.ResourceTypeMainFrame
        )
        if not allowed:
            # Record only scheme, never credential-bearing URLs or content.
            if len(self.blocked) < 64:
                self.blocked.append(info.requestUrl().scheme())
            info.block(True)


class LocalHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.buffers = {}

    def requestStarted(self, job) -> None:
        if (
            job.requestUrl().toString() != self.store.url
            or bytes(job.requestMethod()) != b"GET"
        ):
            job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
            return
        buffer = QBuffer(job)
        buffer.setData(self.store.html)
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        # Qt consumes QIODevice asynchronously. Keep its Python wrapper alive
        # until the request job releases it, including overlapping reloads.
        key = id(job)
        self.buffers[key] = buffer
        job.destroyed.connect(lambda: self.buffers.pop(key, None))
        job.reply(b"text/html", buffer)


class IsolatedPage(QWebEnginePage):
    action_requested = Signal(str)

    def __init__(self, profile, store, parent=None):
        super().__init__(profile, parent)
        self.store = store
        self.permissionRequested.connect(lambda permission: permission.deny())
        self.fileSystemAccessRequested.connect(lambda request: request.reject())
        self.fullScreenRequested.connect(lambda request: request.reject())
        self.registerProtocolHandlerRequested.connect(lambda request: request.reject())
        self.certificateError.connect(lambda error: error.rejectCertificate())
        self.newWindowRequested.connect(lambda request: None)

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame) -> bool:
        address = url.toString()
        if (
            is_main_frame
            and navigation_type == self.NavigationType.NavigationTypeLinkClicked
            and address in self.store.actions
        ):
            self.action_requested.emit(self.store.actions[address])
            return False
        return bool(is_main_frame and address == self.store.url)

    def createWindow(self, window_type):
        return None

    def chooseFiles(self, mode, old_files, accepted_mime_types):
        return []


class BrowserTab(QLabel):
    """Elide visual metadata without letting it set the workspace width."""

    def __init__(self):
        super().__init__()
        self.full_title = ""
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def set_title(self, title):
        self.full_title = "◈  " + title
        self.setToolTip(title)
        self._elide()

    def _elide(self):
        self.setText(
            self.fontMetrics().elidedText(
                self.full_title, Qt.TextElideMode.ElideRight, max(0, self.width() - 16)
            )
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()


class WebBrowser(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._disposed = False
        self.render_failed = False
        self.setMinimumHeight(220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.tab = BrowserTab()
        self.tab.set_title("Нова навчальна сторінка")
        self.tab.setStyleSheet(
            "padding:8px;background:#303643;color:#f2f4fa;border-radius:8px;"
        )
        layout.addWidget(self.tab)
        controls = QHBoxLayout()
        self.back = QPushButton("←")
        self.forward = QPushButton("→")
        self.reload = QPushButton("↻")
        for button, name in (
            (self.back, "Назад"),
            (self.forward, "Вперед"),
            (self.reload, "Оновити"),
        ):
            button.setAccessibleName(name)
            button.setFixedWidth(34)
            button.setStyleSheet("padding:4px")
            controls.addWidget(button)
        self.back.setEnabled(False)
        self.forward.setEnabled(False)
        self.address = QLineEdit()
        self.address.setReadOnly(True)
        self.address.setAccessibleName("Навчальна адреса, лише відображення")
        controls.addWidget(self.address, 1)
        layout.addLayout(controls)
        self.view = QWebEngineView(self)
        self.store = ResourceStore(self)
        # Dedicated profile, independent of application authentication state.
        self.profile = QWebEngineProfile(self)
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        self.profile.setPersistentPermissionsPolicy(
            QWebEngineProfile.PersistentPermissionsPolicy.AskEveryTime
        )
        self.profile.downloadRequested.connect(lambda download: download.cancel())
        self.gate = RequestGate(self.store, self.profile)
        self.profile.setUrlRequestInterceptor(self.gate)
        self.handler = LocalHandler(self.store, self.profile)
        self.profile.installUrlSchemeHandler(b"cyberforge", self.handler)
        self.page = IsolatedPage(self.profile, self.store, self.view)
        settings = self.page.settings()
        for name in (
            "JavascriptEnabled",
            "JavascriptCanOpenWindows",
            "JavascriptCanAccessClipboard",
            "LocalStorageEnabled",
            "LocalContentCanAccessRemoteUrls",
            "LocalContentCanAccessFileUrls",
            "HyperlinkAuditingEnabled",
            "FullScreenSupportEnabled",
            "ScreenCaptureEnabled",
            "WebGLEnabled",
            "Accelerated2dCanvasEnabled",
            "PluginsEnabled",
            "PdfViewerEnabled",
            "DnsPrefetchEnabled",
            "NavigateOnDropEnabled",
            "AllowRunningInsecureContent",
        ):
            settings.setAttribute(getattr(QWebEngineSettings.WebAttribute, name), False)
        settings.setUnknownUrlSchemePolicy(
            QWebEngineSettings.UnknownUrlSchemePolicy.DisallowUnknownUrlSchemes
        )
        self.view.setPage(self.page)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        layout.addWidget(self.view, 1)
        self.feedback = QLabel("")
        self.feedback.setWordWrap(True)
        self.feedback.setStyleSheet("padding:4px;font-size:12px")
        layout.addWidget(self.feedback)
        self.page.loadFinished.connect(self._load_finished)
        self.page.renderProcessTerminated.connect(self._renderer_terminated)
        self.page.action_requested.connect(self.interact)
        self.reload.clicked.connect(self.reload_current)
        self.rendered: RenderedPage | None = None
        self.draft: WebDraftV3 | None = None
        view, page, profile = self.view, self.page, self.profile
        self.destroyed.connect(lambda: release_engine(view, page, profile))

    def dispose(self) -> None:
        self._disposed = True
        release_engine(self.view, self.page, self.profile)

    def _load_finished(self, success: bool) -> None:
        if self._disposed:
            return
        if not success:
            self.render_failed = True
            self.feedback.setText(
                "Не вдалося завантажити локальний перегляд. "
                "Натисніть «Оновити» або закрийте й повторно відкрийте перегляд. "
                "Збережені матеріали не змінено."
            )
        elif not self.render_failed:
            self.feedback.clear()

    def _renderer_terminated(self, status, exit_code: int) -> None:
        if self._disposed:
            return
        self.render_failed = True
        # Only engine status/code; never log URLs, artifact text or credentials.
        logging.getLogger(__name__).warning(
            "Web preview renderer terminated: status=%s exit_code=%d",
            status.name,
            exit_code,
        )
        self.feedback.setText(
            "Процес відображення Web завершив роботу. "
            "Натисніть «Оновити» або закрийте й повторно відкрийте перегляд. "
            "Збережені матеріали не змінено."
        )

    def closeEvent(self, event) -> None:
        self.dispose()
        super().closeEvent(event)

    def set_draft(self, draft: WebDraftV3 | None) -> None:
        self.draft = draft
        self.render_failed = False
        self.feedback.clear()
        self.store.actions = {}
        self.store.html = b""
        self.store.url = ""
        self.rendered = None
        self.reload.setEnabled(draft is not None)
        if draft is None:
            self.view.stop()
            self.store.url = f"cyberforge://page/{uuid4().hex}/empty"
            self.store.html = b"<!doctype html><html><body></body></html>"
            self.page.setUrl(QUrl(self.store.url))
            self.view.hide()
            self.tab.set_title("Нова навчальна сторінка")
            self.address.clear()
            return
        nonce = uuid4().hex
        self.rendered = render_page(draft.page, nonce=nonce)
        self.store.url = f"cyberforge://page/{nonce}/index"
        self.store.html = self.rendered.html.encode("utf-8")
        self.store.actions = {
            action_url(nonce, c.id, a.id): a.id
            for c in draft.page.components
            for a in getattr(c, "actions", ())
        }
        self.tab.set_title(draft.page.tab_title)
        self.address.setText(draft.page.display_url)
        self.view.show()
        self.page.setUrl(QUrl(self.store.url))

    def reload_current(self) -> None:
        if self.draft is not None and not self._disposed:
            self.render_failed = False
            self.feedback.clear()
            self.page.setUrl(QUrl(self.store.url))

    def interact(self, action: str) -> None:
        # The page emits only allowed IDs; independently gate direct controller calls.
        if action not in self.store.actions.values() or self.draft is None:
            return
        messages = {
            "inspect_address": "Навчальна адреса: " + self.draft.page.display_url,
            "leave": "Локальне демо: вихід зі сторінки підтверджено.",
            "report": "Локальне демо: повідомлення про підозру перевірено.",
            "confirm": "Локальне демо: підтвердження виконано.",
            "submit_synthetic": (
                "Навчальну форму перевірено з фіксованими синтетичними значеннями."
            ),
        }
        self.feedback.setText(messages[action])
