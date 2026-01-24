Clean Architecture, phân tách rõ UI, business logic, domain, infrastructure, code dễ đọc, dễ mở rộng, hạn chế phụ thuộc chéo và tăng khả năng bảo trì dài hạn. C:.
ª   .gitignore
ª   CHANGELOG.md
ª   clean_app
ª   LICENSE
ª   pyproject.toml
ª   README.md
ª   structure.txt
ª   
+---data
ª       cold_store.db
ª       cold_store.db-shm
ª       cold_store.db-wal
ª       device_positions.json
ª       hot_store.db
ª       hot_store.db-shm
ª       hot_store.db-wal
ª       legends.json
ª       settings.json
ª       settings.json.bak
ª       
+---docs
ª       README.md
ª       
+---scripts
ª       build.py
ª       dev_setup.py
ª       package.py
ª       
+---src
ª   +---iFactory
ª   ª   ª   app.py
ª   ª   ª   __init__.py
ª   ª   ª   __main__.py
ª   ª   ª   
ª   ª   +---config
ª   ª   ª       constants.py
ª   ª   ª       device_config.py
ª   ª   ª       logging_config.py
ª   ª   ª       settings.py
ª   ª   ª       settings_manager.py
ª   ª   ª       __init__.py
ª   ª   ª       
ª   ª   +---core
ª   ª   ª   ª   exceptions.py
ª   ª   ª   ª   status_mapping.py
ª   ª   ª   ª   __init__.py
ª   ª   ª   ª   
ª   ª   ª   +---interfaces
ª   ª   ª   ª       ports.py
ª   ª   ª   ª       __init__.py
ª   ª   ª   ª       
ª   ª   ª   +---models
ª   ª   ª   ª       dto.py
ª   ª   ª   ª       __init__.py
ª   ª   ª   ª       
ª   ª   ª   +---services
ª   ª   ª           base_service.py
ª   ª   ª           device_data_service.py
ª   ª   ª           full_service.py
ª   ª   ª           input_service.py
ª   ª   ª           load_controller.py
ª   ª   ª           status_service.py
ª   ª   ª           __init__.py
ª   ª   ª           
ª   ª   +---infrastructure
ª   ª   ª   ª   __init__.py
ª   ª   ª   ª   
ª   ª   ª   +---database
ª   ª   ª   ª   ª   base.py
ª   ª   ª   ª   ª   manager.py
ª   ª   ª   ª   ª   __init__.py
ª   ª   ª   ª   ª   
ª   ª   ª   ª   +---models
ª   ª   ª   ª           models_cold.py
ª   ª   ª   ª           models_hot.py
ª   ª   ª   ª           __init__.py
ª   ª   ª   ª           
ª   ª   ª   +---devices
ª   ª   ª   ª       manager.py
ª   ª   ª   ª       __init__.py
ª   ª   ª   ª       
ª   ª   ª   +---gantt
ª   ª   ª   ª       factory.py
ª   ª   ª   ª       manager.py
ª   ª   ª   ª       __init__.py
ª   ª   ª   ª       
ª   ª   ª   +---legend
ª   ª   ª   ª       manager.py
ª   ª   ª   ª       __init__.py
ª   ª   ª   ª       
ª   ª   ª   +---persistence
ª   ª   ª           repository_cold.py
ª   ª   ª           repository_gantt.py
ª   ª   ª           repository_hot.py
ª   ª   ª           right_menu_provider.py
ª   ª   ª           summary_data_provider.py
ª   ª   ª           sync_orchestrator.py
ª   ª   ª           sync_service.py
ª   ª   ª           utils.py
ª   ª   ª           __init__.py
ª   ª   ª           
ª   ª   +---resources
ª   ª   ª   ª   resources.qrc
ª   ª   ª   ª   resources_rc.py
ª   ª   ª   ª   __init__.py
ª   ª   ª   ª   
ª   ª   ª   +---icon
ª   ª   ª   ª   ª   1.svg
ª   ª   ª   ª   ª   arrow_menu_close-white.svg
ª   ª   ª   ª   ª   arrow_menu_close.svg
ª   ª   ª   ª   ª   arrow_menu_open-white.svg
ª   ª   ª   ª   ª   arrow_menu_open.svg
ª   ª   ª   ª   ª   close-white.svg
ª   ª   ª   ª   ª   close.svg
ª   ª   ª   ª   ª   customers-white.svg
ª   ª   ª   ª   ª   customers.svg
ª   ª   ª   ª   ª   dashboard-white.svg
ª   ª   ª   ª   ª   dashboard.svg
ª   ª   ª   ª   ª   dashboard_layout-white.svg
ª   ª   ª   ª   ª   dashboard_layout.svg
ª   ª   ª   ª   ª   expand-white.svg
ª   ª   ª   ª   ª   expand.svg
ª   ª   ª   ª   ª   icon.ico
ª   ª   ª   ª   ª   logo.png
ª   ª   ª   ª   ª   open-white.svg
ª   ª   ª   ª   ª   open.svg
ª   ª   ª   ª   ª   orders-white.svg
ª   ª   ª   ª   ª   orders.svg
ª   ª   ª   ª   ª   orders_layout-white.svg
ª   ª   ª   ª   ª   orders_layout.svg
ª   ª   ª   ª   ª   products-white.svg
ª   ª   ª   ª   ª   products.svg
ª   ª   ª   ª   ª   reports-white.svg
ª   ª   ª   ª   ª   reports.svg
ª   ª   ª   ª   ª   settings-white.svg
ª   ª   ª   ª   ª   settings.svg
ª   ª   ª   ª   ª   
ª   ª   ª   ª   +---devices
ª   ª   ª   ª           ACL-white.svg
ª   ª   ª   ª           ACL.svg
ª   ª   ª   ª           ACT-white.svg
ª   ª   ª   ª           ACT.svg
ª   ª   ª   ª           ALS-white.svg
ª   ª   ª   ª           ALS.svg
ª   ª   ª   ª           AMX-white.svg
ª   ª   ª   ª           AMX.svg
ª   ª   ª   ª           CA1-white.svg
ª   ª   ª   ª           CA1.svg
ª   ª   ª   ª           CA2-white.svg
ª   ª   ª   ª           CA2.svg
ª   ª   ª   ª           CAW-white.svg
ª   ª   ª   ª           CAW.svg
ª   ª   ª   ª           CBC-white.svg
ª   ª   ª   ª           CBC.svg
ª   ª   ª   ª           CBD-white.svg
ª   ª   ª   ª           CBD.svg
ª   ª   ª   ª           CBP-white.svg
ª   ª   ª   ª           CBP.svg
ª   ª   ª   ª           CBW-white.svg
ª   ª   ª   ª           CBW.svg
ª   ª   ª   ª           CCI-white.svg
ª   ª   ª   ª           CCI.svg
ª   ª   ª   ª           CCL-white.svg
ª   ª   ª   ª           CCL.svg
ª   ª   ª   ª           CCR-white.svg
ª   ª   ª   ª           CCR.svg
ª   ª   ª   ª           CCT-white.svg
ª   ª   ª   ª           CCT.svg
ª   ª   ª   ª           CCU-white.svg
ª   ª   ª   ª           CCU.svg
ª   ª   ª   ª           CCW-white.svg
ª   ª   ª   ª           CCW.svg
ª   ª   ª   ª           CEJ-white.svg
ª   ª   ª   ª           CEJ.svg
ª   ª   ª   ª           CHW-white.svg
ª   ª   ª   ª           CHW.svg
ª   ª   ª   ª           CJL-white.svg
ª   ª   ª   ª           CJL.svg
ª   ª   ª   ª           CLS-white.svg
ª   ª   ª   ª           CLS.svg
ª   ª   ª   ª           CMX-white.svg
ª   ª   ª   ª           CMX.svg
ª   ª   ª   ª           COC-white.svg
ª   ª   ª   ª           COC.svg
ª   ª   ª   ª           CRB-white.svg
ª   ª   ª   ª           CRB.svg
ª   ª   ª   ª           CSG-white.svg
ª   ª   ª   ª           CSG.svg
ª   ª   ª   ª           CTB-white.svg
ª   ª   ª   ª           CTB.svg
ª   ª   ª   ª           CTI-white.svg
ª   ª   ª   ª           CTI.svg
ª   ª   ª   ª           CWD-white.svg
ª   ª   ª   ª           CWD.svg
ª   ª   ª   ª           CWS-white.svg
ª   ª   ª   ª           CWS.svg
ª   ª   ª   ª           CXI-white.svg
ª   ª   ª   ª           CXI.svg
ª   ª   ª   ª           
ª   ª   ª   +---themes
ª   ª   ª           base.qss
ª   ª   ª           variables.json
ª   ª   ª           
ª   ª   +---ui
ª   ª   ª   +---designer
ª   ª   ª   ª       main.ui
ª   ª   ª   ª       
ª   ª   ª   +---dialogs
ª   ª   ª   +---generated
ª   ª   ª   ª       main_ui.py
ª   ª   ª   ª       __init__.py
ª   ª   ª   ª       
ª   ª   ª   +---main_window
ª   ª   ª   ª       constants.py
ª   ª   ª   ª       device_manager.py
ª   ª   ª   ª       main_window.py
ª   ª   ª   ª       managers.py
ª   ª   ª   ª       __init__.py
ª   ª   ª   ª       
ª   ª   ª   +---managers
ª   ª   ª   ª       managers.py
ª   ª   ª   ª       __init__.py
ª   ª   ª   ª       
ª   ª   ª   +---widgets
ª   ª   ª       ª   constants.py
ª   ª   ª       ª   menu_widgets.py
ª   ª   ª       ª   panel_widgets.py
ª   ª   ª       ª   right_panel_components.py
ª   ª   ª       ª   right_slide_menu.py
ª   ª   ª       ª   __init__.py
ª   ª   ª       ª   
ª   ª   ª       +---gantt
ª   ª   ª               strip.py
ª   ª   ª               theme.py
ª   ª   ª               utils.py
ª   ª   ª               __init__.py
ª   ª   ª               
ª   ª   +---utils
ª   ª           helpers.py
ª   ª           paths.py
ª   ª           __init__.py
ª   ª           
ª   +---iFactory.egg-info
ª           dependency_links.txt
ª           entry_points.txt
ª           PKG-INFO
ª           requires.txt
ª           SOURCES.txt
ª           top_level.txt tái cấu trúc nếu cần, đây là dự án lớn, mình sẽ gửi từng file để Clean Architecture, phân tách rõ UI, business logic, domain, infrastructure, code dễ đọc, dễ mở rộng, hạn chế phụ thuộc chéo và tăng khả năng bảo trì dài hạn.

src/iFactory/
│
├── 🎯 domain/                           # DOMAIN LAYER (Core Business Logic)
│   ├── entities/                       # Business entities (Device, Task, Order...)
│   ├── value_objects/                  # Immutable objects (Status, Position...)
│   ├── enums/                          # Domain enums
│   ├── exceptions/                     # Domain exceptions
│   └── repositories/                   # Repository interfaces (ports)
│       ├── device_repository.py
│       ├── gantt_repository.py
│       └── data_repository.py
│
├── 💼 application/                      # APPLICATION LAYER (Use Cases)
│   ├── use_cases/                      # Business use cases
│   │   ├── device/
│   │   │   ├── get_device_data.py
│   │   │   ├── update_device_status.py
│   │   │   └── sync_device_data.py
│   │   ├── gantt/
│   │   └── summary/
│   ├── services/                       # Application services
│   ├── dto/                            # Data Transfer Objects
│   ├── interfaces/                     # Application ports
│   │   ├── services.py
│   │   └── providers.py
│   └── mappers/                        # Entity <-> DTO converters
│
├── 🔧 infrastructure/                   # INFRASTRUCTURE LAYER
│   ├── persistence/
│   │   ├── sqlalchemy/
│   │   │   ├── models/                 # ORM models
│   │   │   ├── repositories/           # Repository implementations
│   │   │   └── database.py
│   │   └── json/                       # JSON file storage
│   ├── external/
│   │   ├── devices/                    # Device manager
│   │   └── gantt/                      # Gantt chart generator
│   ├── config/                         # Configuration
│   └── logging/                        # Logging setup
│
├── 🎨 presentation/                     # PRESENTATION LAYER (UI)
│   ├── qt/
│   │   ├── windows/
│   │   │   └── main_window.py
│   │   ├── widgets/
│   │   │   ├── gantt/
│   │   │   ├── panels/
│   │   │   └── menus/
│   │   └── dialogs/
│   ├── controllers/                    # UI Controllers
│   │   ├── main_controller.py
│   │   ├── device_controller.py
│   │   └── gantt_controller.py
│   ├── presenters/                     # View models/Presenters
│   └── di/                             # Dependency Injection container
│       └── container.py
│
├── 🔄 shared/                           # SHARED KERNEL
│   ├── constants/
│   ├── utils/
│   └── events/                         # Domain events
│
└── resources/                          # Static resources (icons, themes...)

Core/Models (entities, DTOs)
Core/Services (business logic)
Infrastructure (database, repositories)
UI (windows, widgets)
Config & Utils

src/iFactory/
│
├── domain/                                 # ← NEW: Domain Layer
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── device.py                      # Device entity
│   │   └── status_period.py               # Status period entity
│   │
│   ├── value_objects/
│   │   ├── __init__.py
│   │   ├── equipment_code.py              # Equipment identifier
│   │   ├── status.py                      # Status value object
│   │   ├── time_range.py                  # Time period
│   │   └── color.py                       # Color value
│   │
│   └── enums/
│       ├── __init__.py
│       └── device_status.py               # Status enum
│
├── application/                            # ← NEW: Application Layer
│   ├── dto/
│   │   ├── __init__.py
│   │   ├── device_status_dto.py
│   │   └── gantt_dto.py
│   │
│   └── mappers/
│       ├── __init__.py
│       └── device_mapper.py               # Entity <-> DTO
│
└── infrastructure/                         # ← REFACTORED
    ├── persistence/
    │   └── types/
    │       ├── __init__.py
    │       ├── hot_store_types.py         # LatestStatusRow
    │       └── cold_store_types.py        # StatusHistoryRow
    │
    └── cache/
        ├── __init__.py
        └── cache_entry.py                 # Generic cache


src/iFactory/
│
├── domain/
│   ├── repositories/                      # Repository Interfaces (Ports)
│   │   ├── __init__.py
│   │   ├── device_repository.py
│   │   ├── status_repository.py
│   │   └── sync_metadata_repository.py
│   │
│   └── services/                          # Domain Services (nếu cần)
│       ├── __init__.py
│       └── status_validator.py
│
├── application/
│   ├── use_cases/
│   │   ├── device/
│   │   │   ├── __init__.py
│   │   │   ├── sync_device_status.py
│   │   │   ├── get_latest_status.py
│   │   │   ├── get_all_devices_status.py
│   │   │   └── get_device_history.py
│   │   │
│   │   └── gantt/
│   │       ├── __init__.py
│   │       └── generate_gantt_segments.py
│   │
│   ├── interfaces/                        # Application Ports
│   │   ├── __init__.py
│   │   ├── cache_provider.py
│   │   └── remote_data_source.py
│   │
│   └── services/                          # Application Services
│       ├── __init__.py
│       └── device_data_service.py         # Facade cho UI
│
├── infrastructure/
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── lru_cache.py
│   │   └── cache_provider.py
│   │
│   └── persistence/
│       └── repositories/
│           ├── __init__.py
│           ├── device_repository_impl.py
│           └── status_repository_impl.py
│
└── presentation/
    └── qt/
        └── controllers/
            ├── __init__.py
            └── data_sync_controller.py     # Pure Qt controller

src/iFactory/
│
├── domain/
│   └── repositories/                      # ← Interfaces (ALREADY CREATED)
│       ├── device_repository.py
│       ├── status_repository.py
│       └── sync_metadata_repository.py
│
├── application/
│   ├── use_cases/                         # ← Business Logic (ALREADY CREATED)
│   └── services/
│       └── sync_orchestrator.py           # ← NEW: Orchestrate sync use cases
│
└── infrastructure/
    ├── database/
    │   ├── engines/
    │   │   ├── __init__.py
    │   │   ├── sqlite_engine.py
    │   │   └── mssql_engine.py
    │   │
    │   ├── models/                        # ORM Models (EXISTING)
    │   │   ├── __init__.py
    │   │   ├── hot_models.py
    │   │   └── cold_models.py
    │   │
    │   └── connection_manager.py          # Refactored from manager.py
    │
    └── persistence/
        ├── repositories/                  # Repository Implementations
        │   ├── __init__.py
        │   ├── device_repository_impl.py
        │   ├── status_repository_impl.py
        │   └── sync_metadata_repository_impl.py
        │
        ├── mappers/                       # ORM ↔ Domain Entity
        │   ├── __init__.py
        │   ├── device_orm_mapper.py
        │   └── status_period_orm_mapper.py
        │
        ├── query_builders/                # SQL Query Builders
        │   ├── __init__.py
        │   └── gantt_query_builder.py
        │
        └── data_sources/                  # Remote Data Sources
            ├── __init__.py
            └── mssql_data_source.py

Presentation (MainWindow)
  ↓ uses
Application (DeviceDataService via DI)
  ↓ uses interfaces
Domain (IDeviceRepository)
  ↑ implemented by
Infrastructure (DeviceRepositoryImpl)

src/iFactory/
│
├── presentation/
│   ├── qt/
│   │   ├── controllers/              # Controllers (MVP pattern)
│   │   │   ├── __init__.py
│   │   │   ├── main_controller.py    # Orchestrate use cases
│   │   │   ├── device_controller.py  # Device interactions
│   │   │   ├── navigation_controller.py
│   │   │   └── menu_controller.py
│   │   │
│   │   ├── views/                    # Pure Qt Views (no logic)
│   │   │   ├── __init__.py
│   │   │   ├── main_view.py          # Wrapper for Ui_MainWindow
│   │   │   └── components/           # Reusable widgets
│   │   │       ├── device_widget.py
│   │   │       ├── gantt_widget.py
│   │   │       └── status_label.py
│   │   │
│   │   ├── presenters/               # View Models (transform data)
│   │   │   ├── __init__.py
│   │   │   ├── device_presenter.py
│   │   │   └── gantt_presenter.py
│   │   │
│   │   └── di/                       # Dependency Injection
│   │       ├── __init__.py
│   │       └── ui_container.py       # Wire UI components
│   │
│   └── managers/                     # UI-only managers
│       ├── __init__.py
│       ├── theme_manager.py          # Pure CSS/QSS management
│       └── icon_manager.py           # Resource loading
│
└── ui/                               # Generated UI files (keep as is)
    └── generated/
        └── main_ui.py

src/iFactory/
│
├── __main__.py                         # Entry point (minimal)
├── bootstrap.py                        # Application bootstrapper (NEW)
│
├── domain/                             # ✅ DONE (previous refactoring)
│   ├── entities/
│   ├── value_objects/
│   ├── enums/
│   └── repositories/                   # Interfaces
│
├── application/                        # ✅ DONE (previous refactoring)
│   ├── use_cases/
│   ├── services/
│   ├── dto/
│   └── interfaces/
│
├── infrastructure/                     # ✅ DONE (previous refactoring)
│   ├── database/
│   ├── persistence/
│   └── cache/
│
├── presentation/
│   ├── qt/
│   │   ├── controllers/               # ✅ DONE
│   │   ├── views/                      # ✅ DONE
│   │   ├── presenters/                 # ✅ DONE
│   │   └── di/
│   │       └── container.py            # UI DI Container
│   │
│   └── adapters/
│       ├── __init__.py
│       ├── qt_signal_adapter.py        # DatabaseBridge refactored (NEW)
│       └── async_executor.py           # Qt-async bridge (NEW)
│
└── shared/
    ├── di/
    │   └── app_container.py            # Main DI Container (NEW)
    └── config/                         # Configuration

# Gộp tất cả vào 1 file
@(
  "src/iFactory/presentation/managers/icon_manager.py",
  "src/iFactory/presentation/qt/views/main_view.py",
  "src/iFactory/ui/widgets/panel_widgets.py",
  "src/iFactory/presentation/qt/presenters/device_presenter.py",
  "src/iFactory/presentation/qt/controllers/device_controller.py"
) | ForEach-Object {
  "`n`n=== $_ ===`n"
  Get-Content $_
}

# Tìm tất cả files trong ui/
Get-ChildItem "src/iFactory/ui/" -Recurse -File | Select-Object FullName