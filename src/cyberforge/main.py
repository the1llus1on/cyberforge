"""Desktop entry point and explicit local account/demo setup."""

import argparse
import sys
from collections.abc import Sequence
from getpass import getpass
from pathlib import Path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CyberForge — навчальна платформа")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Перевірити запуск і закрити вікно"
    )
    parser.add_argument("--database", type=Path, help="Шлях до спільної локальної БД")
    setup = parser.add_mutually_exclusive_group()
    setup.add_argument(
        "--init-admin",
        action="store_true",
        help="Створити першого адміністратора в порожній БД",
    )
    setup.add_argument(
        "--init-demo",
        action="store_true",
        help="Ініціалізувати окрему демонстраційну БД",
    )
    parser.add_argument(
        "--credentials-file",
        type=Path,
        help="Новий приватний JSON-файл випадкових demo-паролів",
    )
    args = parser.parse_args(argv)
    if args.init_demo and (args.database is None or args.credentials_file is None):
        parser.error("Для demo вкажіть --database та --credentials-file.")
    if args.credentials_file and not args.init_demo:
        parser.error("--credentials-file використовується лише з --init-demo.")

    from alembic.util.exc import CommandError
    from PySide6.QtCore import QCoreApplication, QStandardPaths, QTimer
    from sqlalchemy.exc import SQLAlchemyError

    from cyberforge.application.accounts import AccountService
    from cyberforge.domain.accounts import ApplicationError
    from cyberforge.persistence.database import Database

    setup_only = args.init_admin or args.init_demo
    if setup_only:
        app = QCoreApplication([sys.argv[0]])
    else:
        from PySide6.QtWidgets import QApplication

        app = QApplication([sys.argv[0]])
    app.setApplicationName("CyberForge")
    app.setOrganizationName("CyberForge")
    path = (
        args.database
        or Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppLocalDataLocation
            )
        )
        / "cyberforge.sqlite3"
    )
    database = None
    try:
        database = Database(path)
        database.upgrade()
        accounts = AccountService(database)
        if args.init_demo:
            from cyberforge.application.demo import initialize_demo

            created = initialize_demo(accounts, args.credentials_file)
            print(
                (
                    "Демонстраційні дані створено. Паролі записано лише у "
                    "вказаний приватний файл."
                )
                if created
                else (
                    "Демонстраційні облікові записи вже існують. "
                    "Дані та паролі збережено."
                )
            )
            return 0
        if args.init_admin:
            if not sys.stdin.isatty():
                raise ApplicationError(
                    "Для безпечного введення пароля відкрийте інтерактивний термінал."
                )
            username = input("Логін адміністратора: ")
            password = getpass("Пароль (щонайменше 12 символів): ")
            if password != getpass("Повторіть пароль: "):
                raise ApplicationError("Паролі не збігаються.")
            accounts.bootstrap(username, "Адміністратор", password)
            print("Обліковий запис адміністратора створено.")
            return 0
        from cyberforge.ui.shell import MainWindow
        from cyberforge.ui.theme import apply_theme

        apply_theme(app)
        window = MainWindow(accounts)
        window.show()
        if args.smoke_test:
            QTimer.singleShot(500, window.close)
        return app.exec()
    except ApplicationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, SQLAlchemyError, CommandError):
        print("Не вдалося відкрити або оновити локальну базу даних.", file=sys.stderr)
        return 1
    finally:
        if database is not None:
            database.close()
