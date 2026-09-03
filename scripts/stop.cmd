@echo off
rem Stops the background Dossierbuild server started by the desktop shortcut.
rem Only needed because the shortcut runs window-less -- there is no console
rem to close.

echo Stopping Dossierbuild...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":8501 .*LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)
echo Done.
ping -n 2 127.0.0.1 >nul
