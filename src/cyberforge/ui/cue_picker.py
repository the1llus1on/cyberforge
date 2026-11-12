"""Checkable desired-cue selector; IDs, never translated labels, are persisted."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidgetItem

from cyberforge.domain.nist_cues import CUES, NistCueId
from cyberforge.ui.admin_page import MembershipPicker


class CuePicker(MembershipPicker):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setAccessibleName("Бажані ознаки NIST для листа")
        self.setFixedHeight(220)
        self.setWordWrap(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for cue in CUES:
            item = QListWidgetItem(f"{cue.id} · {cue.label}")
            item.setData(Qt.ItemDataRole.UserRole, cue.id.value)
            item.setToolTip(
                f"{cue.cue_type.label} ({cue.cue_type.source_name})\n"
                f"{cue.source_name}\nNIST TN 2276, Appendix {cue.id}"
            )
            item.setFlags(
                (item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                & ~Qt.ItemFlag.ItemIsSelectable
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            self.addItem(item)
        self.itemChanged.connect(lambda _: self.changed.emit())

    def selected(self) -> tuple[NistCueId, ...]:
        return tuple(
            NistCueId(self.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.count())
            if self.item(i).checkState() == Qt.CheckState.Checked
        )

    def set_selected(self, values: tuple[NistCueId, ...]) -> None:
        for index in range(self.count()):
            item = self.item(index)
            item.setCheckState(
                Qt.CheckState.Checked
                if item.data(Qt.ItemDataRole.UserRole) in values
                else Qt.CheckState.Unchecked
            )

    def set_read_only(self, read_only: bool) -> None:
        # Keep scrolling/tooltips/keyboard navigation available during inspection.
        for index in range(self.count()):
            item = self.item(index)
            flags = item.flags()
            item.setFlags(
                flags & ~Qt.ItemFlag.ItemIsUserCheckable
                if read_only
                else flags | Qt.ItemFlag.ItemIsUserCheckable
            )
