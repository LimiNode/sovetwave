[CmdletBinding()]
param(
    [string]$CodexSkillsHome = $env:CODEX_SKILLS_DIR,
    [string]$ClaudeHome = $env:CLAUDE_CONFIG_DIR,
    [ValidateSet('User', 'Repo')]
    [string]$CodexScope = 'User',
    [string]$RepoPath,
    [switch]$LegacyCodex,
    [switch]$Force
)

$repoRoot = Split-Path -Parent $PSCommandPath

if ($LegacyCodex) {
    if ($CodexScope -eq 'Repo') { throw '-LegacyCodex cannot be combined with -CodexScope Repo.' }
    $legacyHome = $env:CODEX_HOME
    if ([string]::IsNullOrWhiteSpace($legacyHome)) { $legacyHome = Join-Path $HOME '.codex' }
    $CodexSkillsHome = Join-Path $legacyHome 'skills'
}
elseif ($CodexScope -eq 'Repo') {
    if ([string]::IsNullOrWhiteSpace($RepoPath)) { throw '-RepoPath is required when -CodexScope Repo.' }
    $resolvedRepoPath = (Resolve-Path -LiteralPath $RepoPath -ErrorAction Stop).Path
    if (-not (Test-Path -LiteralPath (Join-Path $resolvedRepoPath '.git'))) {
        throw "-RepoPath must point to a Git repository: $resolvedRepoPath"
    }
    $CodexSkillsHome = Join-Path $resolvedRepoPath '.agents\skills'
}
elseif ([string]::IsNullOrWhiteSpace($CodexSkillsHome)) {
    $CodexSkillsHome = Join-Path $HOME '.agents\skills'
}

if ([string]::IsNullOrWhiteSpace($ClaudeHome)) { $ClaudeHome = Join-Path $HOME '.claude' }

$targets = @(
    @{ Source = Join-Path $repoRoot 'skills\sovetwave'; Destination = Join-Path $CodexSkillsHome 'sovetwave' },
    @{ Source = Join-Path $repoRoot 'output-styles\sovetwave.md'; Destination = Join-Path $ClaudeHome 'output-styles\sovetwave.md' }
)

# Preflight every destination before changing any installation target.
foreach ($target in $targets) {
    if ((Test-Path -LiteralPath $target.Destination) -and -not $Force) {
        throw "Target exists: $($target.Destination). Run again with -Force to replace it."
    }
}

foreach ($target in $targets) {
    $parent = Split-Path -Parent $target.Destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null

    if ($Force -and (Test-Path -LiteralPath $target.Destination)) {
        Remove-Item -LiteralPath $target.Destination -Recurse -Force
    }

    Copy-Item -LiteralPath $target.Source -Destination $target.Destination -Recurse
    Write-Host "Installed $($target.Destination)"
}

Write-Host 'Installed Sovetwave output style. In Claude Code run /config, choose Sovetwave under Output style, then run /clear or start a new session.'
