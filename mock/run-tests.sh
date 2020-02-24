#!/bin/sh

script=$(readlink -f "$0")
testdir=$(dirname "$script")/tests
sourcedir=$(readlink -f "$testdir/../py")

: "${PYTHON=/usr/bin/python3}"

if test -n "$PYTHONPATH"; then
    PYTHONPATH=$PYTHONPATH:$sourcedir
else
    PYTHONPATH=$sourcedir
fi
export PYTHONPATH

debug() { echo >&2 " * $*" ; }

debug "sourcedir:  $sourcedir"
debug "testdir:    $testdir"
debug "PYTHON:     $PYTHON"
debug "PYTHONPATH: $PYTHONPATH"

"$PYTHON" -B -m pytest --cov-report term-missing --cov "$sourcedir" "$testdir" "$@"
