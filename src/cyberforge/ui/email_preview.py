"""Native, isolated Gmail-inspired training mailbox. No web renderer or URLs."""

from PySide6.QtCore import QSignalBlocker, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cyberforge.agents.contracts import EmailDraftV2

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


def _tool(text: str, name: str, *, enabled: bool = False) -> QToolButton:
    result = QToolButton()
    result.setText(text)
    result.setAccessibleName(name)
    result.setToolTip(name if enabled else name + " · лише навчальний макет")
    result.setEnabled(enabled)
    result.setFixedSize(28, 28)
    return result


LIGHT_STYLE = """
QWidget { color: #202124; font-size: 13px; background: transparent; }
QFrame#emailPreview { background: #f6f8fc; border: 1px solid #c7cbd1;
    border-radius: 12px; }
QFrame#browserTabs { background: #dfe3eb; border-top-left-radius: 11px;
    border-top-right-radius: 11px; }
QLabel#browserTab { background: #f6f8fc; padding: 5px 14px; border-radius: 7px; }
QLabel#browserNotice { color: #5f6368; font-size: 11px; }
QLineEdit#browserAddress { background: #edf0f5; border: none; border-radius: 12px;
    padding: 4px 12px; color: #5f6368; font-size: 12px; }
QLineEdit#mailSearch { background: #eaf1fb; border: none; border-radius: 16px;
    padding: 8px 14px; color: #202124; }
QLineEdit:focus { border: 1px solid #1a73e8; }
QLabel#mailBrand { font-size: 22px; color: #5f6368; }
QLabel#mailMark { color: #d93025; font-size: 25px; font-weight: 700; }
QFrame#mailSheet { background: #ffffff; border-radius: 12px; }
QPushButton { color: #202124; background: transparent; border: none;
    border-radius: 15px; padding: 6px 12px; text-align: left; }
QPushButton:hover, QToolButton:hover { background: #e4e9f1; }
QPushButton:focus, QToolButton:focus { border: 1px solid #1a73e8; }
QPushButton#compose { background: #c2e7ff; border-radius: 14px; padding: 12px; }
QPushButton#inboxFolder { background: #d3e3fd; font-weight: 600; }
QPushButton#reply { border: 1px solid #dadce0; border-radius: 14px;
    padding: 4px 12px; }
QPushButton:disabled { color: #69717c; }
QToolButton { color: #5f6368; background: transparent; border: none;
    border-radius: 14px; font-size: 17px; }
QToolButton:disabled { color: #7c828b; }
QLabel#category { color: #0b57d0; border-bottom: 3px solid #0b57d0;
    padding: 7px 12px; font-weight: 600; }
QLabel#recipient, QLabel#timestamp, QLabel#resource {
    color: #5f6368; font-size: 11px; }
QPlainTextEdit { background: #ffffff; color: #202124; border: none;
    selection-background-color: #d3e3fd; selection-color: #202124; }
QPlainTextEdit#mailSubject { font-size: 20px; }
QPlainTextEdit#mailSender { font-size: 12px; }
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
        return QSize(0, 60)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        data = index.data(Qt.ItemDataRole.UserRole + 1)
        if data is None:
            return
        painter.save()
        rect = option.rect
        selected = option.state & QStyle.StateFlag.State_Selected
        unread = index.data(Qt.ItemDataRole.FontRole).bold()
        painter.fillRect(
            rect, QColor("#d3e3fd" if selected else "#ffffff" if unread else "#f2f6fc")
        )
        painter.setPen(QPen(QColor("#e5e9ef")))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        painter.setPen(QColor("#70757a"))
        painter.drawRoundedRect(rect.x() + 12, rect.y() + 22, 13, 13, 2, 2)
        painter.drawText(rect.x() + 36, rect.y() + 34, "☆")
        left = rect.x() + 62
        width = max(1, rect.width() - 125)
        font = QFont(option.font)
        font.setBold(unread)
        painter.setFont(font)
        painter.setPen(QColor("#202124"))
        painter.drawText(
            left,
            rect.y() + 22,
            painter.fontMetrics().elidedText(
                data[0], Qt.TextElideMode.ElideRight, width
            ),
        )
        painter.drawText(rect.right() - 49, rect.y() + 22, data[3])
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#5f6368"))
        painter.drawText(
            left,
            rect.y() + 44,
            painter.fontMetrics().elidedText(
                data[1] + " — " + data[2],
                Qt.TextElideMode.ElideRight,
                max(1, rect.width() - 78),
            ),
        )
        painter.restore()


class _MailViews(QStackedWidget):
    """Use the active view's minimum layout height, including wrapped labels."""

    def __init__(self) -> None:
        super().__init__()
        self.currentChanged.connect(lambda _: self.updateGeometry())

    def minimumSizeHint(self) -> QSize:
        current = self.currentWidget()
        return current.minimumSizeHint() if current else super().minimumSizeHint()

    def sizeHint(self) -> QSize:
        current = self.currentWidget()
        return current.sizeHint() if current else super().sizeHint()

    def heightForWidth(self, width: int) -> int:
        current = self.currentWidget()
        if current is None:
            return super().heightForWidth(width)
        layout = current.layout()
        return max(layout.minimumSize().height(), layout.minimumHeightForWidth(width))


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
        outer.setContentsMargins(0, 0, 0, 8)
        outer.setSpacing(0)
        tabs = QFrame()
        tabs.setObjectName("browserTabs")
        tab_row = QHBoxLayout(tabs)
        tab_row.setContentsMargins(10, 4, 10, 0)
        self.browser_tab = _text("✉  Gmail — Навчальна пошта  ×", "browserTab")
        tab_row.addWidget(self.browser_tab)
        tab_row.addWidget(_text("Навчальний перегляд", "browserNotice"), 1)
        outer.addWidget(tabs)
        address_row = QHBoxLayout()
        address_row.setContentsMargins(8, 2, 12, 2)
        address_row.setSpacing(2)
        for symbol, name in (
            ("←", "Назад у браузері"),
            ("→", "Уперед у браузері"),
            ("↻", "Оновити сторінку"),
        ):
            address_row.addWidget(_tool(symbol, name))
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
        header.addWidget(_tool("☰", "Меню пошти"))
        header.addWidget(_text("M", "mailMark"))
        header.addWidget(_text("Gmail", "mailBrand"))
        self.search = QLineEdit()
        self.search.setObjectName("mailSearch")
        self.search.setPlaceholderText("Пошук у пошті")
        self.search.setAccessibleName("Пошук у синтетичних листах")
        self.search.setMinimumWidth(0)
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
        folder_layout = QVBoxLayout(self.folders)
        folder_layout.setContentsMargins(0, 5, 0, 0)
        folder_layout.setSpacing(3)
        self.compose = QPushButton("✎  Написати")
        self.compose.setObjectName("compose")
        self.compose.setEnabled(False)
        self.compose.setToolTip("Навчальна скринька не надсилає листів.")
        folder_layout.addWidget(self.compose)
        self.inbox_button = QPushButton("▣  Вхідні")
        self.inbox_button.setObjectName("inboxFolder")
        self.inbox_button.setAccessibleName("Повернутися до вхідних листів")
        self.inbox_button.clicked.connect(self.show_inbox)
        folder_layout.addWidget(self.inbox_button)
        self.folder_extras = QWidget()
        extra = QVBoxLayout(self.folder_extras)
        extra.setContentsMargins(12, 4, 0, 0)
        for name in ("☆  Із зірочкою", "◷  Відкладені", "➤  Надіслані", "▤  Чернетки"):
            extra.addWidget(_text(name))
        folder_layout.addWidget(self.folder_extras)
        folder_layout.addStretch()
        workspace.addWidget(self.folders)
        sheet = QFrame()
        sheet.setObjectName("mailSheet")
        sheet_layout = QVBoxLayout(sheet)
        sheet_layout.setContentsMargins(8, 0, 8, 4)
        sheet_layout.setSpacing(0)
        tools = QHBoxLayout()
        self.inbox_back = _tool("←", "До вхідних листів", enabled=True)
        self.inbox_back.clicked.connect(self.show_inbox)
        tools.addWidget(self.inbox_back)
        for symbol, name in (
            ("▣", "Архів"),
            ("!", "Позначити як спам"),
            ("⌫", "Видалити"),
            ("⋮", "Додаткові дії"),
        ):
            tools.addWidget(_tool(symbol, name))
        tools.addStretch()
        self.counter = _text("0 листів", "timestamp")
        tools.addWidget(self.counter)
        sheet_layout.addLayout(tools)
        self.views = _MailViews()
        inbox = QWidget()
        inbox_layout = QVBoxLayout(inbox)
        inbox_layout.setContentsMargins(0, 0, 0, 0)
        inbox_layout.setSpacing(0)
        inbox_layout.addWidget(_text("▣  Основні", "category"))
        self.messages = QListWidget()
        self.messages.setAccessibleName("Вхідні синтетичні листи: Enter відкриває лист")
        self.messages.setMinimumSize(0, 85)
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
        reading.setSpacing(3)
        self.subject = self._plain("Тема вибраного листа", 36)
        self.subject.setObjectName("mailSubject")
        reading.addWidget(self.subject)
        sender_row = QHBoxLayout()
        sender_row.setSpacing(8)
        self.sender_avatar = _text("Н")
        self.sender_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sender_avatar.setFixedSize(30, 30)
        self.sender_avatar.setStyleSheet("background: #e8d5ff; border-radius: 15px;")
        sender_row.addWidget(self.sender_avatar)
        self.sender = self._plain("Відправник і адреса вибраного листа", 42)
        self.sender.setObjectName("mailSender")
        sender_row.addWidget(self.sender, 1)
        self.timestamp = _text("", "timestamp")
        self.timestamp.setToolTip(
            "Синтетичний навчальний час, не фактична дата доставки."
        )
        sender_row.addWidget(self.timestamp)
        reading.addLayout(sender_row)
        self.recipient = _text("кому: мені · " + MAILBOX_ADDRESS, "recipient")
        reading.addWidget(self.recipient)
        self.body = self._plain("Текст вибраного листа")
        self.body.setMinimumHeight(65)
        reading.addWidget(self.body, 1)
        self.resource = _text("", "resource")
        self.resource.setWordWrap(True)
        reading.addWidget(self.resource)
        self.reply = QPushButton("↶  Відповісти       ➜  Переслати")
        self.reply.setObjectName("reply")
        self.reply.setEnabled(False)
        self.reply.setToolTip(
            "Відповіді та надсилання недоступні в навчальному макеті."
        )
        reading.addWidget(self.reply, 0, Qt.AlignmentFlag.AlignLeft)
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
        if height is not None:
            field.setFixedHeight(height)
        return field

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        compact = self.width() < 850
        self.folders.setFixedWidth(45 if compact else 160)
        self.compose.setText("✎" if compact else "✎  Написати")
        self.inbox_button.setText("▣" if compact else "▣  Вхідні")
        self.folder_extras.setVisible(not compact)
        self.reply.setVisible(not compact)

    def heightForWidth(self, width: int) -> int:
        return self.layout().minimumHeightForWidth(width)

    def set_draft(self, draft: EmailDraftV2 | None) -> None:
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
        self.sender_avatar.setText(message.sender_name[:1].upper())
        self.timestamp.setText(training_time(index) + " · навчальний час")
        self.body.setPlainText(message.body_text)
        self.resource.setText(
            "Навчальне посилання: "
            + self.draft.slots.internal_resource_id
            + " · перехід вимкнено"
            if index == 0
            else "Фоновий синтетичний лист"
        )
        self.views.setCurrentIndex(1)
        self.inbox_back.setEnabled(True)
        self.address.setText(
            f"https://mail.training.invalid/#inbox/message-{index + 1}"
        )
        self.counter.setText(f"{index + 1} із {self.messages.count()}")
        self.message_opened.emit(index)

    def show_inbox(self) -> None:
        self.views.setCurrentIndex(0)
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
