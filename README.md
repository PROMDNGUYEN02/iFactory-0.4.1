pip install -e .
Get-ChildItem -Path . -Include __pycache__ -Recurse | Remove-Item -Recurse -Force
tree /F > structure.txt
python -m iFactory
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
