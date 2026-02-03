pip install -e .
Get-ChildItem -Path . -Include __pycache__ -Recurse | Remove-Item -Recurse -Force
tree /F > structure.txt
python -m iFactory
.\venv\Scripts\activate

ls src\iFactory\presentation\resources\resources_rc.py

pyside6-rcc "C:\python\iFactory 0.4.1\src\iFactory\presentation\resources\resources.qrc" -o "C:\python\iFactory 0.4.1\src\iFactory\presentation\resources\resources_rc.py"
