param([ValidateSet('demo', 'cassandra')][string]$Modo = 'demo')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $pythonLocal = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonLocal)) {
        py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Instale Python 3.10 a 3.14 com Tcl/Tk.' }
    }
    & $pythonLocal main.py --gui --mode $Modo
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível iniciar a janela.' }
}
finally { Pop-Location }
