@echo off
python -m pytest -v > test_logs.txt 2>&1
type test_logs.txt