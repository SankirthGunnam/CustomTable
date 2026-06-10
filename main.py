from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPoint, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QStyle,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

COLUMN_GAP = 20
SOURCE_COLS = 3
COLUMN_COUNT = 6

COLUMN_KEYS = (
    "source_type",
    "source_device",
    "source_pin",
    "target_type",
    "target_device",
    "target_pin",
)

SUBHEADER_LABELS = ("Type", "Device", "Pin")

ARROW_COLOR = QColor(55, 55, 55)

ROW0_HEADER_HEIGHT = 26
ROW1_HEADER_HEIGHT = 28

FILTER_ALL = ""


def side_matches_filter(
    row: dict[str, str | None],
    prefix: str,
    device_type: str | None,
    device: str | None,
    pin: str | None,
) -> bool:
    if device_type and row.get(f"{prefix}_type") != device_type:
        return False
    if device and row.get(f"{prefix}_device") != device:
        return False
    if pin and row.get(f"{prefix}_pin") != pin:
        return False
    return True


def row_matches_filter(
    row: dict[str, str | None],
    device_type: str | None,
    device: str | None,
    pin: str | None,
) -> bool:
    if not device_type and not device and not pin:
        return True
    return side_matches_filter(row, "source", device_type, device, pin) or side_matches_filter(
        row, "target", device_type, device, pin
    )


def should_swap_for_display(
    row: dict[str, str | None],
    device_type: str | None,
    device: str | None,
    pin: str | None,
) -> bool:
    if not device_type and not device and not pin:
        return False
    if side_matches_filter(row, "source", device_type, device, pin):
        return False
    return side_matches_filter(row, "target", device_type, device, pin)


def column_key_for_row(
    row: dict[str, str | None],
    column: int,
    device_type: str | None,
    device: str | None,
    pin: str | None,
) -> str:
    if should_swap_for_display(row, device_type, device, pin):
        swapped_keys = (
            "target_type",
            "target_device",
            "target_pin",
            "source_type",
            "source_device",
            "source_pin",
        )
        return swapped_keys[column]
    return COLUMN_KEYS[column]


def unique_types(rows: list[dict[str, str | None]]) -> list[str]:
    types: set[str] = set()
    for row in rows:
        if row.get("source_type"):
            types.add(row["source_type"])
        if row.get("target_type"):
            types.add(row["target_type"])
    return sorted(types)


def devices_for_type(rows: list[dict[str, str | None]], device_type: str) -> list[str]:
    devices: set[str] = set()
    for row in rows:
        if row.get("source_type") == device_type and row.get("source_device"):
            devices.add(row["source_device"])
        if row.get("target_type") == device_type and row.get("target_device"):
            devices.add(row["target_device"])
    return sorted(devices)


def pins_for_device(
    rows: list[dict[str, str | None]], device_type: str, device: str
) -> list[str]:
    pins: set[str] = set()
    for row in rows:
        if row.get("source_type") == device_type and row.get("source_device") == device:
            if row.get("source_pin"):
                pins.add(row["source_pin"])
        if row.get("target_type") == device_type and row.get("target_device") == device:
            if row.get("target_pin"):
                pins.add(row["target_pin"])
    return sorted(pins)


class Model(QAbstractTableModel):
    def __init__(self, rows: list[dict[str, str | None]]):
        super().__init__()
        self.all_data = rows
        self.visible_indices = list(range(len(rows)))
        self._filter_type: str | None = None
        self._filter_device: str | None = None
        self._filter_pin: str | None = None

    def rowCount(self, parent=QModelIndex()):
        return len(self.visible_indices)

    def columnCount(self, parent=QModelIndex()):
        return COLUMN_COUNT

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            row = self.all_data[self.visible_indices[index.row()]]
            key = column_key_for_row(
                row,
                index.column(),
                self._filter_type,
                self._filter_device,
                self._filter_pin,
            )
            return row.get(key)
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return SUBHEADER_LABELS[section % SOURCE_COLS]
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.EditRole:
            actual_row = self.visible_indices[index.row()]
            row = self.all_data[actual_row]
            key = column_key_for_row(
                row,
                index.column(),
                self._filter_type,
                self._filter_device,
                self._filter_pin,
            )
            row[key] = value
            self.dataChanged.emit(
                index,
                index,
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
            )
            return True
        return False

    def apply_filters(
        self,
        device_type: str | None = None,
        device: str | None = None,
        pin: str | None = None,
    ) -> None:
        self._filter_type = device_type
        self._filter_device = device
        self._filter_pin = pin
        self.beginResetModel()
        self.visible_indices = [
            i
            for i, row in enumerate(self.all_data)
            if row_matches_filter(row, device_type, device, pin)
        ]
        self.endResetModel()

    def addRow(self):
        row_index = len(self.all_data)
        self.beginInsertRows(QModelIndex(), row_index, row_index)
        self.all_data.append({key: None for key in COLUMN_KEYS})
        self.visible_indices.append(row_index)
        self.endInsertRows()


def section_positions_from_widths(widths: list[int]) -> list[tuple[int, int]]:
    positions = []
    x = 0
    for w in widths:
        positions.append((x, w))
        x += w
    return positions


def gap_x(section_positions: list[tuple[int, int]]) -> int:
    return section_positions[2][0] + section_positions[2][1]


def column_x(section_positions: list[tuple[int, int]], col: int) -> int:
    x, _ = section_positions[col]
    if col >= SOURCE_COLS:
        x += COLUMN_GAP
    return x


def block_width(section_positions: list[tuple[int, int]], start: int, count: int) -> int:
    return sum(section_positions[start + i][1] for i in range(count))


class HeaderView(QHeaderView):
    def __init__(self, orientation: Qt.Orientation, parent: QWidget):
        super().__init__(orientation, parent)
        self.setSectionsClickable(True)
        self.setFixedHeight(ROW0_HEADER_HEIGHT + ROW1_HEADER_HEIGHT)

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), ROW0_HEADER_HEIGHT + ROW1_HEADER_HEIGHT)

    def paintEvent(self, event: QPaintEvent):
        del event
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        widths = [self.sectionSize(i) for i in range(COLUMN_COUNT)]
        section_positions = section_positions_from_widths(widths)
        h0 = ROW0_HEADER_HEIGHT

        src_w = block_width(section_positions, 0, SOURCE_COLS)
        tgt_left = column_x(section_positions, SOURCE_COLS)
        tgt_w = block_width(section_positions, SOURCE_COLS, SOURCE_COLS)

        self._draw_cell(painter, QRect(0, 0, src_w, h0), "Source")
        self._draw_cell(painter, QRect(tgt_left, 0, tgt_w, h0), "Target")

        for i in range(COLUMN_COUNT):
            x_pos = column_x(section_positions, i)
            _, w = section_positions[i]
            rect = QRect(x_pos, h0, w, ROW1_HEADER_HEIGHT)
            label = self.model().headerData(
                i, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            )
            self._draw_cell(painter, rect, label or "", bold=False)

    def _draw_cell(self, painter: QPainter, rect: QRect, text: str, *, bold: bool = True) -> None:
        painter.fillRect(rect, self.palette().button())
        painter.setPen(self.palette().color(QPalette.ColorRole.Mid))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        if not text:
            return
        font = QFont(self.font())
        font.setBold(bold)
        painter.setFont(font)
        painter.setPen(self.palette().color(QPalette.ColorRole.ButtonText))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)


class CustomTableView(QTableView):
    def __init__(self, model: Model):
        super().__init__()
        self.setModel(model)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setHorizontalHeader(HeaderView(Qt.Orientation.Horizontal, self))
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )

    def visualRect(self, index: QModelIndex) -> QRect:
        if not index.isValid():
            return QRect()
        return self._cell_rect(index.row(), index.column(), self._section_positions())

    def indexAt(self, pos: QPoint) -> QModelIndex:
        section_positions = self._section_positions()
        model = self.model()
        for row in range(model.rowCount()):
            for col in range(COLUMN_COUNT):
                if self._cell_rect(row, col, section_positions).contains(pos):
                    return model.index(row, col)
        return QModelIndex()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_columns_to_fill()

    def showEvent(self, event):
        super().showEvent(event)
        self._resize_columns_to_fill()

    def _resize_columns_to_fill(self) -> None:
        if self.model() is None:
            return
        viewport_w = self.viewport().width()
        usable = max(viewport_w - COLUMN_GAP, COLUMN_COUNT)
        base_w = usable // COLUMN_COUNT
        remainder = usable - base_w * COLUMN_COUNT
        for col in range(COLUMN_COUNT):
            self.setColumnWidth(col, base_w + (1 if col < remainder else 0))

    def _section_positions(self) -> list[tuple[int, int]]:
        widths = [self.columnWidth(col) for col in range(COLUMN_COUNT)]
        return section_positions_from_widths(widths)

    def _cell_rect(self, row: int, col: int, section_positions: list[tuple[int, int]]) -> QRect:
        _, w = section_positions[col]
        base = super().visualRect(self.model().index(row, col))
        return QRect(column_x(section_positions, col), base.y(), w, base.height())

    def _row_fill_color(self, row: int) -> QColor:
        role = QPalette.ColorRole.AlternateBase if row % 2 == 1 else QPalette.ColorRole.Base
        return self.palette().color(role)

    def _draw_cell_border(self, painter: QPainter, rect: QRect) -> None:
        pen = QPen(self.palette().color(QPalette.ColorRole.Mid))
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

    def paintEvent(self, event: QPaintEvent):
        del event
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        section_positions = self._section_positions()
        gx = gap_x(section_positions)

        for row in range(self.model().rowCount()):
            row_color = self._row_fill_color(row)
            row_top = super().visualRect(self.model().index(row, 0)).y()
            row_h = self.rowHeight(row)

            gap_rect = QRect(gx, row_top, COLUMN_GAP, row_h)
            painter.fillRect(gap_rect, row_color)
            self._paint_arrow_in_gutter(painter, gap_rect)

            for col in range(COLUMN_COUNT):
                rect = self._cell_rect(row, col, section_positions)
                painter.fillRect(rect, row_color)
                index = self.model().index(row, col)
                option = QStyleOptionViewItem()
                option.initFrom(self)
                option.rect = rect
                option.index = index
                if self.selectionModel().isSelected(index):
                    option.state |= QStyle.StateFlag.State_Selected
                if index == self.currentIndex():
                    option.state |= QStyle.StateFlag.State_HasFocus
                self.itemDelegateForIndex(index).paint(painter, option, index)
                self._draw_cell_border(painter, rect)

    def _paint_arrow_in_gutter(self, painter: QPainter, rect: QRect) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        inner = QRectF(rect).adjusted(5.0, 0.0, -5.0, 0.0)
        cy = inner.center().y()
        tip_x = inner.right()
        tail_x = inner.left()
        head_len = 7.0
        head_half_h = 4.5
        shaft_end = tip_x - head_len

        pen = QPen(ARROW_COLOR)
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(QPointF(tail_x, cy), QPointF(shaft_end, cy))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ARROW_COLOR)
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(tip_x, cy),
                    QPointF(shaft_end, cy - head_half_h),
                    QPointF(shaft_end, cy + head_half_h),
                ]
            )
        )
        painter.restore()


class FilterBar(QWidget):
    def __init__(self, model: Model, parent: QWidget | None = None):
        super().__init__(parent)
        self._model = model
        self._updating = False

        self.type_combo = QComboBox()
        self.device_combo = QComboBox()
        self.pin_combo = QComboBox()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.addWidget(QLabel("Type:"))
        layout.addWidget(self.type_combo, stretch=1)
        layout.addWidget(QLabel("Device:"))
        layout.addWidget(self.device_combo, stretch=2)
        layout.addWidget(QLabel("Pin:"))
        layout.addWidget(self.pin_combo, stretch=1)

        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        self.device_combo.currentTextChanged.connect(self._on_device_changed)
        self.pin_combo.currentTextChanged.connect(self._on_pin_changed)

        self._populate_types()

    def _populate_types(self) -> None:
        self._set_combo_items(self.type_combo, unique_types(self._model.all_data))

    def _populate_devices(self, device_type: str) -> None:
        devices = devices_for_type(self._model.all_data, device_type) if device_type else []
        self._set_combo_items(self.device_combo, devices)

    def _populate_pins(self, device_type: str, device: str) -> None:
        pins = (
            pins_for_device(self._model.all_data, device_type, device)
            if device_type and device
            else []
        )
        self._set_combo_items(self.pin_combo, pins)

    def _set_combo_items(self, combo: QComboBox, items: list[str]) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All", FILTER_ALL)
        for item in items:
            combo.addItem(item, item)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _selected_value(self, combo: QComboBox) -> str | None:
        value = combo.currentData()
        return value if value else None

    def _apply_filters(self) -> None:
        if self._updating:
            return
        self._model.apply_filters(
            self._selected_value(self.type_combo),
            self._selected_value(self.device_combo),
            self._selected_value(self.pin_combo),
        )

    def _on_type_changed(self, _text: str) -> None:
        self._updating = True
        device_type = self._selected_value(self.type_combo)
        self._populate_devices(device_type or "")
        self._populate_pins(device_type or "", self._selected_value(self.device_combo) or "")
        self._updating = False
        self._apply_filters()

    def _on_device_changed(self, _text: str) -> None:
        self._updating = True
        device_type = self._selected_value(self.type_combo) or ""
        device = self._selected_value(self.device_combo) or ""
        self._populate_pins(device_type, device)
        self._updating = False
        self._apply_filters()

    def _on_pin_changed(self, _text: str) -> None:
        self._apply_filters()


SAMPLE_DATA: list[dict[str, str | None]] = [
    # ANT devices: Antenna 1–6, Roof Antenna, GPS Antenna
    {
        "source_type": "ANT",
        "source_device": "Antenna 1",
        "source_pin": "IN",
        "target_type": "FEM",
        "target_device": "Device 1",
        "target_pin": "OUT",
    },
    {
        "source_type": "ANT",
        "source_device": "Antenna 1",
        "source_pin": "OUT",
        "target_type": "COUPLER",
        "target_device": "SAMPLE_COUPLER",
        "target_pin": "IN",
    },
    {
        "source_type": "FEM",
        "source_device": "Device 1",
        "source_pin": "OUT",
        "target_type": "COUPLER",
        "target_device": "SAMPLE_COUPLER",
        "target_pin": "IN",
    },
    {
        "source_type": "COUPLER",
        "source_device": "SAMPLE_COUPLER",
        "source_pin": "IN",
        "target_type": "ANT",
        "target_device": "Antenna 2",
        "target_pin": "OUT",
    },
    {
        "source_type": "ANT",
        "source_device": "Antenna 2",
        "source_pin": "IN",
        "target_type": "FEM",
        "target_device": "Device 2",
        "target_pin": "OUT",
    },
    {
        "source_type": "FEM",
        "source_device": "QORVOQM77180",
        "source_pin": "IN",
        "target_type": "LNA",
        "target_device": "QORVOQM77180",
        "target_pin": "OUT",
    },
    {
        "source_type": "LNA",
        "source_device": "QORVOQM77180",
        "source_pin": "OUT",
        "target_type": "FEM",
        "target_device": "Device 2",
        "target_pin": "IN",
    },
    {
        "source_type": "FEM",
        "source_device": "Device 2",
        "source_pin": "IN",
        "target_type": "COUPLER",
        "target_device": "MAIN_COUPLER",
        "target_pin": "OUT",
    },
    {
        "source_type": "COUPLER",
        "source_device": "MAIN_COUPLER",
        "source_pin": "OUT",
        "target_type": "ANT",
        "target_device": "Antenna 3",
        "target_pin": "IN",
    },
    {
        "source_type": "ANT",
        "source_device": "Antenna 3",
        "source_pin": "IN",
        "target_type": "FEM",
        "target_device": "Device 3",
        "target_pin": "OUT",
    },
    {
        "source_type": "FEM",
        "source_device": "Device 3",
        "source_pin": "IN",
        "target_type": "COUPLER",
        "target_device": "BRANCH_COUPLER",
        "target_pin": "OUT",
    },
    {
        "source_type": "COUPLER",
        "source_device": "BRANCH_COUPLER",
        "source_pin": "OUT",
        "target_type": "ANT",
        "target_device": "Antenna 4",
        "target_pin": "IN",
    },
    {
        "source_type": "ANT",
        "source_device": "Antenna 4",
        "source_pin": "OUT",
        "target_type": "FEM",
        "target_device": "SKY77643",
        "target_pin": "IN",
    },
    {
        "source_type": "FEM",
        "source_device": "SKY77643",
        "source_pin": "OUT",
        "target_type": "LNA",
        "target_device": "SKY67151",
        "target_pin": "IN",
    },
    {
        "source_type": "LNA",
        "source_device": "SKY67151",
        "source_pin": "OUT",
        "target_type": "FEM",
        "target_device": "QPF7218",
        "target_pin": "IN",
    },
    {
        "source_type": "FEM",
        "source_device": "QPF7218",
        "source_pin": "OUT",
        "target_type": "COUPLER",
        "target_device": "HYBRID_COUPLER",
        "target_pin": "IN",
    },
    {
        "source_type": "COUPLER",
        "source_device": "HYBRID_COUPLER",
        "source_pin": "OUT",
        "target_type": "ANT",
        "target_device": "Antenna 5",
        "target_pin": "IN",
    },
    {
        "source_type": "ANT",
        "source_device": "Antenna 5",
        "source_pin": "IN",
        "target_type": "LNA",
        "target_device": "BGA725L6",
        "target_pin": "OUT",
    },
    {
        "source_type": "LNA",
        "source_device": "BGA725L6",
        "source_pin": "IN",
        "target_type": "FEM",
        "target_device": "Device 4",
        "target_pin": "OUT",
    },
    {
        "source_type": "FEM",
        "source_device": "Device 4",
        "source_pin": "IN",
        "target_type": "COUPLER",
        "target_device": "SAMPLE_COUPLER",
        "target_pin": "OUT",
    },
    {
        "source_type": "COUPLER",
        "source_device": "SAMPLE_COUPLER",
        "source_pin": "IN",
        "target_type": "ANT",
        "target_device": "Roof Antenna",
        "target_pin": "OUT",
    },
    {
        "source_type": "ANT",
        "source_device": "Roof Antenna",
        "source_pin": "IN",
        "target_type": "FEM",
        "target_device": "Device 5",
        "target_pin": "OUT",
    },
    {
        "source_type": "FEM",
        "source_device": "Device 5",
        "source_pin": "OUT",
        "target_type": "LNA",
        "target_device": "QORVOQM13002",
        "target_pin": "IN",
    },
    {
        "source_type": "LNA",
        "source_device": "QORVOQM13002",
        "source_pin": "OUT",
        "target_type": "COUPLER",
        "target_device": "MAIN_COUPLER",
        "target_pin": "IN",
    },
    {
        "source_type": "COUPLER",
        "source_device": "MAIN_COUPLER",
        "source_pin": "OUT",
        "target_type": "ANT",
        "target_device": "GPS Antenna",
        "target_pin": "IN",
    },
    {
        "source_type": "ANT",
        "source_device": "GPS Antenna",
        "source_pin": "OUT",
        "target_type": "FEM",
        "target_device": "QORVOQM77180",
        "target_pin": "IN",
    },
    {
        "source_type": "LNA",
        "source_device": "QORVOQM13002",
        "source_pin": "IN",
        "target_type": "FEM",
        "target_device": "SKY77643",
        "target_pin": "OUT",
    },
    {
        "source_type": "FEM",
        "source_device": "QORVOQM77180",
        "source_pin": "OUT",
        "target_type": "LNA",
        "target_device": "BGA725L6",
        "target_pin": "IN",
    },
    {
        "source_type": "COUPLER",
        "source_device": "BRANCH_COUPLER",
        "source_pin": "IN",
        "target_type": "ANT",
        "target_device": "Antenna 6",
        "target_pin": "OUT",
    },
    {
        "source_type": "ANT",
        "source_device": "Antenna 6",
        "source_pin": "IN",
        "target_type": "COUPLER",
        "target_device": "HYBRID_COUPLER",
        "target_pin": "OUT",
    },
]


def main():
    app = QApplication([])
    model = Model(SAMPLE_DATA)
    view = CustomTableView(model)
    filter_bar = FilterBar(model)

    central = QWidget()
    layout = QVBoxLayout(central)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(filter_bar)
    layout.addWidget(view)

    window = QMainWindow()
    window.setWindowTitle("Device mapping table")
    window.setCentralWidget(central)
    window.resize(1100, 520)
    window.show()
    return app.exec()


if __name__ == "__main__":
    main()
