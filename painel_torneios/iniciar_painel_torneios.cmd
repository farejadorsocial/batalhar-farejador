@echo off
cd /d "%~dp0"
if not exist node_modules (
  echo Instalando dependencias...
  call npm install
)
echo.
echo Painel de Gestao de Torneios: http://127.0.0.1:5175
echo.
call npm run dev -- --port 5175
pause
