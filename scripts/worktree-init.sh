#!/usr/bin/env bash
# worktree 作成時にメインリポジトリのファイル・ディレクトリへシンボリックリンクを張り、
# 依存パッケージを同期する。post-checkout フックから呼び出す。
export PATH="$HOME/.nix-profile/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

GIT_DIR=$(git rev-parse --git-dir)
COMMON_DIR=$(git rev-parse --git-common-dir)

# worktree でない場合は何もしない
if [ "$GIT_DIR" = "$COMMON_DIR" ]; then
  exit 0
fi

ROOT="$(dirname "$COMMON_DIR")"

# .envrc / .env はコピー（worktree ごとに独立した環境変数を持てるように）
if [ ! -e "$(pwd)/.envrc" ] && [ -e "$ROOT/.envrc" ]; then
  cp "$ROOT/.envrc" "$(pwd)/.envrc"
fi
if [ ! -e "$(pwd)/.env" ] && [ -e "$ROOT/.env" ]; then
  cp "$ROOT/.env" "$(pwd)/.env"
fi

# .claude はシンボリックリンク（設定を共有）
if [ ! -e "$(pwd)/.claude" ]; then
  ln -sfn "$ROOT/.claude" "$(pwd)/.claude"
fi

# SYSDEN_DATA はシンボリックリンク（データディレクトリを共有）
DATA_DIR="${SYSDEN_DATA:-$ROOT/.data}"
if [ ! -e "$(pwd)/.data" ] && [ -e "$DATA_DIR" ]; then
  ln -sfn "$DATA_DIR" "$(pwd)/.data"
fi

# .dagayn はコピー（ビルド済みグラフを再利用）
if [ ! -e "$(pwd)/.dagayn" ] && [ -e "$ROOT/.dagayn" ]; then
  cp -r "$ROOT/.dagayn" "$(pwd)/.dagayn"
fi

uv sync
