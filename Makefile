# Makefile for deepfake detection project

.PHONY: dev-setup test clean

dev-setup:
	python3.9 -m pip install -e .
	python3.9 -m pip install -q pytest

test:
	python3.9 -m pytest -q

clean:
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/
	rm -rf *.egg-info/