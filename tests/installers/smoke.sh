#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
work_dir=$(mktemp -d)
trap 'rm -rf -- "$work_dir"' EXIT

user_skills="$work_dir/user-skills"
user_claude="$work_dir/user-claude"

CODEX_SKILLS_DIR="$user_skills" CLAUDE_CONFIG_DIR="$user_claude" sh "$repo_root/install.sh"
test -f "$user_skills/sovetwave/SKILL.md"
test -f "$user_claude/output-styles/sovetwave.md"

if CODEX_SKILLS_DIR="$user_skills" CLAUDE_CONFIG_DIR="$user_claude" sh "$repo_root/install.sh"; then
  echo "second user-scope installation unexpectedly succeeded" >&2
  exit 1
fi

CODEX_SKILLS_DIR="$user_skills" CLAUDE_CONFIG_DIR="$user_claude" sh "$repo_root/install.sh" --force
test -f "$user_skills/sovetwave/scripts/select_voice_cards.py"

printf '%s\n' 'sentinel' > "$user_skills/sovetwave/.installer-sentinel"
style_target="$user_claude/output-styles/sovetwave.md"
printf '%s\n' 'old-style-sentinel' > "$style_target"
for failure_point in codex claude-style; do
  if SOVETWAVE_TEST_FAIL_AFTER="$failure_point" CODEX_SKILLS_DIR="$user_skills" CLAUDE_CONFIG_DIR="$user_claude" sh "$repo_root/install.sh" --force; then
    echo "injected $failure_point installer failure unexpectedly succeeded" >&2
    exit 1
  fi
  test -f "$user_skills/sovetwave/.installer-sentinel"
  grep -qx 'old-style-sentinel' "$style_target"
  if find "$user_skills" "$user_claude" -type d -name '.sovetwave-stage*' -print -quit | grep -q .; then
    echo "staging directory survived rollback" >&2
    exit 1
  fi
done

target_repo="$work_dir/target-repo"
repo_claude="$work_dir/repo-claude"
mkdir -p "$target_repo/.git"
CLAUDE_CONFIG_DIR="$repo_claude" sh "$repo_root/install.sh" --codex-scope repo --repo-path "$target_repo"
test -f "$target_repo/.agents/skills/sovetwave/SKILL.md"

if CLAUDE_CONFIG_DIR="$repo_claude" sh "$repo_root/install.sh" --codex-scope repo --repo-path "$target_repo"; then
  echo "second repo-scope installation unexpectedly succeeded" >&2
  exit 1
fi

CLAUDE_CONFIG_DIR="$repo_claude" sh "$repo_root/install.sh" --codex-scope repo --repo-path "$target_repo" --force
test -f "$target_repo/.agents/skills/sovetwave/references/voice-core.md"
