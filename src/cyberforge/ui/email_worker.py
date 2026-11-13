"""One-shot QRunnable; all delivery uses a queued QObject signal."""

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from cyberforge.domain.accounts import ApplicationError
from cyberforge.llm.contracts import ErrorCategory, GenerationError


def generation_message(category: ErrorCategory) -> str:
    return {
        ErrorCategory.TIMEOUT: "Час очікування генерації вичерпано. Спробуйте пізніше.",
        ErrorCategory.SAFETY: "Генерацію відхилено перевіркою безпеки.",
        ErrorCategory.BUDGET: "Локальний бюджет генерації вичерпано.",
        ErrorCategory.RATE_LIMIT: "Ліміт провайдера вичерпано. Спробуйте пізніше.",
        ErrorCategory.MISSING_CREDENTIALS: "Ключ обраного провайдера не налаштовано.",
        ErrorCategory.AUTHORIZATION: (
            "Провайдер відхилив доступ. Перевірте конфігурацію."
        ),
    }.get(category, "Не вдалося отримати валідний лист. Попередній матеріал збережено.")


@dataclass(frozen=True)
class RequestIdentity:
    request_id: str
    session_epoch: str
    scenario_id: int
    version: int
    revision: int
    archive_revision: int
    material_revision: int


class WorkerSignals(QObject):
    finished = Signal(object, object, str)


class EmailWorker(QRunnable):
    def __init__(
        self, identity: RequestIdentity, signals: WorkerSignals, operation: Callable
    ):
        super().__init__()
        self.identity, self.signals, self.operation = identity, signals, operation

    @Slot()
    def run(self) -> None:
        draft, message = None, ""
        try:
            draft = self.operation()
        except GenerationError as error:
            message = generation_message(error.category)
        except ApplicationError as error:
            message = str(error)
        except Exception:
            # Never forward raw provider/graph exceptions, prompts or credentials.
            message = "Генерацію не завершено. Попередній матеріал збережено."
        self.signals.finished.emit(self.identity, draft, message)
