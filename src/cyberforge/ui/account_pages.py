"""Login and profile forms. Password fields are masked and cleared after use."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.accounts import AccountService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.ui.pages import label


class AccountPage(QWidget):
    authenticated = Signal(str)
    signed_out = Signal()
    close_requested = Signal()

    def __init__(self, accounts: AccountService) -> None:
        super().__init__()
        self.accounts = accounts
        self.token: str | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 32, 36, 32)
        outer.addStretch()
        content = QFrame()
        content.setObjectName("card")
        content.setMaximumWidth(760)
        centered = QHBoxLayout()
        centered.addStretch()
        centered.addWidget(content, 1)
        centered.addStretch()
        outer.addLayout(centered)
        outer.addStretch()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        self.title = label("Вхід до CyberForge", "title")
        layout.addWidget(label("CyberForge", "heading"))
        layout.addWidget(self.title)
        self.identity = label("")
        layout.addWidget(self.identity)
        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setMaxLength(80)
        self.password = QLineEdit()
        self.password.setMaxLength(1024)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password = QLineEdit()
        self.new_password.setMaxLength(1024)
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Логін", self.username)
        form.addRow("Пароль / поточний пароль", self.password)
        form.addRow("Новий пароль (12–1024 символів)", self.new_password)
        self.form = form
        layout.addLayout(form)
        self.error = label("")
        layout.addWidget(self.error)
        self.login_button = QPushButton("Увійти")
        self.login_button.setObjectName("primary")
        self.login_button.clicked.connect(self.login)
        self.password.returnPressed.connect(self.submit)
        layout.addWidget(self.login_button)
        self.change_button = QPushButton("Змінити пароль та вийти")
        self.change_button.clicked.connect(self.change_password)
        layout.addWidget(self.change_button)
        self.logout_button = QPushButton("Вийти")
        self.logout_button.clicked.connect(self.logout)
        layout.addWidget(self.logout_button)
        close_button = QPushButton("Закрити")
        close_button.clicked.connect(self.close_requested)
        layout.addWidget(close_button)
        layout.addStretch()
        self.refresh(None)

    def refresh(self, token: str | None) -> None:
        self.clear()
        self.token = token
        account = self.accounts.current(token) if token else None
        self.title.setText("Ваш обліковий запис" if account else "Вхід до CyberForge")
        self.identity.setText(
            f"{account.display_name} · {account.username} · {account.role.label}"
            if account
            else "Увійдіть до облікового запису."
        )
        self.form.labelForField(self.password).setText(
            "Поточний пароль" if account else "Пароль"
        )
        self.username.setVisible(account is None)
        self.form.labelForField(self.username).setVisible(account is None)
        self.new_password.setVisible(account is not None)
        self.form.labelForField(self.new_password).setVisible(account is not None)
        self.login_button.setVisible(account is None)
        self.change_button.setVisible(account is not None)
        self.logout_button.setVisible(account is not None)

    def clear(self) -> None:
        self.username.clear()
        self.password.clear()
        self.new_password.clear()
        self.error.clear()

    def submit(self) -> None:
        if self.token:
            self.change_password()
        else:
            self.login()

    def login(self) -> None:
        try:
            token = self.accounts.login(
                self.username.text(), self.password.text(), current_token=self.token
            )
        except ApplicationError as error:
            self.error.setText(str(error))
        else:
            self.authenticated.emit(token)
        finally:
            self.password.clear()

    def logout(self) -> None:
        self.accounts.logout(self.token)
        self.clear()
        self.signed_out.emit()

    def change_password(self) -> None:
        try:
            self.accounts.change_password(
                self.token, self.password.text(), self.new_password.text()
            )
        except ApplicationError as error:
            self.error.setText(str(error))
        else:
            self.signed_out.emit()
        finally:
            self.password.clear()
            self.new_password.clear()
