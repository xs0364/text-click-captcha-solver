python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -e .
playwright install chromium
