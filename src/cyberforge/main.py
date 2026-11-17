"""Desktop entry point and explicit local account/demo setup."""

import argparse
import sys
from collections.abc import Sequence
from getpass import getpass
from pathlib import Path


def _configure_output() -> None:
    """Use UTF-8 for redirected CLI messages, including isolated Windows Python."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None and not stream.isatty():
            reconfigure(encoding="utf-8", errors="backslashreplace")


def main(argv: Sequence[str] | None = None) -> int:
    _configure_output()
    parser = argparse.ArgumentParser(description="CyberForge — навчальна платформа")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Перевірити запуск і закрити вікно"
    )
    parser.add_argument("--database", type=Path, help="Шлях до спільної локальної БД")
    parser.add_argument(
        "--email-demo",
        action="store_true",
        help="Явне офлайн-демо конструктора листа; синтетичний шаблон без AI та мережі",
    )
    parser.add_argument(
        "--web-demo",
        action="store_true",
        help="Явне офлайн-демо Web та Email, без AI й мережі",
    )
    parser.add_argument(
        "--learner-demo",
        action="store_true",
        help=(
            "Явне офлайн-демо проходження; з --init-demo створює публікацію в новій БД"
        ),
    )
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
    if args.learner_demo and (
        args.database is None or (args.init_demo and args.database.exists())
    ):
        parser.error(
            "Для --learner-demo вкажіть окрему БД; ініціалізація потребує нового файлу."
        )
    if args.web_demo and args.database is None:
        parser.error("Для --web-demo вкажіть окрему або явно обрану --database.")
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
    if not setup_only:
        from cyberforge.web.resources import register_web_scheme

        register_web_scheme()
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
            if args.learner_demo and created:
                from cyberforge.application.learner_demo import prepare_publication

                prepare_publication(accounts, args.credentials_file)
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
        from cyberforge.application.email_materials import EmailMaterialService
        from cyberforge.application.scenarios import ScenarioService
        from cyberforge.application.web_materials import WebMaterialService
        from cyberforge.llm.config import GatewayConfig, load_config
        from cyberforge.llm.contracts import GenerationError
        from cyberforge.llm.factory import create_gateway
        from cyberforge.ui.shell import MainWindow
        from cyberforge.ui.theme import apply_theme

        apply_theme(app)
        try:
            config = (
                GatewayConfig()
                if args.email_demo or args.web_demo or args.learner_demo
                else load_config()
            )
        except GenerationError:
            raise ApplicationError(
                "Некоректна конфігурація LLM. Перевірте локальні налаштування."
            ) from None
        emails = EmailMaterialService(
            ScenarioService(accounts),
            create_gateway(config),
            demo=args.email_demo or args.web_demo or args.learner_demo,
        )
        window = MainWindow(
            accounts,
            emails,
            WebMaterialService(emails, demo=args.web_demo or args.learner_demo),
        )
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
