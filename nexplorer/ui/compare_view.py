from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QPalette
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nexplorer.compare import BLOCKED, Row
from nexplorer.i18n import tr
from nexplorer.protocol import Entry
from nexplorer.ui.panes import format_size

_ARROWS = {"to-next": "→", "to-local": "←", None: ""}


def _states() -> dict[str, str]:
    return {
        "only-local": tr("Only on Local"),
        "only-next": tr("Only on the Next"),
        "different": tr("Different"),
        "identical": tr("Identical"),
        "conflict": tr("Conflict"),
        "invalid": tr("Invalid"),
        "ignored": tr("Ignored"),
        "hidden": tr("Hidden"),
    }


def _size(entry: Entry | None) -> str:
    return "" if entry is None or entry.is_dir else format_size(entry.size)


class CompareView(QWidget):
    """The Differences between the Local folder and the Next folder the panes showed."""

    transfer_requested = Signal(str)
    apply_requested = Signal()
    back_requested = Signal()

    def __init__(self):
        super().__init__()
        self._rows: list[Row] = []
        self._title = QLabel()
        self._title.setTextFormat(Qt.PlainText)
        self._tree = QTreeWidget()
        self._tree.setRootIsDecorated(False)
        self._tree.setHeaderLabels(["", tr("Name"), tr("Local"), tr("Direction"), tr("Next"), tr("State")])
        self._tree.itemChanged.connect(self._on_item_changed)
        self._reverse = QPushButton(tr("Reverse direction"))
        self._reverse.clicked.connect(self._reverse_selected)
        self._one = QPushButton(tr("Transfer this file"))
        self._one.clicked.connect(lambda: self._with_selected(self.transfer_requested.emit))
        self._apply = QPushButton(tr("Apply"))
        self._apply.clicked.connect(self.apply_requested)
        self._back = QPushButton(tr("Back to the panes"))
        self._back.clicked.connect(self.back_requested)
        buttons = QHBoxLayout()
        for b in (self._reverse, self._one, self._apply):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(self._back)
        col = QVBoxLayout(self)
        col.addWidget(self._title)
        col.addWidget(self._tree, 1)
        col.addLayout(buttons)

    def show_rows(self, title: str, rows: list[Row]) -> None:
        self._title.setText(title)
        self._rows = rows
        self._fill()

    def _fill(self) -> None:
        states = _states()
        self._tree.blockSignals(True)
        self._tree.clear()
        for r in self._rows:
            item = QTreeWidgetItem(
                ["", r.name, _size(r.local), _ARROWS[r.direction], _size(r.remote), states[r.state]]
            )
            if r.state in BLOCKED:
                self._mark_blocked(item, r.state)
            else:
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Checked if r.checked else Qt.Unchecked)
            self._tree.addTopLevelItem(item)
        self._tree.blockSignals(False)

    def _mark_blocked(self, item: QTreeWidgetItem, state: str) -> None:
        """Greyed rows the user cannot check; an invalid one also gets an error icon."""
        grey = QBrush(self.palette().color(QPalette.Disabled, QPalette.Text))
        for col in range(self._tree.columnCount()):
            item.setForeground(col, grey)
        if state in ("invalid", "conflict"):
            item.setIcon(5, self.style().standardIcon(QStyle.SP_MessageBoxCritical))

    def state_texts(self) -> dict[str, str]:
        return {r.name: self._tree.topLevelItem(i).text(5) for i, r in enumerate(self._rows)}

    def _on_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        self.row(item.text(1)).checked = item.checkState(0) == Qt.Checked

    def _with_selected(self, action) -> None:
        for item in self._tree.selectedItems():
            action(item.text(1))

    def _reverse_selected(self) -> None:
        self._with_selected(self.reverse)

    def row(self, name: str) -> Row:
        return next(r for r in self._rows if r.name == name)

    def rows(self) -> list[Row]:
        return self._rows

    def reverse(self, name: str) -> None:
        self.row(name).reverse()
        self._fill()

    def set_checked(self, name: str, checked: bool) -> None:
        self.row(name).checked = checked
        self._fill()

    def set_busy(self, busy: bool) -> None:
        self.setEnabled(not busy)
