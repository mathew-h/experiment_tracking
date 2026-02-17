$ErrorActionPreference = 'Stop'

function Write-Info([string]$msg) {
  Write-Host "[worktree-setup] $msg"
}

function Ensure-EnvFile([string]$rootPath) {
  $rootEnv = Join-Path $rootPath ".env"
  $rootEnvExample = Join-Path $rootPath ".env.example"

  if (Test-Path $rootEnv) {
    Copy-Item $rootEnv ".env" -Force
    Write-Info "Copied .env from ROOT_WORKTREE_PATH."
    return
  }

  if (Test-Path $rootEnvExample) {
    Copy-Item $rootEnvExample ".env" -Force
    Write-Info "Root .env not found; copied .env.example to .env."
    return
  }

  New-Item -ItemType File -Path ".env" -Force | Out-Null
  Write-Info "Root .env and .env.example not found; created empty .env."
}

function Get-EnvValue([string]$text, [string]$key) {
  $m = [regex]::Match($text, "(?m)^\s*$([regex]::Escape($key))\s*=\s*(?<v>.*)\s*$")
  if (-not $m.Success) { return $null }
  return $m.Groups["v"].Value.Trim()
}

function Set-EnvValue([string]$text, [string]$key, [string]$value) {
  $pattern = "(?m)^\s*$([regex]::Escape($key))\s*=.*$"
  if ([regex]::IsMatch($text, $pattern)) {
    return [regex]::Replace($text, $pattern, "$key=$value")
  }

  $suffix = ""
  if ($text.Length -gt 0 -and -not $text.EndsWith("`n")) { $suffix = "`r`n" }
  return ($text + $suffix + "$key=$value`r`n")
}

Write-Info "Starting worktree setup."

$root = $env:ROOT_WORKTREE_PATH
if (-not $root) {
  throw "ROOT_WORKTREE_PATH is not set. Cursor should set this automatically for worktree setup."
}

# 1) Create isolated virtual environment in the worktree
if (-not (Test-Path ".\.venv")) {
  Write-Info "Creating .venv"
  python -m venv .venv
}

$py = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  throw "Expected venv python at $py"
}

Write-Info "Upgrading pip"
& $py -m pip install --upgrade pip | Out-Host

Write-Info "Installing requirements.txt"
& $py -m pip install -r requirements.txt | Out-Host

# 2) Ensure .env exists in worktree (git-ignored files do not auto-copy)
Ensure-EnvFile -rootPath $root

# 3) Ensure DATABASE_URL is set and safe for parallel agents
$envText = ""
if (Test-Path ".env") {
  $envText = Get-Content ".env" -Raw
}

$dbUrl = Get-EnvValue -text $envText -key "DATABASE_URL"
$defaultSqliteUrl = "sqlite:///./experiments_worktree.db"

if (-not $dbUrl) {
  Write-Info "DATABASE_URL missing; setting to per-worktree sqlite DB."
  $envText = Set-EnvValue -text $envText -key "DATABASE_URL" -value $defaultSqliteUrl
} else {
  # If sqlite is used, force a per-worktree DB file to avoid lock/contention across agents.
  if ($dbUrl -match '^\s*sqlite') {
    Write-Info "Detected sqlite DATABASE_URL; rewriting to per-worktree DB."
    $envText = Set-EnvValue -text $envText -key "DATABASE_URL" -value $defaultSqliteUrl
  }

  # If .env.example placeholder postgres URL is present, rewrite to sqlite so setup succeeds.
  if ($dbUrl -eq "postgresql://user:password@localhost:5432/dbname") {
    Write-Info "Detected placeholder postgres DATABASE_URL; rewriting to per-worktree sqlite DB."
    $envText = Set-EnvValue -text $envText -key "DATABASE_URL" -value $defaultSqliteUrl
  }
}

Set-Content -Path ".env" -Value $envText -NoNewline

# 4) Run migrations into the worktree-local DB
Write-Info "Running alembic upgrade head"
& $py -m alembic upgrade head | Out-Host

Write-Info "Worktree setup complete."

