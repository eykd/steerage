#!/bin/sh
set -e
set -x
poetry run pytest \
    -vv \
    --new-first \
    --last-failed \
    --exitfirst \
    --disable-warnings \
    "$@"
