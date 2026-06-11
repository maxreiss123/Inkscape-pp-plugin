<#
.SYNOPSIS
    Install (or uninstall) the Inkscape Presentation Plugin on Windows.

.DESCRIPTION
    Copies src\pp into %APPDATA%\inkscape\extensions\pp. With -WithExtras it also
    installs the optional Python packages (cairosvg, fonttools) used by the
    PowerPoint / HTML exports and font embedding, into Inkscape's bundled Python
    when it can be found (otherwise the Python on PATH).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File Install-Windows.ps1
    powershell -ExecutionPolicy Bypass -File Install-Windows.ps1 -WithExtras
    powershell -ExecutionPolicy Bypass -File Install-Windows.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [switch]$Uninstall,
    [switch]$WithExtras
)

$ErrorActionPreference = "Stop"

$src     = Join-Path $PSScriptRoot "..\src\pp"
$extRoot = Join-Path $env:APPDATA "inkscape\extensions"
$dest    = Join-Path $extRoot "pp"

if ($Uninstall) {
    if (Test-Path $dest) {
        Remove-Item -Recurse -Force $dest
        Write-Host "Removed $dest"
    } else {
        Write-Host "Nothing to remove at $dest"
    }
    return
}

if (-not (Test-Path (Join-Path $src "pp_setup.inx"))) {
    throw "Plugin files not found at '$src'. Run this from the repository's install\ folder."
}

New-Item -ItemType Directory -Force -Path $extRoot | Out-Null
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
Copy-Item -Recurse -Force $src $dest
Write-Host "Installed to $dest"

if ($WithExtras) {
    $candidates = @(
        (Join-Path $env:ProgramFiles "Inkscape\bin\python.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inkscape\bin\python.exe"),
        "C:\Program Files\Inkscape\bin\python.exe"
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

    $py = $candidates | Select-Object -First 1
    if (-not $py) {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $py = $cmd.Source }
    }

    if ($py) {
        Write-Host "Installing optional packages (cairosvg, fonttools) with: $py"
        & $py -m pip install --user cairosvg fonttools
    } else {
        Write-Warning "No Python found. Install 'cairosvg' and 'fonttools' into Inkscape's Python manually for PPTX/HTML export."
    }
}

Write-Host ""
Write-Host "Done. Restart Inkscape -> Extensions > Presentation."
