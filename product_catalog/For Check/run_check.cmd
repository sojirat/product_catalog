@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%~dp0..\..\.codex-runtime-deps;%PYTHONPATH%"
set "CHECK_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%CHECK_PYTHON%" goto run
set "CHECK_PYTHON=python"
:run
"%CHECK_PYTHON%" "%~dp0validate_po_pop.py" %*
exit /b %errorlevel%
