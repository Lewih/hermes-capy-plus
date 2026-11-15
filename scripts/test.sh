#!/bin/sh
# Offline tests (install into a temp HERMES_HOME, pet.json consistency, desktop JS syntax).
exec "$(dirname "$0")/../tests/run.sh" "$@"
