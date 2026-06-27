.PHONY: install dev test build clean lint

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/

lint:
	ruff check src/
	mypy src/

build:
	pyinstaller --onefile --name ehc \
		--collect-all questionary --collect-all rich --collect-all typer \
		src/ehc/cli.py

clean:
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
