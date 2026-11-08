from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nexplorer.compare import Row
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
        "not-scanned": tr("Not scanned"),
    }


def _size(entry: Entry | None) -> str:
    return "" if entry is None or entry.is_dir else format_size(entry.size)


class CompareView(QWidget):
    """The Differences between the Local folder and the Next folder the panes showed."""

    transfer_requested = Signal(str)
    apply_requested = Signal()
    back_requested = Signal()
    expand_requested = Signal(str)
    scan_all_requested = Signal()

    def __init__(self):
        super().__init__()
        self._rows: list[Row] = []
        self._title = QLabel()
        self._title.setTextFormat(Qt.PlainText)
        self._tree = QTreeWidget()
        self._tree.itemExpanded.connect(self._on_item_expanded)
        self._tree.setHeaderLabels(["", tr("Name"), tr("Local"), tr("Direction"), tr("Next"), tr("State")])
        self._tree.itemChanged.connect(self._on_item_changed)
        self._reverse = QPushButton(tr("Reverse direction"))
        self._reverse.clicked.connect(self._reverse_selected)
        self._one = QPushButton(tr("Transfer this file"))
        self._one.clicked.connect(lambda: self._with_selected(self.transfer_requested.emit))
        self._scan_all = QPushButton(tr("Scan all"))
        self._scan_all.clicked.connect(self.scan_all_requested)
        self._apply = QPushButton(tr("Apply"))
        self._apply.clicked.connect(self.apply_requested)
        self._back = QPushButton(tr("Back to the panes"))
        self._back.clicked.connect(self.back_requested)
        buttons = QHBoxLayout()
        for b in (self._reverse, self._one, self._scan_all, self._apply):
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
        self._tree.blockSignals(True)
        expanded = self._expanded_paths()
        self._tree.clear()
        self._add_rows(self._tree.invisibleRootItem(), self._rows, "", expanded)
        self._tree.blockSignals(False)

    def _expanded_paths(self) -> set[str]:
        found = set()
        stack = [self._tree.topLevelItem(i) for i in range(self._tree.topLevelItemCount())]
        while stack:
            item = stack.pop()
            if item.isExpanded():
                found.add(item.data(1, Qt.UserRole))
            stack += [item.child(i) for i in range(item.childCount())]
        return found

    def _add_rows(self, parent, rows: list[Row], prefix: str, expanded: set[str]) -> None:
        states = _states()
        for r in rows:
            path = prefix + r.name
            item = QTreeWidgetItem(
                ["", r.name, _size(r.local), _ARROWS[r.direction], _size(r.remote), states[r.state]]
            )
            item.setData(1, Qt.UserRole, path)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked if r.checked else Qt.Unchecked)
            parent.addChild(item)
            if r.state == "not-scanned" and r.children is None:
                item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            if r.children is not None:
                self._add_rows(item, r.children, path + "/", expanded)
                item.setExpanded(path in expanded)

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        path = item.data(1, Qt.UserRole)
        row = self.row(path)
        if row.children is None and row.state == "not-scanned":
            self.expand_requested.emit(path)

    def _on_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        self.row(item.data(1, Qt.UserRole)).checked = item.checkState(0) == Qt.Checked

    def _with_selected(self, action) -> None:
        for item in self._tree.selectedItems():
            action(item.data(1, Qt.UserRole))

    def _reverse_selected(self) -> None:
        self._with_selected(self.reverse)

    def row(self, path: str) -> Row:
        """A row by its name, or by its path ("games/deep") below an expanded folder."""
        rows, found = self._rows, None
        for part in path.split("/"):
            found = next(r for r in rows if r.name == part)
            rows = found.children or []
        return found

    def refresh(self) -> None:
        self._fill()

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
