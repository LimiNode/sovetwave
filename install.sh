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
claude_target="$claude_dir/output-styles/sovetwave.md"

# Preflight every destination before changing any installation target.
for destination in "$codex_target" "$claude_target"; do
  if [ -e "$destination" ] && [ "$force" != true ]; then
    printf '%s\n' "Target exists: $destination. Run again with --force to replace it." >&2
    exit 1
  fi
done

install_item() {
  source_path=$1
  destination=$2
  mkdir -p "$(dirname -- "$destination")"
  if [ "$force" = true ] && [ -e "$destination" ]; then rm -rf -- "$destination"; fi
  cp -R -- "$source_path" "$destination"
  printf '%s\n' "Installed $destination"
}

install_item "$repo_dir/skills/sovetwave" "$codex_target"
install_item "$repo_dir/output-styles/sovetwave.md" "$claude_target"
printf '%s\n' 'Installed Sovetwave output style. In Claude Code run /config, choose Sovetwave under Output style, then run /clear or start a new session.'
