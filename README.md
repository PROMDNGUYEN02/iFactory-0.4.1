pip install -e .
Get-ChildItem -Path . -Include __pycache__ -Recurse | Remove-Item -Recurse -Force
python -m iFactory
tree /F > structure.txt

.\venv\Scripts\activate
python -m iFactory
Get-ChildItem -Path "src\iFactory" -Filter "__pycache__" -Recurse -Force | Remove-Item -Recurse -Force
Get-ChildItem -Path "src\iFactory" -Filter "*.pyc" -Recurse -Force | Remove-Item -Recurse -Force

┌─────────────────────────────────────────────────────────────────────┐
│                    AVAILABLE MSSQL DRIVERS                          │
├─────────────────────────────────────────────────────────────────────┤
│ Driver Name                        │ Notes                          │
├────────────────────────────────────┼────────────────────────────────┤
│ "SQL Server"                       │     Legacy, most compatible    │
│                                    │    Works on most Windows       │
├────────────────────────────────────┼────────────────────────────────┤
│ "ODBC Driver 17 for SQL Server"    │ Modern, better performance     │
│                                    │    Requires separate install   │
├────────────────────────────────────┼────────────────────────────────┤
│ "ODBC Driver 18 for SQL Server"    │ Latest, TLS 1.3 support        │
│                                    │    Requires separate install   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│         Presentation Layer (UI)             │
│          ↓ depends on ↓                     │
├─────────────────────────────────────────────┤
│       Application Layer (Use Cases)         │
│          ↓ depends on ↓                     │
├─────────────────────────────────────────────┤
│         Domain Layer (Entities)             │
│          ↑ implemented by ↑                 │
├─────────────────────────────────────────────┤
│      Infrastructure Layer (DB, APIs)        │
└─────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  presentation/qt/                                   │   │
│  │  ├─ controllers/                                    │   │
│  │  │  ├─ DataSyncController                           │   │
│  │  │  ├─ DeviceController                             │   │
│  │  │  ├─ MainController                               │   │
│  │  │  └─ NavigationController                         │   │
│  │  ├─ views/                                          │   │
│  │  │  └─ MainView                                     │   │
│  │  ├─ presenters/                                     │   │
│  │  │  ├─ DevicePresenter                              │   │
│  │  │  └─ GanttPresenter                               │   │
│  │  └─ di/UIContainer                                  │   │
│  │                                                     │   │
│  │  presentation/adapters/                             │   │
│  │  ├─ AsyncExecutor                                   │   │
│  │  └─ QtSignalAdapter                                 │   │
│  │                                                     │   │
│  │  presentation/managers/                             │   │
│  │  ├─ IconManager                                     │   │
│  │  ├─ ThemeManager                                    │   │
│  │  └─ UIManagers                                      │   │
│  │                                                     │   │
│  │  ui/                                                │   │
│  │  ├─ widgets/ (DeviceWidget, LegendWidget, etc.)     │   │
│  │  └─ main_window/                                    │   │
│  └─────────────────┬───────────────────────────────────┘   │
└────────────────────┼───────────────────────────────────────┘
                     │ depends on
┌────────────────────▼───────────────────────────────────────┐
│                  APPLICATION LAYER                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  application/services/                               │  │
│  │  └─ DeviceDataService (Facade)                       │  │
│  │                                                      │  │
│  │  application/use_cases/                              │  │
│  │  ├─ device/                                          │  │
│  │  │  ├─ SyncDeviceStatusUseCase                       │  │
│  │  │  ├─ GetLatestStatusUseCase                        │  │
│  │  │  ├─ GetAllDevicesStatusUseCase                    │  │
│  │  │  └─ GetDeviceHistoryUseCase                       │  │
│  │  └─ gantt/                                           │  │
│  │     └─ GenerateGanttSegmentsUseCase                  │  │
│  │                                                      │  │
│  │  application/dto/                                    │  │
│  │  ├─ DeviceStatusDTO                                  │  │
│  │  └─ GanttDTO                                         │  │
│  │                                                      │  │
│  │  application/mappers/                                │  │
│  │  ├─ DeviceMapper                                     │  │
│  │  └─ StatusPeriodMapper                               │  │
│  │                                                      │  │
│  │  application/interfaces/                             │  │
│  │  ├─ ICacheProvider                                   │  │
│  │  ├─ IRemoteDataSource                                │  │
│  │  └─ IUnitOfWork                                      │  │
│  └──────────────────┬───────────────────────────────────┘  │
└─────────────────────┼──────────────────────────────────────┘
                      │ uses interfaces
┌─────────────────────▼──────────────────────────────────────┐
│                    DOMAIN LAYER                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  domain/repositories/ (Interfaces/Ports):            │  │
│  │  ├─ DeviceRepository                                 │  │
│  │  ├─ StatusRepository                                 │  │
│  │  ├─ InputRepository                                  │  │
│  │  └─ SyncMetadataRepository                           │  │
│  └──────────────────▲───────────────────────────────────┘  │
│  ┌──────────────────┴───────────────────────────────────┐  │
│  │  domain/entities/                                    │  │
│  │  ├─ Device                                           │  │
│  │  └─ StatusPeriod                                     │  │
│  │                                                      │  │
│  │  domain/value_objects/                               │  │
│  │  ├─ Color                                            │  │
│  │  ├─ EquipmentCode                                    │  │
│  │  ├─ Status                                           │  │
│  │  └─ TimeRange                                        │  │
│  │                                                      │  │
│  │  domain/enums/                                       │  │
│  │  └─ DeviceStatus                                     │  │
│  │                                                      │  │
│  │  domain/exceptions.py                                │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
                      ▲ implemented by
┌─────────────────────┴──────────────────────────────────────┐
│                INFRASTRUCTURE LAYER                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  infrastructure/persistence/repositories/            │  │
│  │  ├─ DeviceRepositoryImpl (SQLite)                    │  │
│  │  ├─ StatusRepositoryImpl (SQLite)                    │  │
│  │  ├─ InputRepositoryImpl (SQLite)                     │  │
│  │  └─ SyncMetadataRepositoryImpl (SQLite)              │  │
│  │                                                      │  │
│  │  infrastructure/persistence/data_sources/            │  │
│  │  └─ MSSQLDataSource                                  │  │
│  │                                                      │  │
│  │  infrastructure/persistence/mappers/                 │  │
│  │  ├─ DeviceORMMapper                                  │  │
│  │  └─ StatusPeriodORMMapper                            │  │
│  │                                                      │  │
│  │  infrastructure/persistence/services/                │  │
│  │  ├─ DataProviders                                    │  │
│  │  ├─ SyncOrchestrator                                 │  │
│  │  └─ SyncService                                      │  │
│  │                                                      │  │
│  │  infrastructure/cache/                               │  │
│  │  ├─ CacheProvider (LRU)                              │  │
│  │  ├─ LRUCache                                         │  │
│  │  └─ CacheEntry                                       │  │
│  │                                                      │  │
│  │  infrastructure/database/                            │  │
│  │  ├─ engines/ (BaseEngine, SQLiteEngine, MSSQLEngine) │  │
│  │  ├─ models/ (ModelsCold, ModelsHot)                  │  │
│  │  ├─ Orchestrator                                     │  │
│  │  └─ Config                                           │  │
│  │                                                      │  │
│  │  infrastructure/devices/                             │  │
│  │  └─ Manager                                          │  │
│  │                                                      │  │
│  │  infrastructure/gantt/                               │  │
│  │  ├─ Config                                           │  │
│  │  ├─ Factory                                          │  │
│  │  └─ Manager                                          │  │
│  │                                                      │  │
│  │  infrastructure/legend/                              │  │
│  │  ├─ Config                                           │  │
│  │  └─ Manager                                          │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
                      ▲
┌─────────────────────┴──────────────────────────────────────┐
│                  CROSS-CUTTING CONCERNS                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  config/                                             │  │
│  │  ├─ Settings                                         │  │
│  │  ├─ SettingsManager                                  │  │
│  │  ├─ DeviceConfig                                     │  │
│  │  ├─ LoggingConfig                                    │  │
│  │  └─ Constants                                        │  │
│  │                                                      │  │
│  │  shared/di/                                          │  │
│  │  ├─ AppContainer (Main DI Container)                 │  │
│  │  └─ ApplicationRunner                                │  │
│  │                                                      │  │
│  │  shared/utils/                                       │  │
│  │  ├─ DateTimeUtils                                    │  │
│  │  └─ Paths                                            │  │
│  │                                                      │  │
│  │  resources/                                          │  │
│  │  ├─ icon/ (SVG icons for devices & UI)               │  │
│  │  └─ themes/ (QSS stylesheets)                        │  │
│  │                                                      │  │
│  │  bootstrap.py (Application Entry Point)              │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                       DATA STORAGE                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  src/data/                                           │  │
│  │  ├─ hot_store.db (SQLite - Recent/Active Data)       │  │
│  │  └─ cold_store.db (SQLite - Historical Data)         │  │
│  │                                                      │  │
│  │  data/ (Configuration Files)                         │  │
│  │  ├─ device_positions.json                            │  │
│  │  ├─ legends.json                                     │  │
│  │  └─ settings.json                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘

┌───────────────── ┐    ┌──────────────────┐    ┌──────────────── ─┐
│   Presentation   │◄──►│   Application    │◄──►│ Infrastructure   │
│ (PyQt: Views/    │    │ (Use Cases/DTOs/ │    │ (DB: MSSQL→SQLite│
│  Controllers/    │    │  Services)       │    │  Cache LRU)      │
│  Widgets/Gantt)  │    │                  │    │                  │
└───────────────── ┘    └──────────────────┘    └──────────────────┘
         ▲                        ▲                        ▲
         │                        │                        │
      ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
      │   Domain     │       │   Config/DI  │       │   Shared/UI  │
      │ (Entities/   │       │ (Containers/ │       │ (Utils/Theme/│
      │  Repos/Enums)│       │  Settings)   │       │  Profiler)   │
      └──────────────┘       └──────────────┘       └──────────────┘

[Presentation Layer] (Qt Widgets, Controllers)
       ↓ (Calls)
[Application Layer] (Use Cases, DTOs, Application Services)
       ↓ (Depends on)
[Domain Layer] (Entities, Value Objects, Repository Interfaces)
       ↑ (Implements)
[Infrastructure Layer] (DB, FileSystem, External APIs, RepoImpls)

src/iFactory/
├── main.py                         # Entry point
├── config/                        # Cấu hình hệ thống (không phải business config)
│   └── settings.py
│
├── domain/                        # [CORE] Lõi nghiệp vụ, không phụ thuộc ai
│   ├── __init__.py
│   ├── entities/                  # Các thực thể nghiệp vụ (Device, ProductionOrder)
│   ├── value_objects/             # Các đối tượng giá trị (EquipmentCode, TimeRange)
│   ├── repositories/              # Port (Interface): IDeviceRepository, ISyncRepository
│   └── services/                  # Domain Services (logic nghiệp vụ phức tạp không thuộc Entity)
│
├── application/                   # [ORCHESTRATOR] Điều phối luồng sử dụng
│   ├── __init__.py
│   ├── use_cases/                 # Use Case (Input Port)
│   │   ├── device/
│   │   │   └── sync_device_status.py
│   │   └── production/
│   │       └── generate_timeline.py   # Logic Gantt nằm ở đây
│   ├── dto/                       # Data Transfer Objects (để trả về UI)
│   └── services/                  # Application Services (chia sẻ logic giữa các UC)
│
├── infrastructure/                # [PLUGGABLE] Chi tiết kỹ thuật
│   ├── persistence/               # Cơ sở dữ liệu
│   │   ├── models/                # ORM Models (SQLAlchemy, peewee...)
│   │   ├── repositories/          # Adapter: DeviceRepositoryImpl
│   │   └── mappers/               # Mapper: ORM Model <-> Domain Entity
│   ├── external/                  # Gọi API ngoài, file system...
│   └── cache/                     # Cache implementation (được ẩn trong repo hoặc service)
│
├── presentation/                  # [UI DESKTOP] Qt specific
│   ├── qt/
│   │   ├── views/                 # QWidget, QMainWindow (chỉ chứa UI code, không logic)
│   │   ├── controllers/           # Điều phối: Connect Qt Signal -> Use Case
│   │   └── view_models/           # (Optional) Adapter dữ liệu từ DTO sang Qt Model
│   └── di/                        # Dependency Injection Container (Wire everything)
│
└── shared/                        # Chia sẻ chung (Utils, Constants)
    └── utils/

[Presentation: Controller]
       | 1. Request (primitive types)
       v
[Application: Use Case]
       | 2. Logic điều phối (Validation, Logging, Caching)
       | 3. Gọi Interfaces
       +---------------------------+
       |                           |
       v                           v
[Application: UnitOfWork]   [Application: RemoteDataSource] (Abstract)
       |                           |
       | 4. Lấy Entity              | 5. Lấy Raw Data (khoác ngoại)
       v                           |
[Domain: Entity] <--------------+
       | 6. Logic nghiệp vụ (self-encapsulated)
       v
[Application: Mapper]
       | 7. Chuyển đổi Entity -> DTO
       v
[Application: DTO]
       | 8. Dữ liệu sạch (Read-only)
       v
[Presentation: Controller]

src/iFactory/presentation/
├── qt/                         # Giao diện UI (PySide6)
│   ├── controllers/                # Điều phối sự kiện (Use Cases)
│   │   ├── main_controller.py     # Logic điều phối nhẹ
│   │   ├── device_controller.py # Logic điều phối nhẹ (State caching)
│   │   └── navigation_controller.py # Điều phối nhẹ (State chuyển trang)
│   ├── presenters/                 # Chuyển Entity -> DTO (Logic format nhẹ)
│   │   ├── device_presenter.py
│   │   └── gantt_presenter.py  # Logic Gantt format nhẹ
│   └── adapters/                  # Cầu nối Async (Thread Pool)
│       ├── async_executor.py
│       └── qt_signal_adapter.py
└── managers/                         # Quản lý UI (Theme, Icons, Animation)
    ├── ui/                             # Giao diện Widgets (PySide6)
    ├── widgets/
    │   ├── device_manager.py           # Điều phối UI <-> Infrastructure (Hybrid layer)
    │   └── gantt/                   # Gantt Strip (High-performance UI)
