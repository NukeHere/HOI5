@echo off
setlocal
pushd "%~dp0"
set PYTHONUTF8=1
"%~dp0.venv\Scripts\python.exe" "%~dp0simulate_ai.py" %*
set "simulation_exit=%ERRORLEVEL%"
popd
exit /b %simulation_exit%
