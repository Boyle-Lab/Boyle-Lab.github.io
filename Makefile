PYTHON ?= python3
BUNDLE ?= bundle
JEKYLL_ENV ?= development

.PHONY: publications publications-check cv-source cv cv-check test check build serve clean

publications:
	$(PYTHON) scripts/build_publications.py --strict

publications-check:
	$(PYTHON) scripts/build_publications.py --check --strict

cv-source: publications
	$(PYTHON) scripts/build_cv.py --strict

cv: publications
	$(PYTHON) scripts/build_cv.py --strict --compile

cv-check: publications-check
	$(PYTHON) scripts/build_cv.py --check --strict

test:
	$(PYTHON) -m unittest discover -s tests -v

check: publications-check cv-check test

build: publications cv test
	JEKYLL_ENV=production $(BUNDLE) exec jekyll build --trace

serve: publications cv-source
	$(BUNDLE) exec jekyll serve --livereload

clean:
	rm -rf _site .jekyll-cache .sass-cache cv/build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
