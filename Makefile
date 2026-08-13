PYTHON ?= python3
BUNDLE ?= bundle
JEKYLL_ENV ?= development

.PHONY: publications publications-check test check build serve clean

publications:
	$(PYTHON) scripts/build_publications.py --strict

publications-check:
	$(PYTHON) scripts/build_publications.py --check --strict

test:
	$(PYTHON) -m unittest discover -s tests -v

check: publications-check test

build: publications test
	JEKYLL_ENV=production $(BUNDLE) exec jekyll build --trace

serve: publications
	$(BUNDLE) exec jekyll serve --livereload

clean:
	rm -rf _site .jekyll-cache .sass-cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
