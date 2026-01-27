from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget, QStatusBar
from PySide6.QtCore import Qt

from iFactory.presentation.controllers.main_controller import MainController
from iFactory.presentation.components.device_canvas import DeviceCanvas
from iFactory.presentation.components.gantt_chart import GanttChart
from iFactory.presentation.components.legend_widget import LegendWidget


class MainWindow(QMainWindow):
    """
    Main Application Window.
    Composes the UI from components and binds them to the Controller.
    """

    def __init__(self, controller: MainController):
        super().__init__()
        self._controller = controller

        self.setWindowTitle("iFactory Monitor")
        self.resize(1024, 768)

        self._setup_ui()
        self._bind_events()

        # Initial Load
        self._controller.devices.start_auto_refresh()
        self._controller.devices.load_devices()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Header
        header = QHBoxLayout()
        title = QLabel("Factory Overview")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")

        self._refresh_btn = QPushButton("Sync Now")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._refresh_btn)

        layout.addLayout(header)

        # Legend
        layout.addWidget(LegendWidget())

        # Tabs
        self._tabs = QTabWidget()

        # Tab 1: Device Grid
        self._device_canvas = DeviceCanvas()
        self._tabs.addTab(self._device_canvas, "Device Status")

        # Tab 2: Timeline
        self._gantt_chart = GanttChart()
        self._tabs.addTab(self._gantt_chart, "Timeline Analysis")

        layout.addWidget(self._tabs)

        # Status Bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

    def _bind_events(self):
        # Button -> Controller
        self._refresh_btn.clicked.connect(self._controller.devices.trigger_sync)

        # Canvas -> Controller
        self._device_canvas.device_clicked.connect(self._on_device_selected)

        # Controller -> View
        self._controller.devices.devices_loaded.connect(self._device_canvas.update_devices)
        self._controller.devices.sync_finished.connect(self._on_sync_finished)

        self._controller.gantt.timeline_loaded.connect(self._on_timeline_loaded)

    def _on_device_selected(self, equipment_code: str):
        self._status_bar.showMessage(f"Selected: {equipment_code}")
        self._controller.gantt.select_device(equipment_code)
        self._tabs.setCurrentWidget(self._gantt_chart)

    def _on_sync_finished(self, success: bool):
        msg = "Sync Completed" if success else "Sync Failed"
        self._status_bar.showMessage(msg, 3000)

    def _on_timeline_loaded(self, vm):
        self._gantt_chart.set_data(vm.bars, vm.window_start, vm.window_end)
