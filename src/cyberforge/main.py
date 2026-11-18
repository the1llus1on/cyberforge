"""Desktop entry point and explicit local account/demo setup."""

import argparse
import sys
from collections.abc import Sequence
from contextlib import ExitStack
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
    parser.add_argument("--smoke-result", type=Path, help=argparse.SUPPRESS)
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
    setup.add_argument(
        "--recovery", action="store_true", help="Аварійне відновлення приватної бази"
    )
    parser.add_argument(
        "--credentials-file",
        type=Path,
        help="Новий приватний JSON-файл випадкових demo-паролів",
    )
    parser.add_argument(
        "--demo-profile", action="store_true", help="Окремий навчальний профіль Windows"
    )
    args = parser.parse_args(argv)
    if args.smoke_result and not args.smoke_test:
        parser.error("--smoke-result використовується лише з --smoke-test.")
    if args.learner_demo and (
        args.database is None or (args.init_demo and args.database.exists())
    ):
        parser.error(
            "Для --learner-demo вкажіть окрему БД; ініціалізація потребує нового файлу."
        )
    if args.web_demo and args.database is None:
        parser.error("Для --web-demo вкажіть окрему або явно обрану --database.")
    if args.demo_profile:
        if sys.platform != "win32" or any(
            (
                args.database,
                args.credentials_file,
                args.recovery,
                args.init_admin,
                args.smoke_test,
                args.email_demo,
                args.web_demo,
                args.learner_demo,
            )
        ):
            parser.error(
                "--demo-profile використовуйте окремо або з --init-demo у Windows."
            )
    elif args.init_demo and (args.database is None or args.credentials_file is None):
        parser.error("Для demo вкажіть --database та --credentials-file.")
    if args.credentials_file and not args.init_demo:
        parser.error("--credentials-file використовується лише з --init-demo.")
    if args.recovery and (sys.platform != "win32" or args.database or args.smoke_test):
        parser.error("Аварійне відновлення доступне для стандартного профілю Windows.")
    if getattr(sys, "frozen", False) and args.database:
        parser.error("Цей випуск використовує приватний профіль CyberForge.")

    from alembic.util.exc import CommandError
    from PySide6.QtCore import QCoreApplication, QStandardPaths, QTimer
    from sqlalchemy.exc import SQLAlchemyError

    from cyberforge.application.accounts import AccountService
    from cyberforge.application.data_recovery import DataRecoveryService
    from cyberforge.domain.accounts import ApplicationError
    from cyberforge.persistence.database import Database
    from cyberforge.persistence.profile import (
        PROFILE_ERROR,
        PrivateProfile,
        private_profile_root,
    )
    from cyberforge.persistence.recovery import ProfileRecovery

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
    packaged = getattr(sys, "frozen", False)
    if packaged and args.smoke_test:
        QStandardPaths.setTestModeEnabled(True)
    data_location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    protected = args.database is None and sys.platform == "win32"
    private_root = private_profile_root(Path(data_location))
    path = args.database or private_root / "cyberforge.sqlite3"
    lifetime = ExitStack()
    database = None
    try:
        storage = None
        if protected:
            if not data_location:
                raise ApplicationError(PROFILE_ERROR)
            try:
                if packaged:
                    from cyberforge.persistence.windows_profile import release_instance

                    lifetime.enter_context(release_instance())
                if args.demo_profile:
                    from cyberforge.application.release_demo import (
                        DEMO_DIRECTORY,
                        prepare_demo_profile,
                    )

                    container = PrivateProfile(private_root.with_name(DEMO_DIRECTORY))
                    lifetime.enter_context(container.acquire())
                    profile = prepare_demo_profile(container, initialize=args.init_demo)
                    if args.init_demo:
                        return 0
                else:
                    profile = PrivateProfile(path.parent)
                lifetime.enter_context(profile.acquire())
            except OSError as error:
                _smoke_failure(
                    args.smoke_result,
                    "windows-profile",
                    type(error).__name__,
                    getattr(error, "winerror", None),
                )
                raise ApplicationError(PROFILE_ERROR) from None
            storage = ProfileRecovery(profile)
            if args.recovery:
                from cyberforge.ui.data_recovery import choose_backup

                identifier = choose_backup(
                    None, storage.available_backups(), emergency=True
                )
                if identifier is not None:
                    storage.restore(identifier, emergency=True)
                    _show_restored()
                return 0
            database = storage.startup()
        else:
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
        from cyberforge.application.provider_settings import ProviderSettings
        from cyberforge.application.scenarios import ScenarioService
        from cyberforge.application.web_materials import WebMaterialService
        from cyberforge.llm.config import GatewayConfig, load_config
        from cyberforge.llm.contracts import GenerationError
        from cyberforge.llm.factory import create_gateway
        from cyberforge.llm.windows_credentials import WindowsCredentialStore
        from cyberforge.ui.data_recovery import BootstrapDialog
        from cyberforge.ui.shell import MainWindow
        from cyberforge.ui.theme import apply_theme

        apply_theme(app)
        demo = (
            args.email_demo or args.web_demo or args.learner_demo or args.demo_profile
        )
        if (
            protected
            and not args.smoke_test
            and not demo
            and accounts.needs_bootstrap()
        ):
            if not BootstrapDialog(accounts).exec():
                return 0
        try:
            config = (
                GatewayConfig()
                if demo or getattr(sys, "frozen", False)
                else load_config()
            )
        except GenerationError:
            raise ApplicationError(
                "Некоректна конфігурація LLM. Перевірте локальні налаштування."
            ) from None
        provider_settings = (
            ProviderSettings(
                accounts,
                storage.profile,
                lambda profile_id: WindowsCredentialStore("stable", profile_id),
            )
            if storage is not None and not demo
            else None
        )
        emails = EmailMaterialService(
            ScenarioService(accounts),
            create_gateway(config),
            demo=demo,
            provider_settings=provider_settings
            if config.provider.value == "mock"
            else None,
        )
        recovery = DataRecoveryService(accounts, storage) if storage else None
        window = MainWindow(
            accounts,
            emails,
            WebMaterialService(
                emails, demo=args.web_demo or args.learner_demo or args.demo_profile
            ),
            recovery=recovery,
            provider_settings=provider_settings,
        )
        window.show()
        smoke_browser = None
        if args.smoke_test:
            if packaged:
                from cyberforge.ui.web_browser import WebBrowser

                smoke_browser = WebBrowser(window)
                smoke_browser.load_succeeded.connect(
                    lambda: QTimer.singleShot(0, window.close)
                )
                smoke_browser.resize(500, 320)
                smoke_browser.show()
                smoke_browser.set_draft(None)
                smoke_browser.view.show()
                QTimer.singleShot(20000, lambda: app.exit(2))
            else:
                QTimer.singleShot(500, window.close)
        result = app.exec()
        if smoke_browser is not None:
            smoke_browser.dispose()
        database.close()
        database = None
        if recovery is not None and recovery.restore_after_shutdown():
            _show_restored()
        return result
    except ApplicationError as error:
        _smoke_failure(args.smoke_result, "application", str(error))
        print(str(error), file=sys.stderr)
        if protected and not setup_only and not args.smoke_test:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(None, "CyberForge", str(error))
        return 1
    except (OSError, SQLAlchemyError, CommandError) as error:
        _smoke_failure(args.smoke_result, "startup", type(error).__name__)
        print("Не вдалося відкрити або оновити локальну базу даних.", file=sys.stderr)
        return 1
    finally:
        if database is not None:
            database.close()
        lifetime.close()


def _smoke_failure(path: Path | None, stage: str, detail: str, number=None) -> None:
    if path is None:
        return
    try:
        with path.open("x", encoding="utf-8") as report:
            report.write(f"{stage} ({detail})")
            if number is not None:
                report.write(f" [{number}]")
    except OSError:
        pass


def _show_restored() -> None:
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.information(
        None, "Відновлення", "Базу відновлено. Запустіть CyberForge та увійдіть."
    )
