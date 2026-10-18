@echo off
rem Instala o Hub no PC reserva da sala. Nao precisa de administrador.
cd /d "%~dp0"
echo.
echo  Instalando o Hub dos Analistas...
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo  Nao encontrei o Python. Instale o Python 3.12 ou mais novo
  echo  marcando "Install for me only" e rode este arquivo de novo.
  pause
  exit /b 1
)

%PY% -m venv .venv
if errorlevel 1 ( echo  Falha ao criar o ambiente. & pause & exit /b 1 )
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo  Falha ao instalar as dependencias. Verifique a internet. & pause & exit /b 1 )

rem abre o Hub sozinho quando o Windows iniciar
".venv\Scripts\python.exe" -c "from pathlib import Path; from hub.winsys import set_start_with_windows; set_start_with_windows(True, Path(r'%~dp0.'))"

echo.
echo  Pronto! De dois cliques em iniciar.bat
echo  (o Hub tambem vai abrir sozinho quando o Windows iniciar)
echo.
pause
