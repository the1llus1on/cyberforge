"""Instructor and administrator analytics through the authorized application API."""

from datetime import UTC, datetime, timedelta
from functools import partial
from html import escape
from threading import Event

from pydantic import ValidationError
from PySide6.QtCore import (
    QAbstractTableModel,
    QDateTime,
    QObject,
    QRunnable,
    QSignalBlocker,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from cyberforge.analytics.contracts import (
    AnalyticsQueryV1,
    HistoryQueryV1,
    display_percent,
)
from cyberforge.domain.accounts import AccessDenied, ApplicationError
from cyberforge.ui.analytics_charts import BarChart, CriterionChart

LABELS = {
    "NOT_STARTED": "Не розпочато",
    "IN_PROGRESS": "Триває",
    "ABANDONED": "Припинено",
    "COMPLETED": "Завершено",
    "COMPLETED_PENDING_EVALUATION": "Очікує оцінювання",
    "SCORED_ZERO": "Перевірений нуль",
    "SCORED_NONZERO": "Перевірено",
    "UNSCORABLE": "Без числової оцінки",
    "NOT_APPLICABLE": "Не застосовується",
    "STORED_EVALUATION_INTEGRITY_ERROR": "Порушено цілісність оцінки",
    "IMMUTABLE_SOURCE_INTEGRITY_ERROR": "Порушено цілісність джерела",
    "MISSING_FEEDBACK": "Пояснення відсутнє",
    "STORED_FEEDBACK_INTEGRITY_ERROR": "Порушено цілісність пояснення",
    "VERIFIED": "Пояснення перевірено",
    "MET": "Виконано",
    "NOT_MET": "Не виконано",
    "DESCRIPTIVE": "Описовий",
    "draft": "Чернетка",
    "published": "Опубліковано",
    "archived": "Архівовано",
}


def _label(text=""):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return widget


def _time(value):
    return value.strftime("%d.%m.%Y %H:%M UTC") if value else "—"


def _score(value, state):
    text = display_percent(value)
    return LABELS[state] if text is None else f"{text}% · {LABELS[state]}"


def _summary(value, not_applicable=False):
    if not_applicable:
        return LABELS["NOT_APPLICABLE"]
    if value is None:
        return "Немає даних"
    return (
        f"Виконано {value.met} · Не виконано {value.not_met} · "
        f"Не застос. {value.not_applicable} · Описові {value.descriptive}"
    )


def _observations(value):
    return (
        f"Підтвердження {value.confirm} · "
        f"Синтетичні надсилання {value.submit_synthetic}"
    )


def _coverage(value):
    return (
        f"Перевірені числові {value.scored}/{value.total} · "
        f"Нуль {value.scored_zero} · Без числової оцінки {value.unscorable} · "
        f"Очікують {value.pending} · "
        f"Пошкоджені оцінки {value.stored_integrity_error} · "
        f"Пошкоджені джерела {value.source_integrity_error} · "
        f"Пояснення відсутні {value.feedback_missing}, "
        f"пошкоджені {value.feedback_integrity_error}"
    )


class LearnerTable(QAbstractTableModel):
    headers = (
        "Учень",
        "Групи",
        "Участь",
        "Активність",
        "Спроби",
        "Завершені",
        "Критерії Email",
        "Критерії Web",
        "Оцінка",
        "Спостереження",
        "Остання дія",
    )

    def __init__(self, parent):
        super().__init__(parent)
        self.rows = ()

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else len(self.rows)

    def columnCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else len(self.headers)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self.headers[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role not in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ToolTipRole,
        ):
            return None
        row = self.rows[index.row()]
        participation = (
            "Поточна й історична"
            if row.current and row.historical
            else ("Поточна" if row.current else "Історична")
        )
        columns = (
            f"{row.name} ({row.username})",
            ", ".join(g.name for g in row.groups),
            participation,
            LABELS[row.activity],
            row.attempts.total,
            row.attempts.completed,
            _summary(row.email),
            _summary(row.web, row.web_not_applicable),
            _score(row.score, row.result_status),
            _observations(row.observations),
            _time(row.last_activity),
        )
        value = columns[index.column()]
        return escape(str(value)) if role == Qt.ItemDataRole.ToolTipRole else value


class _WorkerSignals(QObject):
    done = Signal(int, str, object, str)


class _Worker(QRunnable):
    def __init__(self, generation, kind, operation, cancelled, signals):
        super().__init__()
        self.generation, self.kind, self.operation = generation, kind, operation
        self.cancelled, self.signals = cancelled, signals

    def run(self):
        if self.cancelled.is_set():
            return
        try:
            output = self.operation()
        except (ApplicationError, ValidationError) as exc:
            message = (
                "Доступ до аналітики обмежено. Оновіть дані."
                if isinstance(exc, AccessDenied)
                else "Параметри аналітики або збережені дані недійсні."
                if isinstance(exc, ValidationError)
                else str(exc)
            )
            output = None
        except Exception:
            # A failed worker must always return the page to a retryable state.
            message, output = "Не вдалося отримати дані аналітики.", None
        else:
            message = ""
        if not self.cancelled.is_set():
            self.signals.done.emit(self.generation, self.kind, output, message)


class AnalyticsPage(QWidget):
    reveal_details = Signal(QWidget)

    def __init__(self, service):
        super().__init__()
        self.service = service
        self.token = self.scenario_id = None
        self.snapshot = self.access = self.history = None
        self.generation = self.detail_generation = 0
        self.cancelled = Event()
        self.check_pending = False
        self.exporting = False
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.signals = _WorkerSignals(self)
        self.signals.done.connect(self._done, Qt.ConnectionType.QueuedConnection)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(250)
        self.debounce.timeout.connect(self.refresh)
        self.title = _label("Аналіз сценарію")
        self.title.setObjectName("heading")
        self.scenario_info = _label("Сценарій не вибрано.")
        self.message = _label()
        self.login_button = QPushButton("Увійти")
        self.content = QWidget()
        self.content.setMinimumWidth(0)
        self.controls = QWidget()
        self.controls.setMinimumWidth(0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        for widget in (
            self.title,
            self.scenario_info,
            self.login_button,
            self.message,
            self.controls,
            self.content,
        ):
            layout.addWidget(widget)
        self._filters()
        self._results()
        self._detail_panel()
        layout.addStretch()
        self.invalidate()

    @property
    def running(self):
        return self.pool.activeThreadCount() > 0

    def _combo(self, name, values):
        combo = QComboBox()
        combo.setAccessibleName(name)
        combo.setMinimumContentsLength(9)
        combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        for text, value in values:
            combo.addItem(text, value)
        combo.currentIndexChanged.connect(self._filters_changed)
        return combo

    def _filters(self):
        form = QFormLayout(self.controls)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.versions = self._combo("Версія", [("Усі опубліковані версії", None)])
        self.groups = self._combo("Група", [("Усі дозволені групи", None)])
        self.status = self._combo(
            "Стан спроби",
            [("Усі стани", None)]
            + [
                (LABELS[status], status)
                for status in ("IN_PROGRESS", "ABANDONED", "COMPLETED")
            ],
        )
        self.aggregation = self._combo(
            "Агрегація",
            [
                (
                    "Остання завершена спроба кожного учня",
                    "LATEST_COMPLETED_PER_LEARNER",
                ),
                ("Усі завершені спроби", "ALL_COMPLETED_ATTEMPTS"),
            ],
        )
        self.sort = self._combo(
            "Сортування",
            [
                ("Ім’я", "name"),
                ("Активність", "status"),
                ("Кількість спроб", "attempts"),
                ("Оцінка", "score"),
                ("Остання дія", "last_activity"),
            ],
        )
        self.direction = self._combo(
            "Напрямок", [("За зростанням", "asc"), ("За спаданням", "desc")]
        )
        self.search = QLineEdit()
        self.search.setPlaceholderText("Ім’я або логін учня")
        self.search.setAccessibleName("Пошук учня")
        self.search.setMaxLength(160)
        self.search.textChanged.connect(self._filters_changed)
        for title, widget in (
            ("Версія", self.versions),
            ("Група", self.groups),
            ("Стан спроби", self.status),
            ("Агрегація", self.aggregation),
            ("Пошук учня", self.search),
            ("Сортування", self.sort),
            ("Напрямок", self.direction),
        ):
            form.addRow(title, widget)
        self.from_enabled, self.from_time = self._boundary(form, "Від (UTC)")
        self.to_enabled, self.to_time = self._boundary(form, "До (UTC, виключно)")
        refresh = QPushButton("Оновити")
        refresh.clicked.connect(self.refresh)
        form.addRow(refresh)

    def _boundary(self, form, title):
        enabled = QCheckBox(title)
        edit = QDateTimeEdit(QDateTime.currentDateTimeUtc())
        edit.setTimeZone(QDateTime.currentDateTimeUtc().timeZone())
        edit.setDisplayFormat("dd.MM.yyyy HH:mm")
        edit.setCalendarPopup(True)
        edit.setAccessibleName(title)
        edit.setEnabled(False)
        enabled.toggled.connect(edit.setEnabled)
        enabled.toggled.connect(self._filters_changed)
        edit.dateTimeChanged.connect(self._filters_changed)
        form.addRow(enabled, edit)
        return enabled, edit

    def _results(self):
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scope_label = _label()
        layout.addWidget(self.scope_label)
        cards = QGridLayout()
        self.cards = []
        for index, heading in enumerate(
            (
                "Поточна аудиторія",
                "Участь і завершення",
                "Перевірений середній бал",
                "Підтверджені переходи Web",
                "Спостереження",
                "Критична політика",
            )
        ):
            box = QWidget()
            panel = QVBoxLayout(box)
            panel.setContentsMargins(8, 4, 8, 4)
            panel.addWidget(_label(heading))
            value = _label()
            value.setAccessibleName(heading)
            panel.addWidget(value)
            self.cards.append(value)
            cards.addWidget(box, index // 2, index % 2)
        layout.addLayout(cards)
        self.quality = _label()
        layout.addWidget(self.quality)
        self.score_chart = BarChart("Розподіл перевірених балів (%)", 5)
        self.lifecycle_chart = BarChart("Життєвий цикл спроб", 3)
        self.criterion_chart = CriterionChart()
        for chart in (self.score_chart, self.lifecycle_chart, self.criterion_chart):
            layout.addWidget(chart)
        self.table = QTableView()
        self.table.setAccessibleName("Результати учнів")
        self.model = LearnerTable(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.setMinimumHeight(230)
        self.table.setMinimumWidth(0)
        self.table.activated.connect(self._open_history)
        layout.addWidget(self.table)
        navigation = QHBoxLayout()
        self.previous = QPushButton("Попередня")
        self.next = QPushButton("Наступна")
        self.paging = _label()
        self.previous.clicked.connect(lambda: self.refresh(self.page - 1))
        self.next.clicked.connect(lambda: self.refresh(self.page + 1))
        self.open_details = QPushButton("Історія учня")
        self.open_details.clicked.connect(
            lambda: self._open_history(self.table.currentIndex())
        )
        for widget in (self.previous, self.paging, self.next, self.open_details):
            navigation.addWidget(widget)
        layout.addLayout(navigation)
        export = QHBoxLayout()
        self.exports = []
        for kind in ("csv", "json"):
            button = QPushButton(f"Експорт {kind.upper()}")
            button.clicked.connect(partial(self._export, kind))
            self.exports.append(button)
            export.addWidget(button)
        layout.addLayout(export)
        layout.addWidget(_label("Рекомендації викладачу · офлайн"))
        self.advice = _label()
        layout.addWidget(self.advice)

    def _detail_panel(self):
        self.detail_panel = QWidget()
        layout = QVBoxLayout(self.detail_panel)
        self.detail_selector = QComboBox()
        self.detail_selector.setAccessibleName("Спроба учня")
        self.detail_selector.setMinimumContentsLength(12)
        self.detail_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.detail_selector.currentIndexChanged.connect(self._render_attempt)
        self.detail_text = _label()
        self.detail_page = _label()
        self.detail_panel.setVisible(False)
        bar = QHBoxLayout()
        self.detail_previous = QPushButton("Попередні спроби")
        self.detail_next = QPushButton("Наступні спроби")
        self.detail_previous.clicked.connect(
            lambda: self._read_history(self.learner_id, self.history_page - 1)
        )
        self.detail_next.clicked.connect(
            lambda: self._read_history(self.learner_id, self.history_page + 1)
        )
        close = QPushButton("Закрити історію")
        close.clicked.connect(self._close_history)
        for widget in (self.detail_previous, self.detail_next, close):
            bar.addWidget(widget)
        layout.addLayout(bar)
        layout.addWidget(self.detail_page)
        layout.addWidget(self.detail_selector)
        layout.addWidget(self.detail_text)
        self.content.layout().addWidget(self.detail_panel)

    def _close_history(self):
        self.detail_generation += 1
        self.history = None
        self.detail_selector.clear()
        self.detail_text.clear()
        self.detail_page.clear()
        self.detail_panel.hide()

    def _clear_results(self):
        self.snapshot = self.access = None
        self._close_history()
        self.model.set_rows(())
        self.score_chart.set_values(())
        self.lifecycle_chart.set_values(())
        self.criterion_chart.set_series(())
        for label in (
            *self.cards,
            self.quality,
            self.scope_label,
            self.advice,
            self.paging,
        ):
            label.clear()
        self.content.hide()
        self.exporting = False
        for button in self.exports:
            button.setEnabled(True)

    def _cancel_requests(self):
        self.cancelled.set()
        self.cancelled = Event()
        self.generation += 1
        self.pool.clear()
        self.check_pending = False

    def invalidate(self):
        self.debounce.stop()
        self._cancel_requests()
        self.token = self.scenario_id = None
        self._clear_results()
        self._reset_filters()
        self.controls.hide()
        self.message.clear()
        self.title.setText("Аналіз сценарію")
        self.scenario_info.setText("Сценарій не вибрано.")

    def _reset_filters(self):
        self._choices(self.versions, "Усі опубліковані версії", ())
        self._choices(self.groups, "Усі дозволені групи", ())
        for combo in (self.status, self.aggregation, self.sort, self.direction):
            with QSignalBlocker(combo):
                combo.setCurrentIndex(0)
        with QSignalBlocker(self.search):
            self.search.clear()
        for toggle, edit in (
            (self.from_enabled, self.from_time),
            (self.to_enabled, self.to_time),
        ):
            with QSignalBlocker(toggle):
                toggle.setChecked(False)
            edit.setEnabled(False)

    def set_context(self, token, scenario_id):
        if (token, scenario_id) == (self.token, self.scenario_id):
            return
        self.invalidate()
        if token and scenario_id is not None:
            self.token, self.scenario_id = token, scenario_id
            self.controls.show()
            self.scenario_info.setText(f"Сценарій · ID {scenario_id}")
            self.refresh()

    def _submit(self, kind, operation):
        self.pool.start(
            _Worker(self.generation, kind, operation, self.cancelled, self.signals)
        )

    def _filters_changed(self, *_):
        if self.token is not None:
            self._cancel_requests()
            self._clear_results()
            self.debounce.start()

    @staticmethod
    def _utc_bound(enabled, edit):
        if enabled.isChecked():
            return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
                milliseconds=edit.dateTime().toMSecsSinceEpoch()
            )
        return None

    def _make_query(self, page):
        return AnalyticsQueryV1(
            scenario_id=self.scenario_id,
            publication_id=self.versions.currentData(),
            group_id=self.groups.currentData(),
            status=self.status.currentData(),
            aggregation=self.aggregation.currentData(),
            search=self.search.text(),
            sort=self.sort.currentData(),
            direction=self.direction.currentData(),
            started_from=self._utc_bound(self.from_enabled, self.from_time),
            started_to=self._utc_bound(self.to_enabled, self.to_time),
            page=page,
        )

    def refresh(self, page=1):
        if self.token is None:
            return
        self.debounce.stop()
        self._cancel_requests()
        self._clear_results()
        self.page = int(page or 1)
        try:
            query = self._make_query(self.page)
        except ValidationError:
            self.message.setText("Перевірте часові межі та фільтри.")
            return
        self.message.setText("Завантаження аналітики…")
        self._submit("summary", partial(self.service.load, self.token, query))

    def check_access(self):
        if self.snapshot is not None and not self.check_pending:
            self.check_pending = True
            self._submit(
                "access",
                partial(
                    self.service.check_access,
                    self.token,
                    self.snapshot.query,
                    self.access,
                ),
            )

    @Slot(int, str, object, str)
    def _done(self, generation, kind, output, error):
        if generation != self.generation or not self.token:
            return
        if self.service.accounts.sessions.get(self.token) is None:
            self.invalidate()
            return
        if kind == "access":
            self.check_pending = False
        if kind == "export":
            self.exporting = False
            for button in self.exports:
                button.setEnabled(True)
        if kind.startswith("details:") and kind != f"details:{self.detail_generation}":
            return
        if error:
            if kind in {"summary", "access"}:
                self._cancel_requests()
                self._clear_results()
                self._reset_filters()
                self.title.setText("Аналіз сценарію")
                self.scenario_info.setText(f"Сценарій · ID {self.scenario_id}")
            elif kind.startswith("details:"):
                self._close_history()
            self.message.setText(error)
        elif kind == "summary":
            self.snapshot, self.access = output
            self._render_snapshot()
        elif kind.startswith("details:"):
            self.history = output
            self._render_history()
        elif kind == "export":
            self.message.setText("Файл збережено.")

    @staticmethod
    def _choices(combo, label, options):
        selected = combo.currentData()
        with QSignalBlocker(combo):
            combo.clear()
            combo.addItem(label, None)
            for name, identifier in options:
                combo.addItem(name, identifier)
            combo.setCurrentIndex(max(0, combo.findData(selected)))

    def _render_snapshot(self):
        snap = self.snapshot
        scope, query, metrics = snap.scope, snap.query, snap.metrics
        self.title.setText(f"Аналіз · {scope.name}")
        self.scenario_info.setText(
            f"ID {query.scenario_id} · {LABELS[scope.status]} · "
            f"{_time(scope.created_at)}\n"
            f"{scope.topic} · {scope.difficulty}\nАудиторія · {scope.audience or '—'}"
        )
        self._choices(
            self.versions,
            "Усі опубліковані версії",
            (
                (f"Версія {p.version} · {_time(p.published_at)}", p.id)
                for p in scope.publications
            ),
        )
        self._choices(
            self.groups, "Усі дозволені групи", ((g.name, g.id) for g in scope.groups)
        )
        if not scope.publications:
            message = "Дані для аналізу відсутні. Немає опублікованих версій."
        elif not scope.groups:
            message = "Немає доступних груп із дозволом або історією."
        elif not metrics.lifecycle.total:
            message = "За вибраними фільтрами спроб немає."
        elif metrics.mean_score is None:
            message = "У вибраних спробах немає перевірених числових оцінок."
        else:
            message = ""
        self.message.setText(message)
        self.scope_label.setText(
            f"Знімок · {_time(snap.captured_at)}\n{self.versions.currentText()} · "
            f"{self.groups.currentText()} · {self.status.currentText()}\n"
            f"{self.aggregation.currentText()} · "
            f"Період {_time(query.started_from)} – {_time(query.started_to)}"
        )
        mean = display_percent(metrics.mean_score)
        web = display_percent(metrics.web_transition.percent)
        scores = metrics.scored_coverage
        transitions = metrics.web_transition
        values = (
            str(metrics.current_learners),
            f"Учні зі спробами {metrics.participating_learners} · "
            f"Завершили {metrics.completing_learners}",
            f"{mean + '%' if mean is not None else 'Немає даних'} · "
            f"{scores.numerator} із {scores.denominator}"
            + (
                f" · Описова середня для {metrics.scored_versions} версій"
                if metrics.scored_versions > 1
                else ""
            ),
            f"{web + '%' if web is not None else 'Немає даних'} · "
            f"{transitions.numerator} із {transitions.denominator}",
            _observations(metrics.observations),
            "Не налаштовано",
        )
        for card, value in zip(self.cards, values, strict=True):
            card.setText(value)
        self.quality.setText(
            f"Усі завершені · {_coverage(snap.quality.filtered)}\n"
            f"Вибрані завершені · {_coverage(snap.quality.selected)}\n"
            f"Пошкоджені дані порядку спроб · {snap.quality.ordering_errors}"
        )
        score_bins = ("[0,20)", "[20,40)", "[40,60)", "[60,80)", "[80,100]")
        self.score_chart.set_values(
            tuple(
                (name, count, scores.numerator)
                for name, count in zip(
                    score_bins, metrics.score_distribution, strict=True
                )
            )
            if scores.numerator
            else (),
            "Немає числових оцінок.",
        )
        life = metrics.lifecycle
        self.lifecycle_chart.set_values(
            tuple(
                (label, count, life.total)
                for label, count in zip(
                    ("Тривають", "Припинені", "Завершені"),
                    (life.in_progress, life.abandoned, life.completed),
                    strict=True,
                )
            )
            if life.total
            else (),
            "Немає спроб.",
        )
        self.criterion_chart.set_series(snap.criteria)
        self.model.set_rows(snap.rows)
        if snap.rows:
            self.table.selectRow(0)
        self.open_details.setEnabled(bool(snap.rows))
        page_count = max(
            1, (snap.total_learners + query.page_size - 1) // query.page_size
        )
        self.paging.setText(
            f"{query.page} із {page_count} · Учнів {snap.total_learners}"
        )
        self.previous.setEnabled(query.page > 1)
        self.next.setEnabled(query.page < page_count)
        self.advice.setText("\n\n".join(snap.recommendations))
        self.content.show()

    def _open_history(self, index):
        if self.snapshot is not None and index.isValid():
            self._read_history(self.model.rows[index.row()].learner_id, 1)
            # The shell places this page in a QScrollArea.
            self.reveal_details.emit(self.detail_panel)

    def _read_history(self, learner, page):
        if self.snapshot is None:
            return
        self._close_history()
        self.learner_id, self.history_page = learner, page
        self.detail_page.setText("Завантаження історії…")
        self.detail_selector.hide()
        self.detail_previous.setEnabled(False)
        self.detail_next.setEnabled(False)
        self.detail_panel.show()
        self._submit(
            f"details:{self.detail_generation}",
            partial(
                self.service.history,
                self.token,
                self.snapshot.query,
                HistoryQueryV1(learner_id=learner, page=page),
            ),
        )

    def _render_history(self):
        history = self.history
        self.detail_page.setText(
            f"{history.name} ({history.username})\n"
            f"Історія · {_time(history.captured_at)} · Спроб {history.total} · "
            f"Сторінка {self.history_page}"
        )
        self.detail_previous.setEnabled(self.history_page > 1)
        self.detail_next.setEnabled(history.total > self.history_page * 25)
        with QSignalBlocker(self.detail_selector):
            self.detail_selector.clear()
            for attempt in history.attempts:
                self.detail_selector.addItem(
                    f"{_time(attempt.started_at)} · {LABELS[attempt.activity]}"
                )
        self.detail_selector.setVisible(bool(history.attempts))
        self._render_attempt(self.detail_selector.currentIndex())

    def _render_attempt(self, index):
        if self.history is None or index < 0:
            self.detail_text.setText(
                "Спроб на цій сторінці немає." if self.history else ""
            )
            return
        attempt = self.history.attempts[index]
        parts = [
            f"Спроба {attempt.attempt_id}",
            f"Версія {attempt.publication.version} · "
            f"Публікація {attempt.publication.id} · Група {attempt.group.name}",
            f"Початок {_time(attempt.started_at)} · "
            f"Завершення {_time(attempt.completed_at)}",
            f"{LABELS[attempt.activity]} · "
            f"{_score(attempt.score, attempt.result_status)}",
        ]
        if attempt.result_id is not None:
            parts.append(
                f"Результат {attempt.result_id} · Рубрика {attempt.rubric_revision} · "
                f"{attempt.scoring_strategy}"
            )
        if attempt.web_not_applicable:
            parts.append("Web · Не застосовується")
        elif attempt.web_entered:
            parts.append("Web · Підтверджений вхід")
        parts.extend(
            f"{criterion.label} · {LABELS[criterion.outcome]}"
            for criterion in attempt.criteria
        )
        parts.extend(attempt.facts)
        if attempt.result_id is not None:
            parts.append(
                f"Підтвердження {attempt.observations.confirm} · "
                f"Синтетичні надсилання {attempt.observations.submit_synthetic} · "
                "Критична політика · Не налаштовано"
            )
        if attempt.feedback_status:
            parts.append(LABELS[attempt.feedback_status])
        parts.extend(attempt.feedback)
        self.detail_text.setText("\n".join(parts))

    def _export(self, kind):
        if self.snapshot is None or self.exporting:
            return
        generation = self.generation
        token, query = self.token, self.snapshot.query
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Зберегти аналітику",
            f"analytics-{query.scenario_id}.{kind}",
            f"{kind.upper()} (*.{kind})",
        )
        if not path or generation != self.generation:
            return
        self.exporting = True
        for button in self.exports:
            button.setEnabled(False)
        self._submit(
            "export",
            partial(
                self.service.export,
                token,
                query,
                path,
                kind,
                cancelled=self.cancelled.is_set,
            ),
        )
