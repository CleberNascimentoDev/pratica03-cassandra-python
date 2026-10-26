param([ValidateSet('demo', 'cassandra')][string]$Modo = 'demo')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $pythonLocal = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonLocal)) {
        Write-Host 'Criando ambiente virtual do projeto...'
        py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Não foi possível criar .venv. Instale Python 3.10 a 3.14.' }
    }
    & $pythonLocal main.py --mode $Modo
    if ($LASTEXITCODE -ne 0) { throw 'A aplicação não iniciou. Consulte a mensagem acima.' }
}
finally { Pop-Location }
