@echo off
rem Abre o Hub (sem janela preta) e a TV em tela cheia. Se ja estiver aberto, so mostra a TV.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo  O Hub ainda nao foi instalado. Rode instalar.bat primeiro.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m hub
