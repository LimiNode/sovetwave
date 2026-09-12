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

$ErrorActionPreference = 'Stop'

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

$staged = @()
$backups = @()
$installed = @()
$committed = $false
$testFailAfter = $env:SOVETWAVE_TEST_FAIL_AFTER
try {
    # Build and validate every replacement before touching an existing install.
    foreach ($target in $targets) {
        if (-not (Test-Path -LiteralPath $target.Source)) { throw "Source does not exist: $($target.Source)" }
        $parent = Split-Path -Parent $target.Destination
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        $stage = Join-Path $parent ('.sovetwave-stage-' + [guid]::NewGuid().ToString('N'))
        # Register the staging path before copying so a partial/failed copy is
        # still removed by the rollback handler.
        $staged += @{ Target = $target; Path = $stage }
        Copy-Item -LiteralPath $target.Source -Destination $stage -Recurse
        if (-not (Test-Path -LiteralPath $stage)) { throw "Staged copy is missing: $stage" }
    }

    for ($index = 0; $index -lt $staged.Count; $index++) {
        $item = $staged[$index]
        $target = $item.Target
        if (Test-Path -LiteralPath $target.Destination) {
            if (-not $Force) { throw "Target exists: $($target.Destination). Run again with -Force to replace it." }
            $backup = $target.Destination + '.sovetwave-backup-' + [guid]::NewGuid().ToString('N')
            Move-Item -LiteralPath $target.Destination -Destination $backup
            $backups += @{ Target = $target; Path = $backup }
        }
        Move-Item -LiteralPath $item.Path -Destination $target.Destination
        $installed += $target
        Write-Host "Installed $($target.Destination)"
        $failurePoint = if ($target.Destination -eq (Join-Path $CodexSkillsHome 'sovetwave')) {
            'codex'
        } elseif ($target.Source -eq (Join-Path $repoRoot 'output-styles\sovetwave.md')) {
            'claude-style'
        } else {
            'claude-skill'
        }
        if ($testFailAfter -eq $failurePoint) { throw "Injected installer failure after $failurePoint replacement." }
    }
    $committed = $true
}
catch {
    if (-not $committed) {
        foreach ($target in $installed) {
            if (Test-Path -LiteralPath $target.Destination) { Remove-Item -LiteralPath $target.Destination -Recurse -Force }
        }
        foreach ($backup in ($backups | Sort-Object { $_.Path } -Descending)) {
            if (Test-Path -LiteralPath $backup.Path) { Move-Item -LiteralPath $backup.Path -Destination $backup.Target.Destination }
        }
        foreach ($item in $staged) {
            if (Test-Path -LiteralPath $item.Path) { Remove-Item -LiteralPath $item.Path -Recurse -Force }
        }
    }
    throw
}

foreach ($backup in $backups) {
    try { Remove-Item -LiteralPath $backup.Path -Recurse -Force -ErrorAction Stop }
    catch { Write-Warning "Could not remove backup $($backup.Path): $($_.Exception.Message)" }
}

Write-Host 'Installed Sovetwave output style. In Claude Code run /config, choose Sovetwave under Output style, then run /clear or start a new session.'
