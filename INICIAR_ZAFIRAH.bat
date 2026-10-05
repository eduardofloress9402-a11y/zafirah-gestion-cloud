@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Preparando ZAFIRAH Gestion por primera vez...
  py -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000"
echo.
echo ZAFIRAH Gestion esta funcionando.
echo No cierres esta ventana mientras uses el sistema.
echo Para terminar, presiona CTRL+C.
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
endlocal
