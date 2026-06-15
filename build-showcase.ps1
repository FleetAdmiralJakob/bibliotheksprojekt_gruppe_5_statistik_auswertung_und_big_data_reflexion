[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$pyInstallerVersion = "6.21.0"
$applicationName = "Bibliothekskatalog"

function Invoke-Uv {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & uv @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "uv $($Arguments -join ' ') ist mit Exitcode $LASTEXITCODE fehlgeschlagen."
    }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv wurde nicht gefunden. Installation: https://docs.astral.sh/uv/"
}

Push-Location $projectRoot
try {
    Write-Host "Synchronisiere Projektabhaengigkeiten..."
    Invoke-Uv -Arguments @("sync", "--frozen")

    Write-Host "Erzeuge $applicationName.exe..."
    Invoke-Uv -Arguments @(
        "run",
        "--frozen",
        "--with", "pyinstaller==$pyInstallerVersion",
        "pyinstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", $applicationName,
        "--distpath", (Join-Path $projectRoot "dist"),
        "--workpath", (Join-Path $projectRoot "build\pyinstaller"),
        "--specpath", (Join-Path $projectRoot "build\pyinstaller"),
        "--add-data", "$projectRoot\bibliothek.db;.",
        "--add-data", "$projectRoot\src\desktop\assets\Logo Bibliothek.png;src\desktop\assets",
        "--add-data", "$projectRoot\src\server\sql_scripts\create_database.sql;src\server\sql_scripts",
        "--hidden-import", "uvicorn.loops.asyncio",
        "--hidden-import", "uvicorn.protocols.http.h11_impl",
        "--hidden-import", "uvicorn.lifespan.on",
        (Join-Path $projectRoot "showcase_main.py")
    )

    $executable = Join-Path $projectRoot "dist\$applicationName.exe"
    Write-Host ""
    Write-Host "Fertig: $executable"
    Write-Host "Diese Datei kann ohne Python-Installation gestartet werden."
}
finally {
    Pop-Location
}
