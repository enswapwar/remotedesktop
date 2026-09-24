@echo off

python -m pip install --upgrade pip

python -m pip install -r requirements.txt

pyinstaller ^
    --onefile ^
    --name remote-agent ^
    --console ^
    agent.py

echo.
echo ========================================
echo Build complete
echo ========================================
echo.
echo EXE:
echo dist\remote-agent.exe
echo.

pause
