@echo off
rem Dossierbuild launcher -- what the desktop shortcut ultimately runs.
rem
rem Keeping the work in a script rather than in the shortcut itself means the
rem shortcut never has to be rebuilt: change the behaviour here and the
rem desktop icon follows.
rem
rem Called with /quiet by launch.vbs, which runs this window-less. In that
rem mode nothing may wait for a keypress -- there would be no window to press
rem it in, and the process would hang around invisibly forever.

setlocal
set "QUIET="
if /I "%~1"=="/quiet" set "QUIET=1"

title Dossierbuild
cd /d "%~dp0.."

rem If a server is already up on 8501, a second one would fail on the port.
rem Just surface the running app instead.
powershell -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', 8501); $c.Close(); exit 1 } catch { exit 0 }"
if errorlevel 1 (
    echo Dossierbuild is already running -- opening it in your browser.
    start "" "http://localhost:8501/"
    if not defined QUIET (
        rem ping rather than timeout: timeout aborts when stdin is redirected.
        ping -n 3 127.0.0.1 >nul
    )
    exit /b 0
)

echo.
echo   Dossierbuild is starting. Your browser will open in a moment.
echo   Close this window when you are done -- it stops the app.
echo.

rem --server.headless=false overrides the headless setting in
rem .streamlit/config.toml so Streamlit opens the browser itself.
python -m streamlit run app.py --server.headless=false

if defined QUIET exit /b 0
echo.
echo   Dossierbuild has stopped.
pause
