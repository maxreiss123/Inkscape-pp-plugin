@echo off
rem ============================================================================
rem  Inkscape Presentation Plugin - Windows installer (double-click to run)
rem  Copies the plugin into %APPDATA%\inkscape\extensions\pp
rem ============================================================================
setlocal EnableExtensions

set "SRC=%~dp0..\src\pp"
set "EXTROOT=%APPDATA%\inkscape\extensions"
set "DEST=%EXTROOT%\pp"

echo(
echo  Inkscape Presentation Plugin - installer
echo  ----------------------------------------
echo   From: "%SRC%"
echo   To:   "%DEST%"
echo(

if not exist "%SRC%\pp_setup.inx" (
  echo  ERROR: plugin files not found next to this script.
  echo  Please run install-windows.bat from the repository's "install" folder.
  echo(
  pause
  exit /b 1
)

if not exist "%EXTROOT%" mkdir "%EXTROOT%"
if exist "%DEST%" rmdir /S /Q "%DEST%"

xcopy /E /I /Y "%SRC%" "%DEST%" >nul
if errorlevel 1 (
  echo  ERROR: copying the files failed.
  echo(
  pause
  exit /b 1
)

echo  Installed successfully.
echo(
echo  Next steps:
echo   1. Restart Inkscape.
echo   2. Find the tools under  Extensions ^> Presentation.
echo(
echo  Optional (for PowerPoint/HTML export and font embedding):
echo   install the Python packages "cairosvg" and "fonttools" into Inkscape's
echo   Python. The easiest way is to run, in PowerShell, from this folder:
echo       powershell -ExecutionPolicy Bypass -File Install-Windows.ps1 -WithExtras
echo(
pause
endlocal
