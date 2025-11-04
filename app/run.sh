#!/bin/bash
set -e

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to parent directory (project root)
cd "$DIR/.."

export PYTHONPATH=$(pwd)

# Activate virtual environment if exists
if [ -d "app/.venv" ]; then 
    source app/.venv/bin/activate
elif [ -d ".venv" ]; then 
source .venv/bin/activate
fi

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
