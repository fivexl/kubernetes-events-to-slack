#!/usr/bin/env bash

set -ex

pip3 install flake8==3.8.4 pylint==2.6.0

pylint -E *.py
flake8 *.py
