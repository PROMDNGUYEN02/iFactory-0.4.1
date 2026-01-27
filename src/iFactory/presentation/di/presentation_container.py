from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
from iFactory.application.ports.remote_data_source import IRemoteDataSource
from iFactory.application.use_cases.queries.device_queries import DeviceQueries
from iFactory.application.use_cases.queries.production_queries import ProductionQueries
from iFactory.application.use_cases.commands.sync_commands import SyncDevicesCommand

from iFactory.presentation.controllers.main_controller import MainController
from iFactory.presentation.controllers.device_controller import DeviceController
from iFactory.presentation.controllers.gantt_controller import GanttController
from iFactory.presentation.adapters.async_executor import AsyncExecutor


class PresentationContainer:
    """
    Manual Dependency Injection Container for the Presentation Layer.
    Wires Application Use Cases into Controllers.
    """

    def __init__(self, uow: AbstractUnitOfWork, remote_source: IRemoteDataSource):
        self._uow = uow
        self._remote = remote_source
        self._executor = AsyncExecutor()

    def resolve_main_controller(self) -> MainController:
        # Resolve Use Cases
        device_queries = DeviceQueries(self._uow)
        production_queries = ProductionQueries(self._uow)
        sync_command = SyncDevicesCommand(self._uow, self._remote)

        # Resolve Sub-Controllers
        device_ctrl = DeviceController(self._executor, device_queries, sync_command)

        gantt_ctrl = GanttController(self._executor, production_queries)

        # Return Main Controller
        return MainController(device_ctrl, gantt_ctrl)
