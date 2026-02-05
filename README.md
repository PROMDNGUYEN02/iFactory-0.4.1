pip install -e .
Get-ChildItem -Path . -Include __pycache__ -Recurse | Remove-Item -Recurse -Force
tree /F > structure.txt
Get-ChildItem -Path . -Include __pycache__ -Recurse | Remove-Item -Recurse -Force
python -m iFactory
Get-ChildItem -Path . -Include __pycache__ -Recurse | Remove-Item -Recurse -Force
.\venv\Scripts\activate

ls src\iFactory\presentation\resources\resources_rc.py

pyside6-rcc "C:\python\iFactory 0.4.1\src\iFactory\presentation\resources\resources.qrc" -o "C:\python\iFactory 0.4.1\src\iFactory\presentation\resources\resources_rc.py"

# 1. Clean build

pyinstaller --clean --noconfirm iFactory.spec

# 2. Copy .env nếu cần (backup)

copy .env dist\iFactory\.env

# 3. Test chạy

cd dist\iFactory
.\iFactory.exe

# 4. Sau khi OK, đổi console=False trong spec và build lại

pip install structlog orjson
pip show structlog orjson

┌─────────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                         │
│  ┌─────────┐  ┌──────────┐  ┌───────┐  ┌──────────┐            │
│  │  Views  │  │ViewModels│  │ State │  │Components│            │
│  └────┬────┘  └────┬─────┘  └───┬───┘  └──────────┘            │
│       └────────────┴────────────┘                               │
├─────────────────────────────────────────────────────────────────┤
│                      APPLICATION LAYER                          │
│  ┌──────────┐  ┌─────────┐  ┌──────────┐  ┌─────────┐          │
│  │ Commands │  │ Queries │  │ Mediator │  │ Services│          │
│  └────┬─────┘  └────┬────┘  └────┬─────┘  └────┬────┘          │
│       └─────────────┴────────────┴─────────────┘                │
├─────────────────────────────────────────────────────────────────┤
│                        DOMAIN LAYER                             │
│  ┌──────────┐  ┌──────────────┐  ┌────────┐  ┌────────┐        │
│  │ Entities │  │ Value Objects│  │ Events │  │Policies│        │
│  └──────────┘  └──────────────┘  └────────┘  └────────┘        │
├─────────────────────────────────────────────────────────────────┤
│                    INFRASTRUCTURE LAYER                         │
│  ┌──────────┐  ┌───────────┐  ┌───────┐  ┌────────────┐        │
│  │ Adapters │  │Persistence│  │ Cache │  │Observability│       │
│  └──────────┘  └───────────┘  └───────┘  └────────────┘        │
└─────────────────────────────────────────────────────────────────┘

| Khái niệm                  | Trả lời câu hỏi                        |
| -------------------------- | -------------------------------------- |
| __Data Flow__              | Dữ liệu đi *qua những layer nào*       |
| __Data Binding__           | UI *nhận dữ liệu và re-render thế nào* |
| __Data Refresh / Polling__ | *Khi nào* dữ liệu được fetch           |

Data Flow + Data Binding + Data Refresh / Polling

┌────────────────────────────────────────────────────────────┐
│                         USER ACTIONS                       │
│                                                            │
│  • App start                                               │
│  • Page change                                             │
│  • Click device                                            │
│  • Double-click device                                     │
│  • (No action – idle)                                      │
└───────────────┬────────────────────────────────────────────┘
                ↓
┌────────────────────────────────────────────────────────────┐
│                    UI CONTEXT STATE                        │
│                                                            │
│  - current_page                                            │
│  - visible_equip_codes                                     │
│  - selected_equip_code                                     │
│  - gantt_visible (bool)                                    │
│  - right_panel_open (bool)                                 │
│  - gantt_time_range                                        │
└───────────────┬────────────────────────────────────────────┘
                ↓
┌────────────────────────────────────────────────────────────┐
│        REFRESH ORCHESTRATOR / USE CASE                     │
│                                                            │
│  Trigger sources:                                          │
│   • QTimer (every 3s)                                      │
│   • UI context change                                      │
│                                                            │
│  Logic:                                                    │
│   - Decide WHAT data to fetch based on UI context          │
│   - Never decide HOW UI renders                            │
└───────────────┬────────────────────────────────────────────┘
                ↓
┌────────────────────────────────────────────────────────────┐
│                MODEL / REPOSITORY                          │
│                                                            │
│  EqStatusRepository                                        │
│  (TT_EQ_STATUS – Single Source of Truth)                   │
│                                                            │
│  Queries:                                                  │
│   • fetch_latest(eq_codes)                                 │
│   • fetch_history(eq_code, time_range)                     │
└───────────────┬────────────────────────────────────────────┘
                ↓
┌────────────────────────────────────────────────────────────┐
│                 RAW STATUS RECORDS                         │
│                                                            │
│  EqStatus(equip_code, status, start_time, end_time)        │
└───────────────┬────────────────────────────────────────────┘
                ↓
        ┌────────┴─────────────┬───────────────────────────┐
        ↓                      ↓                           ↓
┌──────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ LatestStatusVM   │  │ HistoryGanttVM       │  │ (optional) Other VM  │
│                  │  │                      │  │                      │
│ - reduce latest  │  │ - normalize timeline │  │                      │
│ - per device     │  │ - merge / split      │  │                      │
│ - map color      │  │ - map gantt tasks    │  │                      │
└────────┬─────────┘  └────────┬─────────────┘  └────────┬─────────────┘
         ↓                      ↓                           ↓
┌──────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ Status Card UI   │  │ Gantt Chart UI       │  │ Right Panel UI       │
│ (List / Tile)    │  │ (History timeline)   │  │ (Latest status)     │
│ Render-only      │  │ Render-only           │  │ Render-only         │
└──────────────────┘  └──────────────────────┘  └──────────────────────┘
