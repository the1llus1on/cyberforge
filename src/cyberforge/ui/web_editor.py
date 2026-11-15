"""Typed visual composition editor; changes are candidates until explicit Save."""

import json
from uuid import uuid4

from pydantic import ValidationError
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from cyberforge.domain.accounts import ApplicationError
from cyberforge.ui.pages import label
from cyberforge.web.contracts import (
    ACTIONS,
    COMPONENT_LABELS,
    REGISTRY,
    THEMES,
    WebPageV2,
)
from cyberforge.web.presets import default_component


def combo(values, current=None):
    control = QComboBox()
    for key, title in values.items():
        control.addItem(title, key)
    control.setMinimumContentsLength(10)
    control.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    if current is not None:
        control.setCurrentIndex(control.findData(current))
    return control


class WebEditorDialog(QDialog):
    def __init__(self, page: WebPageV2, apply, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редагувати сайт")
        self.resize(930, 640)
        self.data = page.model_dump(mode="json")
        self._apply = apply
        self.selected = -1
        self.fields = {}
        self.tables = {}
        layout = QVBoxLayout(self)
        layout.addWidget(
            label("Застосуйте композицію до preview. Запис у БД — лише «Зберегти».")
        )
        settings = QFormLayout()
        self.title = QLineEdit(page.tab_title)
        self.address = QLineEdit(page.display_url)
        self.theme = combo(THEMES, page.theme)
        self.mode = combo({"light": "Світла", "dark": "Темна"}, page.color_mode)
        self.page_layout = combo(
            {"standard": "Звичайна", "wide": "Широка", "centered": "Центрована"},
            page.layout,
        )
        settings.addRow("Назва вкладки", self.title)
        settings.addRow("Навчальна адреса (лише текст)", self.address)
        themes = QHBoxLayout()
        for control in (self.theme, self.mode, self.page_layout):
            themes.addWidget(control)
        settings.addRow("Оформлення", themes)
        layout.addLayout(settings)
        row = QHBoxLayout()
        left = QVBoxLayout()
        self.components = QListWidget()
        self.components.setMaximumWidth(250)
        self.components.currentRowChanged.connect(self.select)
        left.addWidget(self.components, 1)
        self.kind = combo(COMPONENT_LABELS)
        left.addWidget(self.kind)
        self.add_button = QPushButton("Додати компонент")
        self.add_button.clicked.connect(self.add_component)
        left.addWidget(self.add_button)
        self.remove_button = QPushButton("Видалити")
        self.remove_button.clicked.connect(self.remove_component)
        left.addWidget(self.remove_button)
        arrows = QHBoxLayout()
        self.up_button, self.down_button = QPushButton("↑ Вище"), QPushButton("↓ Нижче")
        self.up_button.clicked.connect(lambda: self.move_component(-1))
        self.down_button.clicked.connect(lambda: self.move_component(1))
        arrows.addWidget(self.up_button)
        arrows.addWidget(self.down_button)
        left.addLayout(arrows)
        row.addLayout(left)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.properties = QWidget()
        self.form = QFormLayout(self.properties)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        scroll.setWidget(self.properties)
        row.addWidget(scroll, 1)
        layout.addLayout(row, 1)
        self.error = label("")
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).setText(
            "Застосувати до preview"
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.apply
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "Скасувати правки"
        )
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.refresh(0)

    def refresh(self, row):
        self.components.blockSignals(True)
        self.components.clear()
        for c in self.data["components"]:
            self.components.addItem(f"{COMPONENT_LABELS[c['type']]} · {c['id']}")
        self.components.blockSignals(False)
        self.selected = -1
        self.components.setCurrentRow(
            max(0, min(row, len(self.data["components"]) - 1))
        )

    def capture(self):
        if self.selected < 0:
            return
        data = self.data["components"][self.selected]
        for name, control in self.fields.items():
            data[name] = (
                control.currentData()
                if isinstance(control, QComboBox)
                else (
                    control.toPlainText()
                    if isinstance(control, QPlainTextEdit)
                    else control.text()
                )
            )
        for name, table in self.tables.items():
            keys = {
                "items": ("title", "text"),
                "fields": ("id", "label", "kind"),
                "actions": ("id", "label"),
            }[name]
            data[name] = [
                {
                    key: (
                        table.cellWidget(i, j).currentData()
                        if isinstance(table.cellWidget(i, j), QComboBox)
                        else table.cellWidget(i, j).text()
                    )
                    for j, key in enumerate(keys)
                }
                for i in range(table.rowCount())
            ]

    def select(self, row):
        self.capture()
        self.selected = row
        while self.form.rowCount():
            self.form.removeRow(0)
        self.fields, self.tables = {}, {}
        if row < 0:
            return
        c = self.data["components"][row]
        self.form.addRow(label(f"ID: {c['id']} · {COMPONENT_LABELS[c['type']]}"))
        self.fields["variant"] = combo(
            {"standard": "Звичайний", "compact": "Компактний", "emphasis": "Виділений"},
            c["variant"],
        )
        self.form.addRow("Варіант компонента", self.fields["variant"])
        for name, title in (("title", "Заголовок"), ("text", "Текст")):
            if name in c:
                control = (
                    QPlainTextEdit(c[name]) if name == "text" else QLineEdit(c[name])
                )
                if name == "text":
                    control.setMinimumHeight(100)
                control.setAccessibleName(title)
                self.fields[name] = control
                self.form.addRow(title, control)
        for name in ("items", "fields", "actions"):
            if name in REGISTRY[c["type"]].model_fields:
                table = QTableWidget()
                self.tables[name] = table
                self.build_table(name, c.get(name, []))
                self.form.addRow(
                    {
                        "items": "Картки",
                        "fields": "Поля форми",
                        "actions": "Навчальні дії",
                    }[name],
                    table,
                )
                buttons = QHBoxLayout()
                add, remove = QPushButton("+ Запис"), QPushButton("− Запис")
                add.clicked.connect(lambda checked=False, n=name: self.add_entry(n))
                remove.clicked.connect(
                    lambda checked=False, n=name: self.remove_entry(n)
                )
                buttons.addWidget(add)
                buttons.addWidget(remove)
                self.form.addRow(buttons)

    def build_table(self, name, entries):
        table = self.tables[name]
        keys = {
            "items": ("title", "text"),
            "fields": ("id", "label", "kind"),
            "actions": ("id", "label"),
        }[name]
        table.setColumnCount(len(keys))
        table.setHorizontalHeaderLabels(
            [
                {
                    "id": "Дія / поле",
                    "label": "Підпис",
                    "kind": "Тип",
                    "title": "Назва",
                    "text": "Текст",
                }[k]
                for k in keys
            ]
        )
        table.setRowCount(len(entries))
        table.setMinimumHeight(100)
        table.horizontalHeader().setStretchLastSection(True)
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        for i, entry in enumerate(entries):
            for j, key in enumerate(keys):
                if key == "id" and name == "actions":
                    control = combo(ACTIONS, entry[key])
                elif key == "id" and name == "fields":
                    control = combo(
                        {
                            "synthetic_login": "Логін (демо)",
                            "synthetic_code": "Код (демо)",
                            "synthetic_confirmation": "Підтвердження",
                        },
                        entry[key],
                    )
                elif key == "kind":
                    control = combo(
                        {
                            "synthetic_text": "Синтетичний текст",
                            "confirmation": "Підтвердження",
                        },
                        entry[key],
                    )
                else:
                    control = QLineEdit(entry[key])
                table.setCellWidget(i, j, control)

    def add_entry(self, name):
        self.capture()
        entries = self.data["components"][self.selected].setdefault(name, [])
        limit = {"items": 6, "fields": 3, "actions": 5}[name]
        if len(entries) >= limit:
            self.error.setText("Досягнуто ліміту записів.")
            return
        default = {
            "items": {"title": "Нова картка", "text": "Навчальний текст"},
            "fields": {
                "id": "synthetic_code",
                "label": "Код (демо)",
                "kind": "synthetic_text",
            },
            "actions": {"id": "report", "label": "Повідомити"},
        }[name]
        entries.append(default)
        self.build_table(name, entries)

    def remove_entry(self, name):
        self.capture()
        entries = self.data["components"][self.selected][name]
        index = self.tables[name].currentRow()
        if entries:
            entries.pop(index if index >= 0 else -1)
            self.build_table(name, entries)

    def validated(self):
        self.capture()
        return WebPageV2.model_validate_json(
            json.dumps(
                self.data
                | dict(
                    tab_title=self.title.text(),
                    display_url=self.address.text(),
                    theme=self.theme.currentData(),
                    color_mode=self.mode.currentData(),
                    layout=self.page_layout.currentData(),
                )
            )
        )

    def structural(self, change, row):
        self.capture()
        previous = json.loads(json.dumps(self.data))
        change()
        try:
            WebPageV2.model_validate_json(json.dumps(self.data))
        except (ValidationError, ValueError):
            self.data = previous
            self.error.setText(
                "Зміну відхилено: перевірте порядок, кількість, поля й дії."
            )
        else:
            self.error.clear()
        self.refresh(row)

    def add_component(self):
        kind = self.kind.currentData()
        index = 0 if kind == "header" else len(self.data["components"])
        if kind != "header" and self.data["components"][-1]["type"] == "footer":
            index -= 1
        if kind == "footer":
            index = len(self.data["components"])
        self.structural(
            lambda: self.data["components"].insert(
                index, default_component(kind, "c_" + uuid4().hex[:12])
            ),
            index,
        )

    def remove_component(self):
        index = self.selected
        if index >= 0:
            self.structural(lambda: self.data["components"].pop(index), index)

    def move_component(self, direction):
        index, target = self.selected, self.selected + direction
        if index < 0 or not 0 <= target < len(self.data["components"]):
            return

        def move():
            c = self.data["components"]
            c[index], c[target] = c[target], c[index]

        self.structural(move, target)

    def apply(self):
        try:
            self._apply(self.validated())
        except (ValidationError, ValueError, ApplicationError):
            self.error.setText(
                "Правки відхилено: перевірте непорожні тексти, HTTPS адресу, "
                "кількість, порядок та дозволені властивості компонентів. "
                "Сценарій і лист мають залишатися актуальними."
            )
            return
        self.accept()

    def clear_sources(self):
        self.data.clear()
        self.selected = -1
        self.components.clear()
        self.title.clear()
        self.address.clear()
        while self.form.rowCount():
            self.form.removeRow(0)
        self.fields, self.tables = {}, {}
