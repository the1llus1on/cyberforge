"""Accessible native Qt bar charts of immutable snapshot series."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QGroupBox, QLabel, QProgressBar, QVBoxLayout

from cyberforge.analytics.contracts import display_percent


class BarChart(QGroupBox):
    def __init__(self, title, rows):
        super().__init__(title)
        self.setAccessibleName(title)
        layout = QVBoxLayout(self)
        self.empty = QLabel()
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)
        self.bars = []
        for _ in range(rows):
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(bar)
            self.bars.append(bar)
        self.set_values(())

    def set_values(self, values, empty="Немає даних."):
        self.empty.setText(empty)
        self.empty.setVisible(not values)
        for index, bar in enumerate(self.bars):
            bar.setVisible(index < len(values))
            if index < len(values):
                name, count, denominator = values[index]
                label = f"{name} · {count} із {denominator}"
                bar.setValue(round(1000 * count / denominator) if denominator else 0)
                bar.setFormat(label)
                bar.setAccessibleName(label)
            else:
                bar.reset()
                bar.setFormat("")
                bar.setAccessibleName("")


class CriterionChart(QGroupBox):
    def __init__(self):
        super().__init__("Результати сумісних критеріїв")
        layout = QVBoxLayout(self)
        self.selector = QComboBox()
        self.selector.setAccessibleName("Серія критеріїв")
        self.selector.setMinimumContentsLength(12)
        self.selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.selector.currentIndexChanged.connect(self._show_series)
        layout.addWidget(self.selector)
        self.chart = BarChart("Виконання критерію", 2)
        layout.addWidget(self.chart)
        self.coverage = QLabel()
        self.coverage.setWordWrap(True)
        layout.addWidget(self.coverage)
        self.series = ()

    def set_series(self, series):
        self.series = series
        self.selector.blockSignals(True)
        self.selector.clear()
        for entry in series:
            key = entry.key
            self.selector.addItem(
                f"В. {key.scenario_version} · Р. {key.rubric_revision} · {entry.label}"
            )
        self.selector.blockSignals(False)
        self.selector.setVisible(bool(series))
        self._show_series(self.selector.currentIndex())

    def _show_series(self, index):
        self.coverage.clear()
        if index < 0 or index >= len(self.series):
            self.chart.set_values((), "Немає перевірених критеріїв.")
            return
        entry = self.series[index]
        rate = entry.met_rate
        values = (
            ("Виконано", entry.met, rate.denominator),
            ("Не виконано", entry.not_met, rate.denominator),
        )
        self.chart.set_values(
            values if rate.denominator else (), "Немає застосовних числових критеріїв."
        )
        met = display_percent(rate.percent)
        not_met = display_percent(entry.not_met_rate.percent)
        rate_label = (
            f"Виконано {met}% · Не виконано {not_met}%\n" if met is not None else ""
        )
        key = entry.key
        context = f"Версія {key.scenario_version} · Рубрика {key.rubric_revision}"
        if key.criterion_id == "transition.safe_decline":
            context += f" · Безпечна відмова {met + '%' if met is not None else '—'}"
        self.coverage.setText(
            f"{context}\n{rate_label}Числових {rate.denominator} із {entry.verified} · "
            f"Незастосовних {entry.not_applicable} · Описових {entry.descriptive}"
        )
