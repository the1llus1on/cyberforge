from PySide6.QtWidgets import QDialog

from cyberforge.application.accounts import AccountService
from cyberforge.domain.accounts import Role
from cyberforge.persistence.database import Database
from cyberforge.ui.data_recovery import BootstrapDialog


def test_bootstrap_dialog_validates_confirmation_and_creates_once(qtbot, tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.upgrade()
    accounts = AccountService(db)
    try:
        dialog = BootstrapDialog(accounts)
        qtbot.addWidget(dialog)
        assert accounts.needs_bootstrap()
        dialog.username.setText("root")
        dialog.name.setText("Адміністратор")
        dialog.password.setText("synthetic-password")
        dialog.confirmation.setText("different-password")
        dialog.create_account()
        assert "не збігаються" in dialog.message.text()
        assert accounts.needs_bootstrap()
        assert not dialog.password.text() and not dialog.confirmation.text()

        dialog.password.setText("synthetic-password")
        dialog.confirmation.setText("synthetic-password")
        dialog.create_account()
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert not accounts.needs_bootstrap()
        token = accounts.login("root", "synthetic-password")
        assert accounts.current(token).role is Role.ADMINISTRATOR

        duplicate = BootstrapDialog(accounts)
        qtbot.addWidget(duplicate)
        duplicate.username.setText("duplicate")
        duplicate.name.setText("Інший адміністратор")
        duplicate.password.setText("synthetic-password")
        duplicate.confirmation.setText("synthetic-password")
        duplicate.create_account()
        assert "вже створено" in duplicate.message.text()
        assert len(accounts.list_users(token)) == 1
    finally:
        db.close()


def test_bootstrap_cancel_clears_passwords_and_leaves_database_empty(qtbot, tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.upgrade()
    accounts = AccountService(db)
    try:
        dialog = BootstrapDialog(accounts)
        qtbot.addWidget(dialog)
        dialog.password.setText("synthetic-password")
        dialog.confirmation.setText("synthetic-password")
        dialog.reject()
        assert accounts.needs_bootstrap()
        assert not dialog.password.text() and not dialog.confirmation.text()
    finally:
        db.close()
