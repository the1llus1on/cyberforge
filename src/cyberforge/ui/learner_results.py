"""Personal result history and details; all data arrives through authorized services."""

from dataclasses import replace
from uuid import uuid4

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QGridLayout,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.evaluations import EvaluationFailure
from cyberforge.domain.accounts import ApplicationError
from cyberforge.evaluation.canonical import percentage_text
from cyberforge.ui.learner_pages import STATUS, label, stamp


class FeedbackSignals(QObject):
    finished = Signal(str, object, str)


class FeedbackWorker(QRunnable):
    def __init__(self, service, token, attempt_id, epoch, signals):
        super().__init__()
        self.service, self.token, self.attempt_id = service, token, attempt_id
        self.epoch, self.signals = epoch, signals

    @Slot()
    def run(self):
        message = ""
        try:
            self.service.generate(self.token, self.attempt_id)
        except ApplicationError as exc:
            message = str(exc)
        except Exception:
            message = "Пояснення недоступне. Збережену оцінку не змінено."
        self.signals.finished.emit(self.epoch, self.attempt_id, message)


def summary(row):
    if row.error:
        return (
            "Помилка цілісності оцінки"
            if row.error.integrity_reason
            else "Оцінка тимчасово недоступна"
        )
    if row.result:
        return (
            "Оцінка: " + percentage_text(row.result.score_percent) + "%"
            if row.result.status == "SCORED"
            else "Без числової оцінки (UNSCORABLE)"
        )
    if row.attempt.status == "COMPLETED":
        return "Очікує оцінювання"
    return "Незавершена спроба · оцінка відсутня"


def result_text(result):
    lines = [
        "Детерміноване оцінювання · "
        + (
            percentage_text(result.score_percent) + "%"
            if result.status == "SCORED"
            else "Без числової оцінки (UNSCORABLE)"
        ),
        "Час оцінювання: " + stamp(result.evaluated_at),
    ]
    if result.status == "UNSCORABLE":
        lines.append("Немає застосовних числових критеріїв. Це не нульова оцінка.")
    lines.append("\nКритерії:")
    for c in result.criteria:
        text = {
            "MET": "Виконано · 1",
            "NOT_MET": "Не зафіксовано · 0",
            "NOT_APPLICABLE": "Не застосовується · оцінка відсутня",
            "DESCRIPTIVE": "Описовий критерій · без числової оцінки",
        }[c.outcome]
        lines.append(c.criterion.label + ": " + text)
    transition = (
        "Відмова від переходу"
        if result.transition.final_action_id == "decline"
        else "Внутрішній перехід"
    )
    lines.extend(
        [
            "\nРішення про перехід: " + transition,
            "Послідовність рішень: "
            + ", ".join(str(r.sequence) for r in result.transition.event_refs),
            "Шлях: "
            + (
                "Завершено без відвідування Web"
                if result.path.kind == "SAFE_DECLINE"
                else "Підтверджено відвідування Web"
            ),
            "\nПравила критичних порушень не налаштовано. Штрафи не застосовуються.",
        ]
    )
    for obs in result.critical_observations:
        lines.append(
            (
                "Підтвердження"
                if obs.action_id == "confirm"
                else "Надсилання синтетичної форми"
            )
            + f" · подія {obs.event_ref.sequence} · {stamp(obs.observed_at)}"
        )
    lines.append(
        "Факти дій не встановлюють причин поведінки чи правильності "
        "розпізнавання загрози."
    )
    return "\n".join(lines)


def feedback_text(value):
    mode = (
        "Детерміноване локальне пояснення"
        if value.mode == "DETERMINISTIC"
        else "AI добір перевірених фактів"
    )
    lines = ["Навчальне пояснення · " + mode]
    for fact in value.explanation.selected_facts:
        lines.append(fact.observation + " " + fact.explanation)
    lines.extend(
        [
            "\nРекомендації:",
            *value.explanation.recommendations,
            "\nОбмеження:",
            *value.explanation.limitations,
        ]
    )
    return "\n".join(lines)


class LearnerResultsPage(QWidget):
    def __init__(self, evaluations, mentor, token_provider):
        super().__init__()
        self.evaluations, self.mentor, self.token_provider = (
            evaluations,
            mentor,
            token_provider,
        )
        self.rows, self.epoch, self.pending = (), uuid4().hex, set()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.jobs = set()
        self.signals = FeedbackSignals(self)
        self.signals.finished.connect(self._feedback_finished)
        layout = QVBoxLayout(self)
        layout.addWidget(label("Мої результати · історія проходжень"))
        self.notice = label(
            "Завершення сценарію не означає успішне складання. Оцінку обчислює система."
        )
        layout.addWidget(self.notice)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.list = QListWidget()
        self.list.setAccessibleName("Мої проходження")
        self.list.setWordWrap(True)
        self.list.currentRowChanged.connect(self.details)
        splitter.addWidget(self.list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        detail_layout = QVBoxLayout(content)
        self.detail, self.feedback = label(), label()
        for item in (self.detail, self.feedback):
            item.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            item.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            detail_layout.addWidget(item)
        detail_layout.addStretch()
        scroll.setWidget(content)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        controls = QGridLayout()
        self.refresh_button = QPushButton("Оновити результати")
        self.evaluate_button = QPushButton("Обчислити оцінку")
        self.feedback_button = QPushButton("Отримати пояснення")
        self.refresh_button.clicked.connect(self.refresh)
        self.evaluate_button.clicked.connect(self.evaluate)
        self.feedback_button.clicked.connect(self.generate_feedback)
        for i, item in enumerate(
            (self.refresh_button, self.evaluate_button, self.feedback_button)
        ):
            item.setAccessibleName(item.text())
            controls.addWidget(item, i // 2, i % 2)
        layout.addLayout(controls)
        self.setMinimumWidth(0)
        self.invalidate()

    @property
    def running(self):
        return bool(self.jobs) or self.pool.activeThreadCount() > 0

    def invalidate(self):
        self.epoch, self.rows = uuid4().hex, ()
        self.pending.clear()
        self.list.clear()
        self.detail.clear()
        self.feedback.clear()
        self.notice.clear()
        self.evaluate_button.setEnabled(False)
        self.feedback_button.setEnabled(False)

    def refresh(self):
        aid = self._selected_id()
        try:
            rows = self.evaluations.history(self.token_provider())
        except ApplicationError as exc:
            self.invalidate()
            self.notice.setText(str(exc))
            return
        self.rows = rows
        self.list.blockSignals(True)
        self.list.clear()
        for row in rows:
            a = row.attempt
            self.list.addItem(
                f"{a.scenario_name} · версія {a.scenario_version}\n"
                f"{STATUS[a.status]} · Початок: {stamp(a.started_at)}\n"
                f"Завершення: {stamp(a.completed_at or a.abandoned_at)}\n{summary(row)}"
            )
        index = next(
            (i for i, r in enumerate(rows) if r.attempt.attempt_id == aid),
            0 if rows else -1,
        )
        self.list.setCurrentRow(index)
        self.list.blockSignals(False)
        self.notice.setText("" if rows else "Ви ще не розпочали жодного сценарію.")
        self.details(index)

    def _selected_id(self):
        i = self.list.currentRow()
        return self.rows[i].attempt.attempt_id if 0 <= i < len(self.rows) else None

    def details(self, index):
        self.detail.clear()
        self.feedback.clear()
        self.evaluate_button.setEnabled(False)
        self.feedback_button.setEnabled(False)
        if not 0 <= index < len(self.rows):
            return
        aid = self.rows[index].attempt.attempt_id
        try:
            # Reauthorize on every detail action, including cached history rows.
            a = self.evaluations.attempts.get(self.token_provider(), aid)
            result = self.evaluations.read(self.token_provider(), aid)
            self.detail.setText(
                f"{a.scenario_name} · версія {a.scenario_version}\n"
                f"{STATUS[a.status]} · Завершення: "
                f"{stamp(a.completed_at or a.abandoned_at)}\n"
                + (result_text(result) if result else summary(self.rows[index]))
            )
            self.evaluate_button.setEnabled(a.status == "COMPLETED" and result is None)
        except ApplicationError as exc:
            self._details_error(exc)
            return
        try:
            value = self.mentor.read(self.token_provider(), aid) if result else None
            self.feedback.setText(
                feedback_text(value)
                if value
                else "Навчальне пояснення ще не збережено."
            )
            self.feedback_button.setEnabled(
                result is not None and value is None and aid not in self.pending
            )
        except ApplicationError as exc:
            self._details_error(exc, feedback_only=True)

    def _details_error(self, exc, *, feedback_only=False):
        if isinstance(exc, EvaluationFailure) and exc.error.code != "ACCESS_DENIED":
            if exc.error.code in {
                "STORED_EVALUATION_INTEGRITY_ERROR",
                "IMMUTABLE_SOURCE_INTEGRITY_ERROR",
            }:
                index = self.list.currentRow()
                if 0 <= index < len(self.rows):
                    row = replace(self.rows[index], result=None, error=exc.error)
                    self.rows = self.rows[:index] + (row,) + self.rows[index + 1 :]
                    item = self.list.item(index)
                    item.setText(item.text().rsplit("\n", 1)[0] + "\n" + summary(row))
                self.detail.setText(str(exc))
                self.feedback.clear()
                self.evaluate_button.setEnabled(False)
                self.feedback_button.setEnabled(False)
            elif feedback_only:
                self.feedback.setText(str(exc))
            else:
                self.detail.setText(str(exc))
        else:
            self.invalidate()
            self.notice.setText(str(exc))

    def evaluate(self):
        aid = self._selected_id()
        if aid is None:
            return
        try:
            self.evaluations.evaluate(self.token_provider(), aid)
            self.refresh()
            self.generate_feedback()
        except ApplicationError as exc:
            self.notice.setText(str(exc))
            self.details(self.list.currentRow())

    def generate_feedback(self):
        aid = self._selected_id()
        if aid is None or aid in self.pending:
            return
        self.pending.add(aid)
        self.feedback_button.setEnabled(False)
        self.feedback.setText("Готуємо навчальне пояснення…")
        worker = FeedbackWorker(
            self.mentor, self.token_provider(), aid, self.epoch, self.signals
        )
        self.jobs.add((self.epoch, aid))
        self.pool.start(worker)

    def _feedback_finished(self, epoch, aid, message):
        self.jobs.discard((epoch, aid))
        if epoch != self.epoch:
            return
        self.pending.discard(aid)
        if self._selected_id() != aid:
            return
        self.details(self.list.currentRow())
        if message:
            self.feedback.setText(message)
