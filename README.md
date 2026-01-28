pip install -e .
Get-ChildItem -Path . -Include __pycache__ -Recurse | Remove-Item -Recurse -Force
tree /F > structure.txt
python -m iFactory
.\venv\Scripts\activate
