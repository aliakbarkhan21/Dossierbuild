@echo off
rem Dossierbuild launcher -- what the desktop shortcut ultimately runs.
rem
rem Keeping the work in a script rather than in the shortcut itself means the
rem shortcut never has to be rebuilt: change the behaviour here and the
rem desktop icon follows.
rem
rem One process. uvicorn serves the API and the built React app from the same
rem port, so there is no Node to start and nothing for the two halves to
rem disagree about. See dossier/api/static.py.
rem
rem Called with /quiet by launch.vbs, which runs this window-less. In that
rem mode nothing may wait for a keypress -- there would be no window to press
rem it in, and the process would hang around invisibly forever.

setlocal
set "QUIET="
if /I "%~1"=="/quiet" set "QUIET=1"
set "PORT=8000"
set "URL=http://127.0.0.1:%PORT%/"

title Dossierbuild
cd /d "%~dp0.."

rem If a server is already up, a second one would fail on the port. Just
rem surface the running app instead.
powershell -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', %PORT%); $c.Close(); exit 1 } catch { exit 0 }"
if errorlevel 1 (
    echo Dossierbuild is already running -- opening it in your browser.
    start "" "%URL%"
    if not defined QUIET ping -n 3 127.0.0.1 >nul
    exit /b 0
)

rem The frontend is served from disk, so a missing build is a blank page with
rem no explanation. Say so here instead.
if not exist "web\dist\index.html" (
    echo.
    echo   The interface has not been built yet.
    echo   Run this once, from the project folder:
    echo.
    echo       cd web ^&^& npm install ^&^& npm run build
    echo.
    if not defined QUIET pause
    exit /b 1
)

echo.
echo   Dossierbuild is starting. Your browser will open in a moment.
echo.

rem Open the browser only once the port answers. Starting it immediately shows
rem a connection error for the second or two uvicorn needs to bind, and the
rem person is then looking at a failure page while the app works fine behind
rem it.
start "" /b powershell -NoProfile -Command ^
  "for ($i = 0; $i -lt 60; $i++) { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', %PORT%); $c.Close(); Start-Process '%URL%'; break } catch { Start-Sleep -Milliseconds 400 } }"

python -m uvicorn dossier.api:app --host 127.0.0.1 --port %PORT%

if defined QUIET exit /b 0
echo.
echo   Dossierbuild has stopped.
pause
