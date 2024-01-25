#!/bin/bash
set -e

cov=`poetry run coverage report --format=total`

if [[ "$cov" -eq "100" ]]
then
    exit 0;
else
    echo "Test coverage only $cov%"
    exit 1;
fi
