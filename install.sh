#!/usr/bin/env sh
set -eu

force=false
if [ "${1:-}" = "--force" ]; then force=true; fi

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
codex_dir=${CODEX_HOME:-"$HOME/.codex"}
claude_dir=${CLAUDE_CONFIG_DIR:-"$HOME/.claude"}

install_item() {
  source_path=$1
  destination=$2
  if [ -e "$destination" ] && [ "$force" != true ]; then
    printf '%s\n' "Target exists: $destination. Run again with --force to replace it." >&2
    exit 1
  fi
  mkdir -p "$(dirname -- "$destination")"
  if [ "$force" = true ]; then rm -rf -- "$destination"; fi
  cp -R -- "$source_path" "$destination"
  printf '%s\n' "Installed $destination"
}

install_item "$repo_dir/skills/sovetwave" "$codex_dir/skills/sovetwave"
install_item "$repo_dir/output-styles/sovetwave.md" "$claude_dir/output-styles/sovetwave.md"
