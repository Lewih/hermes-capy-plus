#!/bin/sh
# Offline test suite (~1 s): plugin install logic, sheet geometry, desktop plugin syntax.
set -e
cd "$(dirname "$0")"
uv run --no-project --with pytest --with pillow python -m pytest -q -c pytest.ini --rootdir . .
node --input-type=module --check < ../desktop/plugin.js && echo "desktop/plugin.js: syntax ok"
