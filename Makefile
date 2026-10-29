.PHONY: install prepare train research build test serve bundle
install:
	python -m pip install -e '.[dev]'
prepare:
	python -m marketbudget.ingest prepare
train:
	python -m marketbudget.train
research:
	python -m marketbudget.research
build:
	python scripts/build.py
test:
	python -m pytest -q
	node --test tests/*.test.mjs
serve:
	python -m marketbudget.api
bundle:
	python scripts/package.py
