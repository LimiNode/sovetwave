#!/usr/bin/env sh
set -eu

force=false
legacy_codex=false
codex_scope=user
repo_path=

while [ "$#" -gt 0 ]; do
  argument=$1
  case "$argument" in
    --force) force=true ;;
    --legacy-codex) legacy_codex=true ;;
    --codex-scope)
      shift
      [ "$#" -gt 0 ] || { printf '%s\n' '--codex-scope requires user or repo' >&2; exit 2; }
      codex_scope=$1
      ;;
    --repo-path)
      shift
      [ "$#" -gt 0 ] || { printf '%s\n' '--repo-path requires a Git repository path' >&2; exit 2; }
      repo_path=$1
      ;;
    *) printf '%s\n' "Unknown option: $argument" >&2; exit 2 ;;
  esac
  shift
done

case "$codex_scope" in user|repo) ;; *) printf '%s\n' '--codex-scope must be user or repo' >&2; exit 2 ;; esac
if [ "$legacy_codex" = true ] && [ "$codex_scope" = repo ]; then
  printf '%s\n' '--legacy-codex cannot be combined with --codex-scope repo' >&2
  exit 2
fi

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$legacy_codex" = true ]; then
  codex_home=${CODEX_HOME:-"$HOME/.codex"}
  codex_skills_dir="$codex_home/skills"
elif [ "$codex_scope" = repo ]; then
  [ -n "$repo_path" ] || { printf '%s\n' '--repo-path is required when --codex-scope repo' >&2; exit 2; }
  repo_path=$(CDPATH= cd -- "$repo_path" && pwd)
  [ -e "$repo_path/.git" ] || { printf '%s\n' "--repo-path must point to a Git repository: $repo_path" >&2; exit 2; }
  codex_skills_dir="$repo_path/.agents/skills"
else
  codex_skills_dir=${CODEX_SKILLS_DIR:-"$HOME/.agents/skills"}
fi
claude_dir=${CLAUDE_CONFIG_DIR:-"$HOME/.claude"}
codex_target="$codex_skills_dir/sovetwave"
claude_skill_target="$claude_dir/skills/sovetwave"
claude_target="$claude_dir/output-styles/sovetwave.md"

# Preflight every destination before changing any installation target.
for destination in "$codex_target" "$claude_skill_target" "$claude_target"; do
  if [ -e "$destination" ] && [ "$force" != true ]; then
    printf '%s\n' "Target exists: $destination. Run again with --force to replace it." >&2
    exit 1
  fi
done

codex_parent=$(dirname -- "$codex_target")
claude_skill_parent=$(dirname -- "$claude_skill_target")
claude_parent=$(dirname -- "$claude_target")
mkdir -p "$codex_parent" "$claude_skill_parent" "$claude_parent"
stage_root=
stage_claude_skill=
stage_claude=
codex_stage=
claude_skill_stage=
claude_stage=
codex_backup=
claude_skill_backup=
claude_backup=
codex_installed=false
claude_skill_installed=false
claude_installed=false
committed=false
test_fail_after=${SOVETWAVE_TEST_FAIL_AFTER:-}
cleanup_staging() {
  [ -z "$stage_root" ] || rm -rf -- "$stage_root" || true
  [ -z "$stage_claude_skill" ] || rm -rf -- "$stage_claude_skill" || true
  [ -z "$stage_claude" ] || rm -rf -- "$stage_claude" || true
}
rollback() {
  if [ "$committed" = true ]; then return; fi
  if [ "$codex_installed" = true ] && [ -e "$codex_target" ]; then rm -rf -- "$codex_target" || true; fi
  if [ "$claude_skill_installed" = true ] && [ -e "$claude_skill_target" ]; then rm -rf -- "$claude_skill_target" || true; fi
  if [ "$claude_installed" = true ] && [ -e "$claude_target" ]; then rm -rf -- "$claude_target" || true; fi
  if [ -n "$codex_backup" ] && [ -e "$codex_backup" ]; then mv -- "$codex_backup" "$codex_target" || true; fi
  if [ -n "$claude_skill_backup" ] && [ -e "$claude_skill_backup" ]; then mv -- "$claude_skill_backup" "$claude_skill_target" || true; fi
  if [ -n "$claude_backup" ] && [ -e "$claude_backup" ]; then mv -- "$claude_backup" "$claude_target" || true; fi
  cleanup_staging
}
trap rollback EXIT
stage_root=$(mktemp -d "$codex_parent/.sovetwave-stage.XXXXXX")
stage_claude_skill=$(mktemp -d "$claude_skill_parent/.sovetwave-stage.XXXXXX")
stage_claude=$(mktemp -d "$claude_parent/.sovetwave-stage.XXXXXX")
codex_stage="$stage_root/sovetwave"
claude_skill_stage="$stage_claude_skill/sovetwave"
claude_stage="$stage_claude/sovetwave.md"

cp -R -- "$repo_dir/skills/sovetwave" "$codex_stage"
cp -R -- "$repo_dir/skills/sovetwave" "$claude_skill_stage"
cp -- "$repo_dir/output-styles/sovetwave.md" "$claude_stage"
test -f "$codex_stage/SKILL.md" -a -f "$claude_skill_stage/SKILL.md" -a -f "$claude_stage"

if [ -e "$codex_target" ]; then
  codex_backup="$codex_target.sovetwave-backup.$$"
  mv -- "$codex_target" "$codex_backup"
fi
if [ -e "$claude_target" ]; then
  claude_backup="$claude_target.sovetwave-backup.$$"
  mv -- "$claude_target" "$claude_backup"
fi
if [ -e "$claude_skill_target" ]; then
  claude_skill_backup="$claude_skill_target.sovetwave-backup.$$"
  mv -- "$claude_skill_target" "$claude_skill_backup"
fi
mv -- "$codex_stage" "$codex_target"
codex_installed=true
if [ "$test_fail_after" = codex ]; then
  printf '%s\n' 'Injected installer failure after Codex replacement.' >&2
  exit 97
fi
mv -- "$claude_skill_stage" "$claude_skill_target"
claude_skill_installed=true
mv -- "$claude_stage" "$claude_target"
claude_installed=true
if [ "$test_fail_after" = claude-style ]; then
  printf '%s\n' 'Injected installer failure after claude-style replacement.' >&2
  exit 97
fi
committed=true
trap - EXIT
if [ -n "$codex_backup" ] && ! rm -rf -- "$codex_backup"; then printf '%s\n' "Warning: could not remove backup $codex_backup" >&2; fi
if [ -n "$claude_skill_backup" ] && ! rm -rf -- "$claude_skill_backup"; then printf '%s\n' "Warning: could not remove backup $claude_skill_backup" >&2; fi
if [ -n "$claude_backup" ] && ! rm -rf -- "$claude_backup"; then printf '%s\n' "Warning: could not remove backup $claude_backup" >&2; fi
if ! cleanup_staging; then printf '%s\n' 'Warning: could not remove installer staging directory.' >&2; fi
printf '%s\n' "Installed $codex_target" "Installed $claude_skill_target" "Installed $claude_target"
printf '%s\n' 'Installed Sovetwave output style. In Claude Code run /config, choose Sovetwave under Output style, then run /clear or start a new session.'
