APP=app.main:app
HOST=127.0.0.1
PORT=8000
PYTHON=.venv/bin/python

# Run dev server
dev:
	$(PYTHON) -m uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

# Install dependencies
install:
	$(PYTHON) -m pip install -r requirements.txt

# Apply database migrations
migrate:
	$(PYTHON) -m alembic upgrade head

# Create a new migration (usage: make revision msg="your message")
revision:
	$(PYTHON) -m alembic revision --autogenerate -m "$(msg)"

# Show migration history
history:
	$(PYTHON) -m alembic history

# Downgrade database by one revision
downgrade:
	$(PYTHON) -m alembic downgrade -1