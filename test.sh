#!/usr/bin/env bash

set -ex

pip3 install flake8==3.5.0 pylint==2.3.0

pylint -E *.py
flake8 *.py
