"""First-run setup and explicit, confirmed private-profile recovery."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.accounts import AccountService
from cyberforge.application.data_recovery import DataRecoveryService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.ui.pages import label


class BootstrapDialog(QDialog):
    def __init__(self, accounts: AccountService) -> None:
        super().__init__()
        self.accounts = accounts
        self.setWindowTitle("Початкове налаштування CyberForge")
        layout = QVBoxLayout(self)
        layout.addWidget(label("Створіть першого адміністратора.", "heading"))
        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setMaxLength(80)
        self.name = QLineEdit()
        self.name.setMaxLength(160)
        self.password = QLineEdit()
        self.confirmation = QLineEdit()
        for field in (self.password, self.confirmation):
            field.setMaxLength(1024)
            field.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Логін", self.username)
        form.addRow("Ім’я", self.name)
        form.addRow("Пароль (12–1024 символів)", self.password)
        form.addRow("Повторіть пароль", self.confirmation)
        layout.addLayout(form)
        self.message = label("")
        layout.addWidget(self.message)
        buttons = QDialogButtonBox()
        submit = buttons.addButton(
            "Створити адміністратора", QDialogButtonBox.AcceptRole
        )
        cancel = buttons.addButton("Скасувати", QDialogButtonBox.RejectRole)
        submit.clicked.connect(self.create_account)
        cancel.clicked.connect(self.reject)
        layout.addWidget(buttons)
        self.finished.connect(lambda _: self.clear_passwords())

    def clear_passwords(self) -> None:
        self.password.clear()
        self.confirmation.clear()

    def create_account(self) -> None:
        try:
            if self.password.text() != self.confirmation.text():
                raise ApplicationError("Паролі не збігаються.")
            self.accounts.bootstrap(
                self.username.text(), self.name.text(), self.password.text()
            )
        except ApplicationError as error:
            self.message.setText(str(error))
        else:
            self.accept()
        finally:
            self.clear_passwords()


def confirm_legacy_import() -> bool:
    return (
        QMessageBox.question(
            None,
            "Перенесення наявної бази CyberForge",
            "Знайдено базу попереднього випуску. Закрийте старий CyberForge. "
            "Перенести облікові записи, сценарії та результати до приватного профілю? "
            "Стара база залишиться на місці. Перевірену копію буде збережено "
            "у приватному сховищі. "
            "Після перенесення працюйте в новому випуску.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        == QMessageBox.StandardButton.Yes
    )


def choose_backup(
    parent: QWidget | None, backups: tuple[str, ...], *, emergency: bool = False
) -> str | None:
    if not backups:
        QMessageBox.information(parent, "Відновлення", "Резервних копій ще немає.")
        return None
    value, selected = QInputDialog.getItem(
        parent, "Відновлення", "Резервна копія", list(backups), 0, False
    )
    if not selected:
        return None
    warning = (
        "Використовуйте аварійне відновлення, якщо вхід неможливий. "
        "Закрийте всі інші випуски CyberForge. "
        if emergency
        else "CyberForge закриється для відновлення. "
    )
    reply = QMessageBox.question(
        parent,
        "Підтвердьте заміну бази даних",
        warning + "Активну базу буде замінено вибраною копією. "
        "Пізніші записи будуть відсутні у відновленій базі.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return value if reply == QMessageBox.StandardButton.Yes else None


class RecoveryPage(QWidget):
    def __init__(
        self,
        service: DataRecoveryService,
        get_token: Callable[[], str | None],
        close_for_restore: Callable[[str], None],
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        status = label("")
        backup = QPushButton("Створити резервну копію")
        restore = QPushButton("Відновити базу даних")
        layout.addWidget(status)
        layout.addWidget(backup)
        layout.addWidget(restore)
        layout.addStretch()

        def save() -> None:
            try:
                identifier = service.backup(get_token())
                status.setText(f"Створено перевірену резервну копію {identifier}.")
            except ApplicationError as error:
                status.setText(str(error))

        def recover() -> None:
            try:
                identifier = choose_backup(self, service.backups(get_token()))
                if identifier is not None:
                    close_for_restore(identifier)
            except ApplicationError as error:
                status.setText(str(error))

        backup.clicked.connect(save)
        restore.clicked.connect(recover)
