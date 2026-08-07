#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
work_dir=$(mktemp -d)
trap 'rm -rf -- "$work_dir"' EXIT

user_skills="$work_dir/user-skills"
user_claude="$work_dir/user-claude"

CODEX_SKILLS_DIR="$user_skills" CLAUDE_CONFIG_DIR="$user_claude" "$repo_root/install.sh"
test -f "$user_skills/sovetwave/SKILL.md"
test -f "$user_claude/output-styles/sovetwave.md"

if CODEX_SKILLS_DIR="$user_skills" CLAUDE_CONFIG_DIR="$user_claude" "$repo_root/install.sh"; then
  echo "second user-scope installation unexpectedly succeeded" >&2
  exit 1
fi

CODEX_SKILLS_DIR="$user_skills" CLAUDE_CONFIG_DIR="$user_claude" "$repo_root/install.sh" --force
test -f "$user_skills/sovetwave/scripts/select_voice_cards.py"

target_repo="$work_dir/target-repo"
repo_claude="$work_dir/repo-claude"
mkdir -p "$target_repo/.git"
CLAUDE_CONFIG_DIR="$repo_claude" "$repo_root/install.sh" --codex-scope repo --repo-path "$target_repo"
test -f "$target_repo/.agents/skills/sovetwave/SKILL.md"

if CLAUDE_CONFIG_DIR="$repo_claude" "$repo_root/install.sh" --codex-scope repo --repo-path "$target_repo"; then
  echo "second repo-scope installation unexpectedly succeeded" >&2
  exit 1
fi

CLAUDE_CONFIG_DIR="$repo_claude" "$repo_root/install.sh" --codex-scope repo --repo-path "$target_repo" --force
test -f "$target_repo/.agents/skills/sovetwave/references/voice-core.md"
