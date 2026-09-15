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
rem It also stops on its own. The page heartbeats while it is open and says so
rem when it closes; the server exits a few seconds later. That is what a
rem desktop app does, and it is why there is no "stop" icon any more.
rem See dossier/api/lifetime.py.
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

rem If a server is already up, a second one would fail on the port -- so this
rem used to just open the browser at whatever was there. That is wrong when
rem "whatever was there" is older than the folder it was started from.
rem
rem A server holds its own Python in memory for as long as it runs. Static
rem files are read from disk per request, so a rebuild reaches the browser
rem immediately, but the API does not: the shortcut would hand you a new
rem frontend talking to an old backend, which looks like the app losing
rem features rather than like a stale process. That is exactly how a CV list
rem grouped by a field the server had never heard of came out blank.
rem
rem So: ask what is running before adopting it. 0 = nothing there, 1 = ours
rem and current, 2 = stale and now stopped.
for /f "usebackq delims=" %%v in (`python -c "import dossier; print(dossier.__version__)"`) do set "SRC_VERSION=%%v"
powershell -NoProfile -Command ^
  "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', %PORT%); $c.Close() } catch { exit 0 };" ^
  "$live = ''; try { $live = (Invoke-RestMethod -Uri '%URL%api/health' -TimeoutSec 5).version } catch { };" ^
  "if ($live -and $live -eq $env:SRC_VERSION) { exit 1 };" ^
  "Write-Host ''; Write-Host '  A stale Dossierbuild (version' $live ') is still running.';" ^
  "Write-Host '  Stopping it so version' $env:SRC_VERSION 'can start.'; Write-Host '';" ^
  "try { Invoke-RestMethod -Method Post -Uri '%URL%api/leaving' -TimeoutSec 3 | Out-Null } catch { };" ^
  "for ($i = 0; $i -lt 20; $i++) { Start-Sleep -Milliseconds 400;" ^
  "  try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', %PORT%); $c.Close() } catch { exit 2 } };" ^
  "$owner = (Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue).OwningProcess;" ^
  "if ($owner) { Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800 };" ^
  "exit 2"
if errorlevel 2 goto :start
if errorlevel 1 (
    echo Dossierbuild is already running -- opening it in your browser.
    start "" "%URL%"
    if not defined QUIET ping -n 3 127.0.0.1 >nul
    exit /b 0
)

:start

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

set "DOSSIER_EXIT_WHEN_IDLE=1"
python -m uvicorn dossier.api:app --host 127.0.0.1 --port %PORT%

if defined QUIET exit /b 0
echo.
echo   Dossierbuild has stopped.
pause
