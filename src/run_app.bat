@echo off
powershell -NoProfile -Command "Start-Process cmd -ArgumentList '/k', 'title Bank && python -m src.main' -WindowStyle Normal"