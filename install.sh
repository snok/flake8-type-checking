#!/usr/bin/env bash

poetry build
pip install .
flake8
