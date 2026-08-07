$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$temporaryRoot = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { [System.IO.Path]::GetTempPath() } else { $env:RUNNER_TEMP }
$workDir = Join-Path $temporaryRoot ('sovetwave-installer-' + [guid]::NewGuid().ToString('N'))
$userSkills = Join-Path $workDir 'user-skills'
$userClaude = Join-Path $workDir 'user-claude'
$targetRepo = Join-Path $workDir 'target-repo'
$repoClaude = Join-Path $workDir 'repo-claude'

try {
    New-Item -ItemType Directory -Force -Path (Join-Path $targetRepo '.git') | Out-Null

    $previousSkillsDir = $env:CODEX_SKILLS_DIR
    $env:CODEX_SKILLS_DIR = $userSkills
    try {
        & (Join-Path $repoRoot 'install.ps1') -ClaudeHome $userClaude
        if (-not (Test-Path -LiteralPath (Join-Path $userSkills 'sovetwave\SKILL.md'))) { throw 'User-scope skill was not installed.' }
        if (-not (Test-Path -LiteralPath (Join-Path $userClaude 'output-styles\sovetwave.md'))) { throw 'Claude output style was not installed.' }

        $rejected = $false
        try { & (Join-Path $repoRoot 'install.ps1') -ClaudeHome $userClaude } catch { $rejected = $true }
        if (-not $rejected) { throw 'Second user-scope installation unexpectedly succeeded.' }

        & (Join-Path $repoRoot 'install.ps1') -ClaudeHome $userClaude -Force
        if (-not (Test-Path -LiteralPath (Join-Path $userSkills 'sovetwave\scripts\select_voice_cards.py'))) { throw 'Forced user-scope installation is incomplete.' }
    }
    finally {
        $env:CODEX_SKILLS_DIR = $previousSkillsDir
    }

    & (Join-Path $repoRoot 'install.ps1') -CodexScope Repo -RepoPath $targetRepo -ClaudeHome $repoClaude
    if (-not (Test-Path -LiteralPath (Join-Path $targetRepo '.agents\skills\sovetwave\SKILL.md'))) { throw 'Repo-scope skill was not installed.' }

    $rejected = $false
    try { & (Join-Path $repoRoot 'install.ps1') -CodexScope Repo -RepoPath $targetRepo -ClaudeHome $repoClaude } catch { $rejected = $true }
    if (-not $rejected) { throw 'Second repo-scope installation unexpectedly succeeded.' }

    & (Join-Path $repoRoot 'install.ps1') -CodexScope Repo -RepoPath $targetRepo -ClaudeHome $repoClaude -Force
    if (-not (Test-Path -LiteralPath (Join-Path $targetRepo '.agents\skills\sovetwave\references\voice-core.md'))) { throw 'Forced repo-scope installation is incomplete.' }
}
finally {
    Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue
}
