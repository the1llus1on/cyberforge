"""Administrator forms backed exclusively by authorized application services."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.accounts import AccountService
from cyberforge.domain.accounts import ApplicationError, Role
from cyberforge.groups.service import GroupService
from cyberforge.ui.pages import label


class EditableList(QListWidget):
    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        # Keep the current edit identity and check states, only drop row highlight.
        self.clearSelection()

    def mousePressEvent(self, event) -> None:
        if not self.indexAt(event.position().toPoint()).isValid():
            self.setCurrentRow(-1)
            self.clearSelection()
        super().mousePressEvent(event)


class RoleChoice(QWidget):
    """Three explicit choices; no popup or implicit persistence."""

    def __init__(self) -> None:
        super().__init__()
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for role in (Role.LEARNER, Role.INSTRUCTOR, Role.ADMINISTRATOR):
            control = QRadioButton(role.label)
            control.setAccessibleName("Роль: " + role.label)
            self.group.addButton(control)
            self.buttons[role] = control
            layout.addWidget(control)
        self.set_role(Role.LEARNER)

    def selected_role(self) -> Role:
        return next(
            role for role, control in self.buttons.items() if control.isChecked()
        )

    def set_role(self, role: Role) -> None:
        self.buttons[Role(role)].setChecked(True)


class MembershipPicker(QListWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setObjectName("membershipPicker")


class AdminPage(QWidget):
    def heightForWidth(self, width: int) -> int:
        # Inner forms scroll; preferred form heights must not push actions below
        # the outer viewport. Keep width-dependent header/message wrapping.
        layout = self.layout()
        return layout.minimumHeightForWidth(width) if layout is not None else -1

    def __init__(
        self,
        accounts: AccountService,
        groups: GroupService,
        get_token: Callable[[], str | None],
        on_change: Callable[[], None],
    ) -> None:
        super().__init__()
        self.accounts, self.groups = accounts, groups
        self.get_token, self.on_change = get_token, on_change
        self.filters = []
        self.user_id: int | None = None
        self.group_id: int | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        self.title = label("Адміністрування", "title")
        layout.addWidget(self.title)
        self.message = label("")
        layout.addWidget(self.message)
        tabs = QTabWidget()
        self.tabs = tabs
        layout.addWidget(tabs)
        users_page, groups_page = QWidget(), QWidget()
        tabs.addTab(users_page, "Користувачі")
        tabs.addTab(groups_page, "Навчальні групи")
        users_outer = QVBoxLayout(users_page)
        users_layout = self._scroll_form(users_outer)
        self.users = EditableList()
        self.users.setMinimumHeight(100)
        self.users.setMaximumHeight(220)
        self.users.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.users.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.users.currentItemChanged.connect(self.select_user)
        self._filter(users_layout, self.users, "Пошук користувачів")
        users_layout.addWidget(self.users)
        form = QFormLayout()
        self.username, self.display_name = QLineEdit(), QLineEdit()
        self.role = RoleChoice()
        self.active = QCheckBox("Обліковий запис активний")
        self.active.setChecked(True)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setMaxLength(1024)
        for title, field in (
            ("Логін", self.username),
            ("Ім’я", self.display_name),
            ("Роль", self.role),
            ("Стан", self.active),
            ("Новий пароль (12–1024 символів)", self.password),
        ):
            form.addRow(title, field)
        users_layout.addLayout(form)
        self._buttons(
            users_outer,
            (
                ("Новий запис", self.new_user),
                ("Зберегти користувача", self.save_user),
                ("Скинути пароль", self.reset_password),
                ("Видалити користувача", self.delete_user),
            ),
        )
        users_layout.addWidget(
            label(
                "Зміна ролі прибирає членство у групах. Зміна ролі, стану "
                "або пароля завершує попередні сесії. Останнього "
                "адміністратора вимкнути не можна."
            )
        )
        groups_outer = QVBoxLayout(groups_page)
        groups_layout = self._scroll_form(groups_outer)
        self.group_list = EditableList()
        self.group_list.currentItemChanged.connect(self.select_group)
        self._filter(groups_layout, self.group_list, "Пошук груп")
        groups_layout.addWidget(self.group_list)
        group_form = QFormLayout()
        self.group_name, self.description = QLineEdit(), QLineEdit()
        group_form.addRow("Назва групи", self.group_name)
        group_form.addRow("Опис", self.description)
        groups_layout.addLayout(group_form)
        row = QHBoxLayout()
        self.instructors, self.learners = MembershipPicker(), MembershipPicker()
        for title, widget in (("Викладачі", self.instructors), ("Учні", self.learners)):
            column = QVBoxLayout()
            column.addWidget(label(title))
            self._filter(column, widget, "Пошук: " + title.lower())
            column.addWidget(widget)
            row.addLayout(column)
        groups_layout.addLayout(row)
        self._buttons(
            groups_outer,
            (
                ("Нова група", self.new_group),
                ("Зберегти групу", self.save_group),
                ("Видалити групу", self.delete_group),
            ),
        )

    @staticmethod
    def _scroll_form(outer):
        content = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        return QVBoxLayout(content)

    def _buttons(self, layout, entries) -> None:
        row = QGridLayout()
        for index, (text, callback) in enumerate(entries):
            control = QPushButton(text)
            control.clicked.connect(
                lambda checked=False, action=callback: self.perform(action)
            )
            control.setObjectName("adminAction")
            row.addWidget(control, index // 2, index % 2)
        layout.addLayout(row)

    def perform(self, action) -> None:
        try:
            result = action()
        except ApplicationError as error:
            self.message.setText(str(error))
        else:
            if result is False or action in (self.new_user, self.new_group):
                self.message.clear()
            else:
                self.message.setText("Зміни збережено.")
        finally:
            self.password.clear()
            self.on_change()

    def clear(self, *, reset_filters: bool = True) -> None:
        if reset_filters:
            for _, field in self.filters:
                field.clear()
        self.users.clear()
        self.group_list.clear()
        self.instructors.clear()
        self.learners.clear()
        self.new_user()
        self.new_group()
        self.message.clear()

    def refresh(self) -> None:
        self.clear(reset_filters=False)
        token = self.get_token()
        users = self.accounts.list_users(token)
        for user in users:
            item = QListWidgetItem(
                f"{user.display_name} ({user.username}) — {user.role.label} · "
                f"{'Активний' if user.active else 'Вимкнений'}"
            )
            item.setToolTip(item.text())
            item.setData(Qt.ItemDataRole.UserRole, user)
            self.users.addItem(item)
            if user.role in (Role.INSTRUCTOR, Role.LEARNER):
                member = QListWidgetItem(
                    f"{user.display_name} ({user.username})"
                    + (" — Неактивний" if not user.active else "")
                )
                member.setData(Qt.ItemDataRole.UserRole + 1, user.active)
                member.setData(Qt.ItemDataRole.UserRole, user.id)
                member.setFlags(
                    (member.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    & ~Qt.ItemFlag.ItemIsSelectable
                )
                member.setCheckState(Qt.CheckState.Unchecked)
                if not user.active:
                    member.setFlags(member.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                (
                    self.instructors if user.role == Role.INSTRUCTOR else self.learners
                ).addItem(member)
        for group in self.groups.list_groups(token):
            item = QListWidgetItem(group.name)
            item.setData(Qt.ItemDataRole.UserRole, group)
            self.group_list.addItem(item)

        for widget, field in self.filters:
            self._apply_filter(widget, field.text())

    def new_user(self) -> None:
        self.users.setCurrentRow(-1)
        self.users.clearSelection()
        self.user_id = None
        self.username.clear()
        self.display_name.clear()
        self.password.clear()
        self.active.setChecked(True)
        self.role.set_role(Role.LEARNER)

    def select_user(self, current, previous=None) -> None:
        if current is None:
            self.new_user()
            return
        user = current.data(Qt.ItemDataRole.UserRole)
        self.user_id = user.id
        self.username.setText(user.username)
        self.display_name.setText(user.display_name)
        self.role.set_role(user.role)
        self.active.setChecked(user.active)
        self.password.clear()

    def save_user(self) -> None:
        token = self.get_token()
        if self.user_id is None:
            self.accounts.create_user(
                token,
                self.username.text(),
                self.display_name.text(),
                self.role.selected_role(),
                self.password.text(),
                active=self.active.isChecked(),
            )
        else:
            self.accounts.update_user(
                token,
                self.user_id,
                self.display_name.text(),
                self.role.selected_role(),
                self.active.isChecked(),
                username=self.username.text(),
            )
        self.refresh()

    def reset_password(self) -> None:
        if self.user_id is None:
            raise ApplicationError("Виберіть користувача.")
        self.accounts.reset_password(
            self.get_token(), self.user_id, self.password.text()
        )
        self.refresh()

    def new_group(self) -> None:
        self.group_list.setCurrentRow(-1)
        self.group_list.clearSelection()
        self.group_id = None
        self.group_name.clear()
        self.description.clear()
        for widget in (self.instructors, self.learners):
            for i in range(widget.count()):
                item = widget.item(i)
                item.setCheckState(Qt.CheckState.Unchecked)
                if not item.data(Qt.ItemDataRole.UserRole + 1):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

    def select_group(self, current, previous=None) -> None:
        if current is None:
            self.new_group()
            return
        group = current.data(Qt.ItemDataRole.UserRole)
        self.group_id = group.id
        self.group_name.setText(group.name)
        self.description.setText(group.description)
        for widget, identifiers in (
            (self.instructors, group.instructors),
            (self.learners, group.learners),
        ):
            for i in range(widget.count()):
                item = widget.item(i)
                existing = item.data(Qt.ItemDataRole.UserRole) in identifiers
                flags = item.flags() & ~Qt.ItemFlag.ItemIsEnabled
                if existing or item.data(Qt.ItemDataRole.UserRole + 1):
                    flags |= Qt.ItemFlag.ItemIsEnabled
                item.setFlags(flags)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if item.data(Qt.ItemDataRole.UserRole) in identifiers
                    else Qt.CheckState.Unchecked
                )

    def save_group(self) -> None:
        group = self.groups.save_group(
            self.get_token(),
            self.group_name.text(),
            self.description.text(),
            self.group_id,
            instructors=self._checked(self.instructors),
            learners=self._checked(self.learners),
        )
        self.refresh()
        for i in range(self.group_list.count()):
            if self.group_list.item(i).data(Qt.ItemDataRole.UserRole).id == group.id:
                self.group_list.setCurrentRow(i)

    def save_members(self) -> None:
        self.save_group()

    @staticmethod
    def _checked(widget) -> tuple[int, ...]:
        return tuple(
            widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(widget.count())
            if widget.item(i).checkState() == Qt.CheckState.Checked
        )

    def _filter(self, layout, widget, placeholder) -> None:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setAccessibleName(placeholder)
        self.filters.append((widget, field))
        field.textChanged.connect(lambda text: self._apply_filter(widget, text))
        layout.addWidget(field)

    @staticmethod
    def _apply_filter(widget, text) -> None:
        for i in range(widget.count()):
            item = widget.item(i)
            item.setHidden(text.casefold() not in item.text().casefold())

    def delete_user(self) -> bool:
        from PySide6.QtWidgets import QMessageBox

        if self.user_id is None:
            raise ApplicationError("Виберіть користувача.")
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Видалити користувача?")
        dialog.setText("Обліковий запис і членство буде видалено. Продовжити?")
        accept = dialog.addButton("Видалити", QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton("Скасувати", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() == accept:
            self.accounts.delete_user(self.get_token(), self.user_id)
            self.refresh()
            return True
        return False

    def delete_group(self) -> bool:
        from PySide6.QtWidgets import QMessageBox

        if self.group_id is None:
            raise ApplicationError("Виберіть групу.")
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Видалити групу?")
        dialog.setText("Групу та її членство буде видалено. Продовжити?")
        delete_button = dialog.addButton("Видалити", QMessageBox.ButtonRole.AcceptRole)
        cancel_button = dialog.addButton("Скасувати", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        if dialog.clickedButton() == delete_button:
            self.groups.delete_group(self.get_token(), self.group_id)
            self.refresh()
            return True
        return False
