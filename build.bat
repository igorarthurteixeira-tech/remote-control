@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo =========================================
echo  Remote Control — Build do executavel
echo =========================================
echo.

echo [1/4] Instalando PyInstaller...
pip install pyinstaller -q
if errorlevel 1 (
    echo ERRO: Falha ao instalar PyInstaller.
    pause
    exit /b 1
)

echo [2/4] Gerando icone...
python gen_icon.py
if errorlevel 1 (
    echo AVISO: Falha ao gerar icone. Continuando sem icone personalizado.
    set ICON_ARG=
) else (
    set ICON_ARG=--icon "icon.ico"
)

rem Detecta se existe um .apk na pasta para embutir no exe
set APK_ARG=
for %%f in (*.apk) do (
    set APK_ARG=--add-data "%%f;."
    echo APK encontrado: %%f - sera embutido no executavel.
)
if not defined APK_ARG (
    echo Aviso: nenhum .apk encontrado. O executavel nao incluira o app Android.
)
echo.

echo [3/4] Gerando RemoteControlServer.exe ...
python -m PyInstaller --onefile --noconsole --uac-admin --noconfirm ^
  --runtime-tmpdir "C:\ProgramData\RemoteControl" ^
  %ICON_ARG% ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "monitor_control.ps1;." ^
  %APK_ARG% ^
  --name "RemoteControlServer" ^
  server.py

if errorlevel 1 (
    echo.
    echo ERRO: Falha ao gerar o executavel.
    pause
    exit /b 1
)

echo.
echo [4/4] Limpando arquivos temporarios...
if exist "build"                    rmdir /s /q "build"
if exist "RemoteControlServer.spec" del /q "RemoteControlServer.spec"
if exist "icon.ico"                 del /q "icon.ico"

echo.
echo =========================================
echo  Executavel gerado com sucesso!
echo  Local: %~dp0dist\RemoteControlServer.exe
echo =========================================
echo.

echo Abrindo o servidor...
start "" "%~dp0dist\RemoteControlServer.exe"
