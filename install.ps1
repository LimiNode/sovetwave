[CmdletBinding()]
param(
    [string]$CodexHome = $env:CODEX_HOME,
    [string]$ClaudeHome = $env:CLAUDE_CONFIG_DIR,
    [switch]$Force
)

$repoRoot = Split-Path -Parent $PSCommandPath
if ([string]::IsNullOrWhiteSpace($CodexHome)) { $CodexHome = Join-Path $HOME '.codex' }
if ([string]::IsNullOrWhiteSpace($ClaudeHome)) { $ClaudeHome = Join-Path $HOME '.claude' }

$targets = @(
    @{ Source = Join-Path $repoRoot 'skills\sovetwave'; Destination = Join-Path $CodexHome 'skills\sovetwave' },
    @{ Source = Join-Path $repoRoot 'output-styles\sovetwave.md'; Destination = Join-Path $ClaudeHome 'output-styles\sovetwave.md' }
)

foreach ($target in $targets) {
    if ((Test-Path -LiteralPath $target.Destination) -and -not $Force) {
        throw "Target exists: $($target.Destination). Run again with -Force to replace it."
    }
    $parent = Split-Path -Parent $target.Destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item -LiteralPath $target.Source -Destination $target.Destination -Recurse -Force:$Force
    Write-Host "Installed $($target.Destination)"
}
