from PySide6.QtCore import QObject

from .device_controller import DeviceController
from .gantt_controller import GanttController


class MainController(QObject):
    """
    Root Controller/Orchestrator.
    Coordinates interaction between sub-controllers if needed.
    """

    def __init__(self, device_controller: DeviceController, gantt_controller: GanttController, parent=None):
        super().__init__(parent)
        self.devices = device_controller
        self.gantt = gantt_controller

        # Example orchestration: When device selected in grid, load gantt
        # Note: In pure decoupling, this might happen in the View or via shared state,
        # but the Controller is a valid place for flow logic.
        pass
