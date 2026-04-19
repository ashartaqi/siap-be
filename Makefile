APP=app.main:app
HOST=127.0.0.1
PORT=8000
python=.venv/bin/python

dev:
	$(python) -m uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

install:
	$(python) -m pip install -r requirements.txt