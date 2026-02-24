.PHONY: install run test lint format worker beat smoke

install:
	python3 -m pip install -r requirements.txt

run:
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	celery -A src.tasks.worker.celery_app worker --loglevel=info --concurrency=4

beat:
	celery -A src.tasks.worker.celery_app beat --loglevel=info

smoke:
	bash scripts/smoke.sh

test:
	pytest -q

lint:
	python3 -m compileall -q src tests

format:
	python3 -m pip install black==24.10.0
	black src tests
