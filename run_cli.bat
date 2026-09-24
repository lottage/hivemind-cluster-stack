@echo off
title StoneSage Unified LLM Harness CLI (v4.0.6)
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"
python -m harness.cli.main %*

if errorlevel 1 (
    echo.
    echo [!] CLI exited with error code %errorlevel%.
    pause
)
