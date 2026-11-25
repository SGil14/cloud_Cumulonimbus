@echo off
rem Compila el front si hace falta, abre el navegador y levanta la app en http://localhost:8000
cd /d "%~dp0"
if not exist frontend\dist (
  echo Compilando el frontend por primera vez...
  pushd frontend
  call npm install || exit /b 1
  call npm run build || exit /b 1
  popd
)
start "" http://localhost:8000
call backend\iniciar.bat
