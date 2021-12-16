#! /bin/bash

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

args=()
cov=true
for arg; do
    case $arg in
    --no-cov) cov=false ;;
    *) args+=( "$arg" ) ;;
    esac
done

cov_args=()
if $cov; then
    cov_args=( --cov-report term-missing --cov "$sourcedir" )
fi

set -x
"$PYTHON" -B -m pytest "${cov_args[@]}" "$testdir" "${args[@]}"
