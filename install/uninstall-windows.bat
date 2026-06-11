@echo off
rem  Inkscape Presentation Plugin - Windows uninstaller (double-click to run)
setlocal EnableExtensions
set "DEST=%APPDATA%\inkscape\extensions\pp"

if exist "%DEST%" (
  rmdir /S /Q "%DEST%"
  echo  Removed "%DEST%".
) else (
  echo  Nothing to remove at "%DEST%".
)
echo  Restart Inkscape to finish.
echo(
pause
endlocal
