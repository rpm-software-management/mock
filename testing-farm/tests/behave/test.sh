#!/bin/sh -eux

cd ../../../behave
install-mock-packages-built-by-packit mock-core-configs mock
behave
