@echo off
rem Levanta la API en modo desarrollo (se recarga sola al guardar cambios).
rem Escucha en toda la red (0.0.0.0): otros equipos de la misma red pueden entrar con http://TU_IP:8000
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
.venv\Scripts\alembic upgrade head || exit /b 1

echo.
echo  Cumulonimbus disponible en:
echo    En este equipo:       http://localhost:8000
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do call :mostrar_ip %%a
echo  (si otro equipo no abre la pagina, revisa el Firewall de Windows y que ambos esten en la misma red)
echo.

.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
exit /b

:mostrar_ip
echo    Desde otro equipo:    http://%1:8000
exit /b
