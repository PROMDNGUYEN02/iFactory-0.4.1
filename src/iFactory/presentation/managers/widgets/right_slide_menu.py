"""
Optimized Right Slide Menu Widget.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Literal
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSpinBox,
    QProgressBar,
    QAbstractItemView,
    QDateEdit,
)
from .constants import STATUS_COLORS, DISPLAY_STATUS_MAP

__all__ = ["StatusSummaryRow", "InputHistoryRow", "SummaryRow", "SummaryTableWidget", "RightSlideMenuWidget", "STATUS_COLORS", "ViewMode"]
logger = logging.getLogger(__name__)
ViewMode = Literal["summary", "status_detail", "input_detail"]


@dataclass(slots=True)
class StatusSummaryRow:
    """Summary row for status history."""

    date: str = ""
    equip_code: str = ""
    running: float = 0.0
    shutdown: float = 0.0
    stop: float = 0.0
    maintenance: float = 0.0
    alarm: float = 0.0

    @property
    def total(self) -> float:
        return self.running + self.shutdown + self.stop + self.maintenance + self.alarm

    def to_row(self) -> List[str]:
        fmt = self._fmt_dur
        return [self.date, self.equip_code, fmt(self.running), fmt(self.shutdown), fmt(self.stop), fmt(self.maintenance), fmt(self.alarm)]

    @staticmethod
    def _fmt_dur(seconds: float) -> str:
        if seconds <= 0:
            return "-"
        s = int(seconds)
        (h, m, sec) = (s // 3600, s % 3600 // 60, s % 60)
        if h:
            return f"{h}h {m}m"
        if m:
            return f"{m}m {sec}s"
        return f"{sec}s"


@dataclass(slots=True)
class InputHistoryRow:
    """Row for input/feeding history."""

    timestamp: str = ""
    equip_code: str = ""
    material_batch: str = ""
    material_code: str = ""
    quantity: float = 0.0
    unit: str = ""

    def to_row(self) -> List[str]:
        qty = f"{self.quantity:.2f}" if self.quantity else "-"
        if self.unit:
            qty = f"{qty} {self.unit}"
        return [self.timestamp, self.equip_code, self.material_batch or "-", self.material_code or "-", qty]


SummaryRow = StatusSummaryRow


class SummaryTableWidget(QTableWidget):
    """Optimized summary table."""

    __slots__ = ("_status_col", "_mode", "_headers_cache")
    _SUMMARY_H = ("Date", "Device", "Running", "Shutdown", "Stop", "Maintenance", "Alarm")
    _INPUT_H = ("Time", "Device", "Batch", "Material", "Quantity")

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._status_col: Optional[int] = None
        self._mode: ViewMode = "summary"
        self._headers_cache: tuple = self._SUMMARY_H
        self._setup()

    def _setup(self) -> None:
        self.setObjectName("summaryTable")
        self.setColumnCount(len(self._SUMMARY_H))
        self.setHorizontalHeaderLabels(self._SUMMARY_H)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.setShowGrid(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def set_view_mode(self, mode: ViewMode) -> None:
        self._mode = mode
        headers = self._INPUT_H if mode == "input_detail" else self._SUMMARY_H
        if headers != self._headers_cache:
            self._headers_cache = headers
            self.setColumnCount(len(headers))
            self.setHorizontalHeaderLabels(headers)

    def set_status_column(self, col: int) -> None:
        self._status_col = col

    def load_summary_rows(self, rows: List[StatusSummaryRow]) -> None:
        self.setRowCount(len(rows))
        headers = self._headers_cache
        for row_idx, row_data in enumerate(rows):
            for col, val in enumerate(row_data.to_row()):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col >= 2 and val != "-":
                    color = STATUS_COLORS.get(headers[col].lower())
                    if color:
                        item.setForeground(QBrush(QColor(color)))
                self.setItem(row_idx, col, item)
        self.resizeColumnsToContents()

    def load_input_rows(self, rows: List[InputHistoryRow]) -> None:
        self.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col, val in enumerate(row_data.to_row()):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.setItem(row_idx, col, item)
        self.resizeColumnsToContents()

    def load_dict_rows(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            self.setRowCount(0)
            return
        headers = tuple(rows[0].keys())
        if headers != self._headers_cache:
            self._headers_cache = headers
            self.setColumnCount(len(headers))
            self.setHorizontalHeaderLabels(headers)
        self.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col, header in enumerate(headers):
                val = str(row_data.get(header, ""))
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if self._status_col == col:
                    internal = DISPLAY_STATUS_MAP.get(val, "unknown")
                    color = STATUS_COLORS.get(internal)
                    if color:
                        item.setForeground(QBrush(QColor(color)))
                self.setItem(row_idx, col, item)
        self.resizeColumnsToContents()


class RightSlideMenuWidget(QFrame):
    """Right slide menu with summary/detail tables."""

    __slots__ = (
        "_page_devices",
        "_current_page",
        "_current_devices",
        "_view_mode",
        "_current_device",
        "_history_type",
        "_title_label",
        "_subtitle_label",
        "_days_spin",
        "_refresh_btn",
        "_back_btn",
        "_loading_bar",
        "_table",
        "_info_label",
        "btn_close",
        "_date_edit",
    )
    closed = Signal()
    data_request = Signal(list, int)
    row_double_clicked = Signal(int, list)
    cold_data_request = Signal(str, str, object)
    _PAGE_TITLES = {
        "dashboard_page": "📊 Dashboard Summary",
        "orders_page": "📦 Orders Summary",
        "products_page": "🏭 Products Summary",
        "customers_page": "👥 Customers Summary",
        "reports_page": "📈 Reports Summary",
    }
    _BTN_STYLE = "\n        QPushButton {\n            border: none; border-radius: 14px;\n            font-size: 16px; font-weight: bold;\n        }\n        QPushButton:hover { background-color: rgba(100, 100, 100, 0.2); }\n    "
    _CLOSE_STYLE = "\n        QPushButton {\n            border: none; border-radius: 14px;\n            font-size: 16px; font-weight: bold;\n        }\n        QPushButton:hover { background-color: rgba(255, 0, 0, 0.1); color: #ff4444; }\n    "

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._page_devices: Dict[str, List[str]] = {}
        self._current_page = ""
        self._current_devices: List[str] = []
        self._view_mode: ViewMode = "summary"
        self._current_device: Optional[str] = None
        self._history_type = "status"
        self._setup_ui()
        self._connect_signals()

    def configure_page_devices(self, mapping: Dict[str, List[str]]) -> None:
        """
        Configure which devices belong to which page.

        This MUST be called during initialization to enable data loading.

        Args:
            mapping: {"dashboard_page": ["CCI01", "CCI02"], ...}

        Example:
            menu.configure_page_devices({
                "daboard_page": device_manager.get_all_device_ids(),
                "orders_page": ["CCI01", "CCI02", "CCI03"],
            })
        """
        self._page_devices = mapping.copy()
        logger.info(f"[RightSlideMenu] Configured {sum((len(v) for v in mapping.values()))} devices across {len(mapping)} pages")
        if self._current_page:
            self._current_devices = self._page_devices.get(self._current_page, [])

    def _setup_ui(self) -> None:
        self.setObjectName("rightSlideMenu")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        header = QFrame()
        header.setObjectName("rightMenuHeader")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(4, 4, 4, 4)
        h_layout.setSpacing(4)
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self._back_btn = QPushButton("←")
        self._back_btn.setObjectName("backBtn")
        self._back_btn.setFixedSize(28, 28)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.setToolTip("Back to summary")
        self._back_btn.setStyleSheet(self._BTN_STYLE)
        self._back_btn.hide()
        top_row.addWidget(self._back_btn)
        self._title_label = QLabel("📊 Summary")
        self._title_label.setObjectName("rightMenuTitle")
        self._title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        top_row.addWidget(self._title_label)
        top_row.addStretch()
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("rightMenuCloseBtn")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip("Close panel (Ctrl+R or Esc)")
        self.btn_close.setStyleSheet(self._CLOSE_STYLE)
        top_row.addWidget(self.btn_close)
        h_layout.addLayout(top_row)
        self._subtitle_label = QLabel("")
        self._subtitle_label.setObjectName("rightMenuSubtitle")
        self._subtitle_label.setStyleSheet("color: #888; font-size: 12px;")
        self._subtitle_label.hide()
        h_layout.addWidget(self._subtitle_label)
        layout.addWidget(header)
        controls = QFrame()
        controls.setObjectName("rightMenuControls")
        c_layout = QHBoxLayout(controls)
        c_layout.setContentsMargins(4, 4, 4, 4)
        c_layout.setSpacing(8)
        c_layout.addWidget(QLabel("Date:"))
        self._date_edit = QDateEdit()
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setFixedWidth(110)
        c_layout.addWidget(self._date_edit)
        c_layout.addStretch()
        self._refresh_btn = QPushButton("🔄 Refresh")
        self._refresh_btn.setObjectName("refreshBtn")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_layout.addWidget(self._refresh_btn)
        layout.addWidget(controls)
        self._loading_bar = QProgressBar()
        self._loading_bar.setObjectName("loadingBar")
        self._loading_bar.setRange(0, 0)
        self._loading_bar.setFixedHeight(3)
        self._loading_bar.hide()
        layout.addWidget(self._loading_bar)
        self._table = SummaryTableWidget()
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self._table, 1)
        footer = QFrame()
        footer.setObjectName("rightMenuFooter")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(4, 4, 4, 4)
        self._info_label = QLabel("Ready")
        self._info_label.setObjectName("rightMenuInfo")
        self._info_label.setStyleSheet("color: #888; font-size: 11px;")
        f_layout.addWidget(self._info_label)
        f_layout.addStretch()
        layout.addWidget(footer)

    def _connect_signals(self) -> None:
        self.btn_close.clicked.connect(self.closed.emit)
        self._refresh_btn.clicked.connect(self._on_refresh)
        self._back_btn.clicked.connect(self._on_back)

    def _on_back(self) -> None:
        self.set_view_mode("summary")
        self._on_refresh()

    def _on_refresh(self) -> None:
        """Handle refresh with validation."""
        if self._view_mode == "summary":
            if not self._current_devices:
                self._info_label.setText("⚠ No devices - configure first")
                return
            today = QDate.currentDate()
            selected = self._date_edit.date()
            days = max(1, min(abs(today.daysTo(selected)) + 1, 365))
            self.data_request.emit(self._current_devices, days)
        elif self._current_device:
            date_obj = self._date_edit.date().toPython()
            self.cold_data_request.emit(self._current_device, self._history_type, date_obj)

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        data = [self._table.item(row, c).text() if self._table.item(row, c) else "" for c in range(self._table.columnCount())]
        self.row_double_clicked.emit(row, data)

    def set_page_devices(self, mapping: Dict[str, List[str]]) -> None:
        """
        Set the mapping of page names to device codes.

        Args:
            mapping: Dict like {"dashboard_page": ["CCI01", "CCI02", ...]}
        """
        self._page_devices = mapping.copy()
        logger.info(f"[RightSlideMenu] Page devices mapping set: {list(mapping.keys())}")
        if self._current_page and self._current_page in self._page_devices:
            self._current_devices = self._page_devices[self._current_page]

    def register_page(self, page_name: str, device_codes: List[str]) -> None:
        """Register devices for a single page."""
        self._page_devices[page_name] = device_codes.copy()
        if page_name == self._current_page:
            self._current_devices = device_codes.copy()

    @property
    def has_page_devices(self) -> bool:
        """Check if any page has devices configured."""
        return any((bool(devices) for devices in self._page_devices.values()))

    def get_page_devices(self, page: Optional[str] = None) -> List[str]:
        """Get devices for a page (or current page if not specified)."""
        target_page = page or self._current_page
        return self._page_devices.get(target_page, []).copy()

    def set_view_mode(self, mode: ViewMode) -> None:
        self._view_mode = mode
        if mode == "summary":
            self._back_btn.hide()
            self._subtitle_label.hide()
            self._title_label.setText("📊 Summary")
        elif mode == "status_detail":
            self._back_btn.show()
            self._subtitle_label.show()
            self._title_label.setText("📋 Status History")
        elif mode == "input_detail":
            self._back_btn.show()
            self._subtitle_label.show()
            self._title_label.setText("📥 Input History")
        self._table.set_view_mode(mode)

    def show_device_history(self, device_code: str, history_type: str) -> None:
        self._current_device = device_code
        self._history_type = history_type
        self.set_view_mode("input_detail" if history_type == "input" else "status_detail")
        self._subtitle_label.setText(f"Device: {device_code}")

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def set_page(self, page: str) -> None:
        """Set current page and load its devices."""
        self._current_page = page
        self._current_devices = self._page_devices.get(page, [])
        self.set_view_mode("summary")
        self._current_device = None
        self.set_title(self._PAGE_TITLES.get(page, "📊 Summary"))
        if not self._current_devices:
            self._info_label.setText(f"⚠ No devices configured for {page}")
        else:
            self._info_label.setText(f"Ready ({len(self._current_devices)} devices)")

    def start_loading(self, message: str = "Loading...") -> None:
        self._loading_bar.show()
        self._info_label.setText(message)
        self._refresh_btn.setEnabled(False)

    def stop_loading(self) -> None:
        self._loading_bar.hide()
        self._refresh_btn.setEnabled(True)

    def load_summary_data(self, rows: List[StatusSummaryRow]) -> None:
        self._table.load_summary_rows(rows)
        self._info_label.setText(f"Loaded {len(rows)} records")

    def load_input_data(self, rows: List[InputHistoryRow]) -> None:
        self._table.load_input_rows(rows)
        self._info_label.setText(f"Loaded {len(rows)} records")

    def load_dict_rows(self, rows: List[Dict[str, Any]]) -> None:
        self._table.load_dict_rows(rows)
        self._info_label.setText(f"Loaded {len(rows)} records")

    def _get_field(self, data: Dict[str, Any], keys: List[str]) -> Any:
        """Try to get value from dict using multiple possible keys (case-insensitive)."""
        for key in keys:
            if key in data:
                return data[key]
            lower_key = key.lower()
            for k, v in data.items():
                if isinstance(k, str) and k.lower() == lower_key:
                    return v
        return None

    def load_from_history(self, records: List[Dict[str, Any]]) -> None:
        """Aggregate status history records."""
        if not records:
            self._table.setRowCount(0)
            self._info_label.setText("No data available")
            return
        summary_map: Dict[str, StatusSummaryRow] = {}
        for rec in records:
            equip = self._get_field(rec, ["equip_code", "EQUIP_CODE", "device_id"])
            start = self._get_field(rec, ["start_time", "START_TIME"])
            end = self._get_field(rec, ["end_time", "END_TIME"])
            status = str(self._get_field(rec, ["equip_status", "EQUIP_STATUS", "status", "STATUS", "0"]))
            if not start or not equip:
                continue
            date_str = start.strftime("%Y-%m-%d") if isinstance(start, datetime) else str(start)[:10]
            key = f"{date_str}|{equip}"
            if key not in summary_map:
                summary_map[key] = StatusSummaryRow(date=date_str, equip_code=equip)
            duration = 0.0
            if end and start:
                if isinstance(end, datetime) and isinstance(start, datetime):
                    duration = (end - start).total_seconds()
            row = summary_map[key]
            status_attr = {"1": "running", "2": "shutdown", "3": "stop", "4": "maintenance", "5": "alarm"}.get(status)
            if status_attr:
                setattr(row, status_attr, getattr(row, status_attr) + duration)
        sorted_rows = sorted(summary_map.values(), key=lambda r: (r.date, r.equip_code), reverse=True)
        self.load_summary_data(sorted_rows)

    def load_from_input_history(self, records: List[Dict[str, Any]]) -> None:
        """Load input history records."""
        if not records:
            self._table.setRowCount(0)
            self._info_label.setText("No data available")
            return
        rows = []
        for rec in records:
            ts = self._get_field(rec, ["FEEDING_TIME", "feeding_time", "timestamp"])
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, datetime) else str(ts)[:19]
            equip = self._get_field(rec, ["EQUIP_CODE", "equip_code", "device_id"])
            rows.append(
                InputHistoryRow(
                    timestamp=ts_str,
                    equip_code=equip or "",
                    material_batch=self._get_field(rec, ["MATERIAL_BATCH", "material_batch"]) or "",
                    material_code=self._get_field(rec, ["MATERIAL_CODE", "material_code"]) or "",
                    quantity=float(self._get_field(rec, ["QUANTITY", "quantity"]) or 0),
                    unit=self._get_field(rec, ["UNIT", "unit"]) or "",
                )
            )
        rows.sort(key=lambda r: r.timestamp, reverse=True)
        self.load_input_data(rows)

    def clear_rows(self) -> None:
        self._table.setRowCount(0)
        self._info_label.setText("Ready")

    def set_headers(self, headers: List[str]) -> None:
        if not headers:
            return
        headers_tuple = tuple(headers)
        if headers_tuple != self._table._headers_cache:
            self._table._headers_cache = headers_tuple
            self._table.setColumnCount(len(headers))
            self._table.setHorizontalHeaderLabels(headers)
            logger.debug("Headers set: %s", headers)

    def set_status_column(self, col: int) -> None:
        self._table.set_status_column(col)

    @property
    def current_devices(self) -> List[str]:
        """Get current devices list."""
        return self._current_devices.copy()

    @property
    def has_devices(self) -> bool:
        """Check if current page has devices."""
        return len(self._current_devices) > 0
