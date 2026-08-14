param(
  [Parameter(Mandatory = $true)]
  [string]$InputPath,

  [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "export_markdown_to_docx.py"
if (-not (Test-Path -LiteralPath $scriptPath)) {
  throw "Impossible de trouver export_markdown_to_docx.py"
}

$arguments = @($scriptPath, "--input", $InputPath)
if ($OutputPath) {
  $arguments += @("--output", $OutputPath)
}

python @arguments
