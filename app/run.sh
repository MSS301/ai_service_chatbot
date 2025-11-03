#!/bin/bash
set -e
export PYTHONPATH=$(pwd)
if [ -d ".venv" ]; then source .venv/bin/activate; fi
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
