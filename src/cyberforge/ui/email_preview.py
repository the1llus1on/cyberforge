"""Native, isolated Gmail-inspired training mailbox. No web renderer or URLs."""

from PySide6.QtCore import QRect, QSignalBlocker, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPen, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cyberforge.agents.contracts import EmailDraftV2
from cyberforge.ui.email_body import MessageBody
from cyberforge.ui.icons import icon

MAILBOX_ADDRESS = "participant@training.invalid"


def training_time(index: int) -> str:
    minutes = 9 * 60 + 30 - index * 5
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _text(text: str, name: str = "") -> QLabel:
    result = QLabel(text)
    result.setObjectName(name)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setMinimumWidth(0)
    return result


def _tool(
    symbol: str, name: str, *, enabled: bool = False, size: int = 30
) -> QToolButton:
    result = QToolButton()
    glyph = icon(symbol, color="#5f6368")
    glyph.addPixmap(glyph.pixmap(20, 20), QIcon.Mode.Disabled)
    result.setIcon(glyph)
    result.setIconSize(QSize(20, 20))
    result.setAccessibleName(name)
    result.setToolTip(name if enabled else name + " · лише навчальний макет")
    result.setEnabled(enabled)
    result.setFixedSize(size, size)
    return result


LIGHT_STYLE = """
QWidget { color: #202124; font-family: Arial; font-size: 14px;
    background: transparent; }
QFrame#emailPreview { background: #f6f8fc; border: 1px solid #c7cbd1;
    border-radius: 12px; }
QFrame#browserTabs { background: #dfe3eb; border-top-left-radius: 11px;
    border-top-right-radius: 11px; }
QFrame#browserTab { background: #f6f8fc; border-radius: 7px; }
QLabel#browserTabTitle { font-size: 12px; }
QLabel#browserNotice { color: #5f6368; font-size: 11px; }
QLineEdit#browserAddress { background: #edf0f5; border: none; border-radius: 12px;
    padding: 4px 12px; color: #5f6368; font-size: 12px; }
QLineEdit#mailSearch { background: #eaf1fb; border: none; border-radius: 20px;
    padding: 10px 12px; color: #202124; }
QLineEdit:focus { border: 1px solid #1a73e8; }
QLabel#mailBrand { font-size: 22px; color: #5f6368; }
QLabel#mailMark { color: #d93025; font-size: 25px; font-weight: 700; }
QFrame#mailSheet { background: #ffffff; border-radius: 12px; }
QPushButton { color: #202124; background: transparent; border: none;
    border-radius: 15px; padding: 6px 12px; text-align: left; }
QPushButton:hover, QToolButton:hover { background: #e4e9f1; }
QPushButton:focus, QToolButton:focus { border: 1px solid #1a73e8; }
QPushButton#compose { background: #c2e7ff; border-radius: 15px; padding: 14px 12px; }
QPushButton#inboxFolder { background: #d3e3fd; font-weight: 600; }
QWidget#mailFolders QPushButton { padding: 7px 12px; }
QWidget#mailFolders QPushButton#compose { padding: 14px 12px; }
QPushButton#reply, QPushButton#mailForward { border: 1px solid #9aa0a6;
    border-radius: 17px; padding: 7px 16px; color: #444746; }
QPushButton:disabled { color: #69717c; }
QToolButton { color: #5f6368; background: transparent; border: none;
    border-radius: 14px; font-size: 17px; }
QToolButton:disabled { color: #7c828b; }
QFrame#category { border-bottom: 3px solid #0b57d0; }
QLabel#categoryTitle { color: #0b57d0; font-weight: 600; }
QLabel#recipient, QLabel#timestamp, QLabel#resource {
    color: #5f6368; font-size: 12px; }
QPlainTextEdit, QTextEdit { background: #ffffff; color: #202124; border: none;
    selection-background-color: #d3e3fd; selection-color: #202124; }
QPlainTextEdit#mailSubject { font-size: 22px; }
QPlainTextEdit#mailSender { font-size: 14px; }
QTextEdit#mailBody { font-size: 15px; }
QListWidget { background: #ffffff; border: none; outline: none; }
QListWidget:focus { border: 1px solid #1a73e8; }
QScrollBar:vertical { background: #f1f3f4; width: 8px; }
QScrollBar::handle:vertical { background: #bdc1c6; min-height: 22px;
    border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class _MessageDelegate(QStyledItemDelegate):
    """Paint real artifact fields as dense mailbox rows; elide only the overview."""

    def sizeHint(self, option, index) -> QSize:
        width = (
            option.widget.viewport().width()
            if isinstance(option.widget, QListWidget)
            else option.rect.width()
        )
        return QSize(0, 46 if width >= 680 else 64)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        data = index.data(Qt.ItemDataRole.UserRole + 1)
        if data is None:
            return
        painter.save()
        rect = option.rect
        selected = option.state & QStyle.StateFlag.State_Selected
        unread = index.data(Qt.ItemDataRole.FontRole).bold()
        background = "#ffffff" if unread else "#f2f6fc"
        if option.state & QStyle.StateFlag.State_MouseOver:
            background = "#e8eef7"
        painter.fillRect(rect, QColor("#c2dbff" if selected else background))
        painter.setPen(QPen(QColor("#e5e9ef")))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        middle = rect.center().y()
        for name, offset in (("checkbox", 10), ("star", 36)):
            icon(name, color="#7a8189").paint(
                painter, QRect(rect.x() + offset, middle - 9, 18, 18)
            )
        left = rect.x() + 66
        font = QFont(option.font)
        font.setPixelSize(14)
        font.setWeight(QFont.Weight.DemiBold if unread else QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor("#202124"))
        wide = rect.width() >= 680
        baseline = middle + 5 if wide else rect.y() + 24
        sender_width = 155 if wide else max(1, rect.width() - 138)
        painter.drawText(
            left,
            baseline,
            painter.fontMetrics().elidedText(
                data[0], Qt.TextElideMode.ElideRight, sender_width
            ),
        )
        font.setPixelSize(12)
        painter.setFont(font)
        painter.drawText(rect.right() - 47, baseline, data[3])
        font.setPixelSize(14)
        painter.setFont(font)
        subject_left = left + 175 if wide else left
        subject_y = baseline if wide else rect.y() + 48
        available = max(1, rect.right() - subject_left - (65 if wide else 12))
        subject = painter.fontMetrics().elidedText(
            data[1], Qt.TextElideMode.ElideRight, available
        )
        painter.drawText(subject_left, subject_y, subject)
        used = painter.fontMetrics().horizontalAdvance(subject)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#5f6368"))
        if available - used > 35:
            painter.drawText(
                subject_left + used,
                subject_y,
                painter.fontMetrics().elidedText(
                    " — " + data[2], Qt.TextElideMode.ElideRight, available - used
                ),
            )
        painter.restore()


class _MailLayout(QStackedLayout):
    """Ignore inactive views and preferred editor heights in native HFW queries."""

    def minimumSize(self) -> QSize:
        current = self.currentWidget()
        return current.minimumSizeHint() if current else QSize(0, 0)

    def sizeHint(self) -> QSize:
        current = self.currentWidget()
        return current.sizeHint() if current else QSize(0, 0)

    def heightForWidth(self, width: int) -> int:
        current = self.currentWidget()
        if current is None:
            return 0
        layout = current.layout()
        return max(layout.minimumSize().height(), layout.minimumHeightForWidth(width))


class _MailViews(QWidget):
    """Keep the existing view API with an active-page native layout policy."""

    def __init__(self) -> None:
        super().__init__()
        self._pages = _MailLayout(self)
        self._pages.setContentsMargins(0, 0, 0, 0)
        self._pages.currentChanged.connect(lambda _: self.updateGeometry())

    def addWidget(self, widget: QWidget) -> int:
        return self._pages.addWidget(widget)

    def currentWidget(self) -> QWidget | None:
        return self._pages.currentWidget()

    def currentIndex(self) -> int:
        return self._pages.currentIndex()

    def setCurrentIndex(self, index: int) -> None:
        self._pages.setCurrentIndex(index)

    def minimumSizeHint(self) -> QSize:
        return self._pages.minimumSize()

    def sizeHint(self) -> QSize:
        return self._pages.sizeHint()

    def heightForWidth(self, width: int) -> int:
        return self._pages.heightForWidth(width)


class MailPreview(QFrame):
    message_opened = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("emailPreview")
        self.setStyleSheet(LIGHT_STYLE)
        palette = self.palette()
        for role, color in (
            (QPalette.ColorRole.Window, "#f6f8fc"),
            (QPalette.ColorRole.Base, "#ffffff"),
            (QPalette.ColorRole.Text, "#202124"),
            (QPalette.ColorRole.WindowText, "#202124"),
            (QPalette.ColorRole.Highlight, "#d3e3fd"),
            (QPalette.ColorRole.HighlightedText, "#202124"),
        ):
            palette.setColor(role, QColor(color))
        self.setPalette(palette)
        self.setMinimumWidth(0)
        self.draft: EmailDraftV2 | None = None
        self.selected_index: int | None = None
        self.read_messages: set[int] = set()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 4)
        outer.setSpacing(0)
        tabs = QFrame()
        tabs.setObjectName("browserTabs")
        tab_row = QHBoxLayout(tabs)
        tab_row.setContentsMargins(10, 4, 10, 0)
        tab = QFrame()
        tab.setObjectName("browserTab")
        tab_content = QHBoxLayout(tab)
        tab_content.setContentsMargins(10, 0, 4, 0)
        tab_content.setSpacing(6)
        tab_glyph = _text("")
        tab_glyph.setPixmap(icon("mail", color="#5f6368").pixmap(16, 16))
        tab_content.addWidget(tab_glyph)
        self.browser_tab = _text("Gmail — Навчальна пошта", "browserTabTitle")
        tab_content.addWidget(self.browser_tab)
        tab_content.addWidget(_tool("close", "Закрити навчальну вкладку", size=24))
        tab_row.addWidget(tab)
        tab_row.addWidget(_text("Навчальний перегляд", "browserNotice"), 1)
        outer.addWidget(tabs)
        address_row = QHBoxLayout()
        address_row.setContentsMargins(8, 2, 12, 2)
        address_row.setSpacing(2)
        for symbol, name in (
            ("arrow_left", "Назад у браузері"),
            ("arrow_right", "Уперед у браузері"),
            ("refresh", "Оновити сторінку"),
        ):
            address_row.addWidget(_tool(symbol, name, size=24))
        self.address = QLineEdit("https://mail.training.invalid/#inbox")
        self.address.setObjectName("browserAddress")
        self.address.setReadOnly(True)
        self.address.setAccessibleName(
            "Синтетична адреса поштового макета, без переходів"
        )
        self.address.setToolTip(
            "Лише візуальна адреса .invalid. Навігація та мережеві запити відсутні."
        )
        address_row.addWidget(self.address, 1)
        outer.addLayout(address_row)
        header = QHBoxLayout()
        header.setContentsMargins(12, 2, 12, 4)
        header.setSpacing(8)
        header.addWidget(_tool("menu", "Меню пошти"))
        header.addWidget(_text("M", "mailMark"))
        header.addWidget(_text("Gmail", "mailBrand"))
        self.search = QLineEdit()
        self.search.setObjectName("mailSearch")
        self.search.setPlaceholderText("Пошук у пошті")
        self.search.setAccessibleName("Пошук у синтетичних листах")
        self.search.setMinimumWidth(0)
        self.search.addAction(
            icon("search", color="#444746"), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        header.addWidget(self.search, 1)
        self.avatar = _text("Н")
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setFixedSize(28, 28)
        self.avatar.setStyleSheet("background: #c2e7ff; border-radius: 14px;")
        self.avatar.setToolTip("Навчальна скринька · " + MAILBOX_ADDRESS)
        header.addWidget(self.avatar)
        outer.addLayout(header)
        workspace = QHBoxLayout()
        workspace.setContentsMargins(8, 0, 8, 0)
        workspace.setSpacing(8)
        self.folders = QWidget()
        self.folders.setObjectName("mailFolders")
        folder_layout = QVBoxLayout(self.folders)
        folder_layout.setContentsMargins(0, 5, 0, 0)
        folder_layout.setSpacing(4)
        self.compose = QPushButton("Написати")
        self.compose.setIcon(icon("compose", color="#243947"))
        self.compose.setIconSize(QSize(22, 22))
        self.compose.setAccessibleName(
            "Написати лист · недоступно в навчальному макеті"
        )
        self.compose.setObjectName("compose")
        self.compose.setEnabled(False)
        self.compose.setToolTip("Навчальна скринька не надсилає листів.")
        folder_layout.addWidget(self.compose)
        self.inbox_button = QPushButton("Вхідні")
        self.inbox_button.setIcon(icon("inbox", color="#1f3761"))
        self.inbox_button.setIconSize(QSize(20, 20))
        self.inbox_button.setObjectName("inboxFolder")
        self.inbox_button.setAccessibleName("Повернутися до вхідних листів")
        self.inbox_button.clicked.connect(self.show_inbox)
        folder_layout.addWidget(self.inbox_button)
        self.folder_extras = QWidget()
        extra = QVBoxLayout(self.folder_extras)
        extra.setContentsMargins(0, 0, 0, 0)
        extra.setSpacing(0)
        for symbol, name in (
            ("star", "Із зірочкою"),
            ("clock", "Відкладені"),
            ("send", "Надіслані"),
            ("draft", "Чернетки"),
        ):
            folder = QPushButton(name)
            folder.setIcon(icon(symbol, color="#5f6368"))
            folder.setIconSize(QSize(20, 20))
            folder.setEnabled(False)
            folder.setToolTip("Лише навчальний макет; доступні «Вхідні».")
            extra.addWidget(folder)
        folder_layout.addWidget(self.folder_extras)
        folder_layout.addStretch()
        workspace.addWidget(self.folders)
        sheet = QFrame()
        sheet.setObjectName("mailSheet")
        sheet_layout = QVBoxLayout(sheet)
        sheet_layout.setContentsMargins(8, 0, 8, 4)
        sheet_layout.setSpacing(0)
        tools = QHBoxLayout()
        tools.setContentsMargins(0, 3, 0, 3)
        tools.setSpacing(6)
        self.inbox_tools = QWidget()
        inbox_tools = QHBoxLayout(self.inbox_tools)
        inbox_tools.setContentsMargins(0, 0, 0, 0)
        inbox_tools.setSpacing(6)
        for symbol, name in (
            ("checkbox", "Вибрати листи"),
            ("refresh", "Оновити пошту"),
            ("more", "Додаткові дії зі списком"),
        ):
            inbox_tools.addWidget(_tool(symbol, name))
        tools.addWidget(self.inbox_tools)
        self.reading_tools = QWidget()
        reading_tools = QHBoxLayout(self.reading_tools)
        reading_tools.setContentsMargins(0, 0, 0, 0)
        reading_tools.setSpacing(6)
        self.inbox_back = _tool("arrow_left", "До вхідних листів", enabled=True)
        self.inbox_back.clicked.connect(self.show_inbox)
        reading_tools.addWidget(self.inbox_back)
        for symbol, name in (
            ("archive", "Архів"),
            ("spam", "Позначити як спам"),
            ("trash", "Видалити"),
            ("mail", "Позначити непрочитаним"),
            ("more", "Додаткові дії"),
        ):
            reading_tools.addWidget(_tool(symbol, name))
        tools.addWidget(self.reading_tools)
        tools.addStretch()
        self.counter = _text("0 листів", "timestamp")
        tools.addWidget(self.counter)
        sheet_layout.addLayout(tools)
        self.views = _MailViews()
        inbox = QWidget()
        inbox_layout = QVBoxLayout(inbox)
        inbox_layout.setContentsMargins(0, 0, 0, 0)
        inbox_layout.setSpacing(0)
        category = QFrame()
        category.setObjectName("category")
        category_content = QHBoxLayout(category)
        category_content.setContentsMargins(14, 10, 14, 10)
        category_content.setSpacing(12)
        category_icon = _text("")
        category_icon.setPixmap(icon("inbox", color="#0b57d0").pixmap(20, 20))
        category_content.addWidget(category_icon)
        category_content.addWidget(_text("Основні", "categoryTitle"))
        category_content.addStretch()
        category.setMaximumWidth(240)
        inbox_layout.addWidget(category)
        self.messages = QListWidget()
        self.messages.setAccessibleName("Вхідні синтетичні листи: Enter відкриває лист")
        self.messages.setMinimumSize(0, 85)
        self.messages.setMouseTracking(True)
        self.messages.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.messages.setItemDelegate(_MessageDelegate(self.messages))
        self.messages.itemClicked.connect(self._activate)
        self.messages.itemActivated.connect(self._activate)
        inbox_layout.addWidget(self.messages, 1)
        self.views.addWidget(inbox)
        self.reading = QWidget()
        reading = QVBoxLayout(self.reading)
        reading.setContentsMargins(12, 0, 12, 0)
        reading.setSpacing(4)
        self.subject = self._plain("Тема вибраного листа", 38)
        self.subject.setObjectName("mailSubject")
        subject_row = QHBoxLayout()
        subject_row.addSpacing(46)
        subject_row.addWidget(self.subject)
        reading.addLayout(subject_row)
        sender_row = QHBoxLayout()
        sender_row.setSpacing(10)
        self.sender_avatar = _text("Н")
        self.sender_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sender_avatar.setFixedSize(36, 36)
        self.sender_avatar.setStyleSheet("background: #e8d5ff; border-radius: 18px;")
        sender_row.addWidget(self.sender_avatar, 0, Qt.AlignmentFlag.AlignTop)
        self.sender = self._plain("Відправник і адреса вибраного листа", 44)
        self.sender.setObjectName("mailSender")
        sender_details = QVBoxLayout()
        sender_details.setSpacing(0)
        sender_details.addWidget(self.sender)
        self.recipient = _text("кому: мені · " + MAILBOX_ADDRESS, "recipient")
        self.recipient.setWordWrap(True)
        sender_details.addWidget(self.recipient)
        sender_row.addLayout(sender_details, 1)
        self.timestamp = _text("", "timestamp")
        self.timestamp.setMaximumWidth(160)
        self.timestamp.setToolTip(
            "Синтетичний навчальний час, не фактична дата доставки."
        )
        self.timestamp.setContentsMargins(0, 4, 0, 0)
        sender_row.addWidget(self.timestamp, 0, Qt.AlignmentFlag.AlignTop)
        reading.addLayout(sender_row)
        self.body = MessageBody()
        body_row = QHBoxLayout()
        body_row.setSpacing(0)
        body_row.addSpacing(46)
        body_row.addWidget(self.body, 1)
        reading.addLayout(body_row, 1)
        self.resource = _text("", "resource")
        self.resource.setWordWrap(True)
        reading.addWidget(self.resource)
        self.reply_actions = QWidget()
        reply_row = QHBoxLayout(self.reply_actions)
        reply_row.setContentsMargins(46, 5, 0, 5)
        reply_row.setSpacing(8)
        self.reply = QPushButton("Відповісти")
        self.reply.setObjectName("reply")
        self.forward = QPushButton("Переслати")
        self.forward.setObjectName("mailForward")
        for button, name in ((self.reply, "reply"), (self.forward, "mail_forward")):
            button.setIcon(icon(name, color="#444746"))
            button.setIconSize(QSize(18, 18))
            button.setEnabled(False)
            button.setToolTip(
                "Відповіді та надсилання недоступні в навчальному макеті."
            )
            reply_row.addWidget(button)
        reply_row.addStretch()
        reading.addWidget(self.reply_actions)
        self.views.addWidget(self.reading)
        sheet_layout.addWidget(self.views, 1)
        workspace.addWidget(sheet, 1)
        outer.addLayout(workspace, 1)
        self.show_inbox()

    @staticmethod
    def _plain(name: str, height: int | None = None) -> QPlainTextEdit:
        field = QPlainTextEdit()
        field.setReadOnly(True)
        field.setTabChangesFocus(True)
        field.setAccessibleName(name)
        field.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        field.setMinimumSize(0, 0)
        field.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        if height is not None:
            field.setFixedHeight(height)
        return field

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        compact = self.width() < 850
        self.folders.setFixedWidth(48 if compact else 168)
        self.compose.setText("" if compact else "Написати")
        self.inbox_button.setText("" if compact else "Вхідні")
        self.folder_extras.setVisible(not compact)
        self.reply_actions.setVisible(not compact)
        self.messages.doItemsLayout()

    def heightForWidth(self, width: int) -> int:
        return self.layout().minimumHeightForWidth(width)

    def set_link(self, link) -> None:
        from cyberforge.web.contracts import email_digest

        self.link = (
            link
            if link is not None
            and self.draft is not None
            and (
                link.scenario_id == self.draft.scenario_id
                and link.scenario_version == self.draft.scenario_version
                and link.source_email_digest == email_digest(self.draft)
            )
            else None
        )
        if self.selected_index is not None:
            self.open_message(self.selected_index)

    def set_draft(self, draft: EmailDraftV2 | None) -> None:
        self.link = None
        self.draft = draft
        self.selected_index = None
        self.read_messages.clear()
        self.messages.clear()
        # Filtering must not run between clearing and rebuilding the row model.
        with QSignalBlocker(self.search):
            self.search.clear()
        for field in (self.subject, self.sender, self.body):
            field.clear()
        self.timestamp.clear()
        self.resource.clear()
        if draft is not None:
            for index, message in enumerate(
                [draft.slots.main, *draft.slots.background]
            ):
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, index)
                item.setData(
                    Qt.ItemDataRole.UserRole + 1,
                    (
                        message.sender_name,
                        message.subject,
                        message.body_text[:150].replace("\n", " "),
                        training_time(index),
                    ),
                )
                item.setText(f"{message.sender_name}\n{message.subject}")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setToolTip(message.sender_address)
                self.messages.addItem(item)
            self.messages.setCurrentRow(0)
        self.counter.setText(f"{self.messages.count()} листів")
        self.show_inbox()

    def _activate(self, item: QListWidgetItem) -> None:
        self.open_message(item.data(Qt.ItemDataRole.UserRole))

    def open_message(self, index: int) -> None:
        if self.draft is None or not 0 <= index < self.messages.count():
            return
        message = [self.draft.slots.main, *self.draft.slots.background][index]
        self.selected_index = index
        self.read_messages.add(index)
        item = self.messages.item(index)
        font = item.font()
        font.setBold(False)
        item.setFont(font)
        self.subject.setPlainText(message.subject)
        self.sender.setPlainText(f"{message.sender_name}\n{message.sender_address}")
        cursor = self.sender.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
        )
        style = cursor.charFormat()
        style.setFontWeight(QFont.Weight.DemiBold)
        style.setForeground(QColor("#202124"))
        cursor.mergeCharFormat(style)
        self.sender_avatar.setText(message.sender_name[:1].upper())
        self.timestamp.setText(training_time(index) + " · навчальний час")
        self.body.set_message(
            message,
            self.draft.slots.internal_resource_id if index == 0 else None,
            self.link if index == 0 else None,
        )
        self.resource.setText(
            "Навчальне посилання: "
            + (
                self.link.link_label + " · " + self.link.display_url + " · "
                if self.link
                else ""
            )
            + self.draft.slots.internal_resource_id
            + " · перехід вимкнено"
            if index == 0
            else "Фоновий синтетичний лист"
        )
        self.views.setCurrentIndex(1)
        self.inbox_tools.hide()
        self.reading_tools.show()
        self.inbox_back.setEnabled(True)
        self.address.setText(
            f"https://mail.training.invalid/#inbox/message-{index + 1}"
        )
        self.counter.setText(f"{index + 1} із {self.messages.count()}")
        self.message_opened.emit(index)

    def show_inbox(self) -> None:
        self.views.setCurrentIndex(0)
        self.inbox_tools.show()
        self.reading_tools.hide()
        self.inbox_back.setEnabled(False)
        self.address.setText("https://mail.training.invalid/#inbox")
        self.counter.setText(f"{self.messages.count()} листів")

    def _filter(self, query: str) -> None:
        if self.draft is None:
            return
        messages = [self.draft.slots.main, *self.draft.slots.background]
        for index, message in enumerate(messages):
            self.messages.item(index).setHidden(
                query.casefold().strip()
                not in " ".join(
                    (
                        message.sender_name,
                        message.sender_address,
                        message.subject,
                        message.body_text,
                    )
                ).casefold()
            )
        if query:
            self.show_inbox()
