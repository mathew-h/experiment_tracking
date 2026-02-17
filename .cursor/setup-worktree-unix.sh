#!/usr/bin/env bash
set -euo pipefail

echo "[worktree-setup] Starting worktree setup."

if [[ -z "${ROOT_WORKTREE_PATH:-}" ]]; then
  echo "[worktree-setup] ROOT_WORKTREE_PATH is not set." >&2
  exit 1
fi

# 1) Create isolated venv in the worktree
if [[ ! -d ".venv" ]]; then
  echo "[worktree-setup] Creating .venv"
  python3 -m venv .venv
fi

PY="./.venv/bin/python"

echo "[worktree-setup] Upgrading pip"
"$PY" -m pip install --upgrade pip

echo "[worktree-setup] Installing requirements.txt"
"$PY" -m pip install -r requirements.txt

# 2) Ensure .env exists in worktree
if [[ -f "$ROOT_WORKTREE_PATH/.env" ]]; then
  cp "$ROOT_WORKTREE_PATH/.env" .env
  echo "[worktree-setup] Copied .env from ROOT_WORKTREE_PATH."
elif [[ -f "$ROOT_WORKTREE_PATH/.env.example" ]]; then
  cp "$ROOT_WORKTREE_PATH/.env.example" .env
  echo "[worktree-setup] Root .env not found; copied .env.example to .env."
else
  : > .env
  echo "[worktree-setup] Root .env and .env.example not found; created empty .env."
fi

# 3) Ensure DATABASE_URL safe for parallel agents (sqlite => worktree-local file)
DEFAULT_SQLITE_URL="sqlite:///./experiments_worktree.db"

if ! grep -qE '^[[:space:]]*DATABASE_URL[[:space:]]*=' .env; then
  echo "[worktree-setup] DATABASE_URL missing; setting to per-worktree sqlite DB."
  printf "\nDATABASE_URL=%s\n" "$DEFAULT_SQLITE_URL" >> .env
else
  DB_URL="$(python3 - <<'PY'
import re
text = open(".env", "r", encoding="utf-8", errors="ignore").read()
m = re.search(r'(?m)^\s*DATABASE_URL\s*=\s*(.*)\s*$', text)
print((m.group(1).strip() if m else ""))
PY
)"
  if [[ "$DB_URL" == sqlite* ]] || [[ "$DB_URL" == "postgresql://user:password@localhost:5432/dbname" ]]; then
    echo "[worktree-setup] Rewriting DATABASE_URL to per-worktree sqlite DB."
    python3 - <<PY
import re
path = ".env"
text = open(path, "r", encoding="utf-8", errors="ignore").read()
text = re.sub(r'(?m)^\s*DATABASE_URL\s*=.*$', 'DATABASE_URL=$DEFAULT_SQLITE_URL', text)
open(path, "w", encoding="utf-8").write(text)
PY
  fi
fi

# 4) Run migrations into the worktree-local DB
echo "[worktree-setup] Running alembic upgrade head"
"$PY" -m alembic upgrade head

echo "[worktree-setup] Worktree setup complete."

