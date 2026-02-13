"""
Auto-updater for the Experiment Tracking application.

Designed to run on the Lab PC (production environment). Checks GitHub for
new commits on the main branch and, if found, safely updates the application:

    1. Verify no local uncommitted changes exist
    2. Acquire a file lock to prevent concurrent updates
    3. Create a timestamped database backup (via database_backup.py)
    4. Pull the latest changes from origin/main
    5. Install any new/updated dependencies
    6. Run Alembic migrations
    7. Restart the Streamlit application
    8. Roll back on failure (git reset + database restore)

Can be run once (default) or in a polling loop (--poll).
"""

import os
import sys
import time
import shutil
import signal
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Path bootstrap – ensure project root is importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "auto_updater.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LOCK_FILE = PROJECT_ROOT / ".update_lock"
BRANCH = "main"
REMOTE = "origin"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
STREAMLIT_PORT = 8501

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess command and log it."""
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        **kwargs,
    )
    if result.stdout.strip():
        logger.info(result.stdout.strip())
    if result.stderr.strip():
        logger.warning(result.stderr.strip())
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed (exit {result.returncode}): {' '.join(cmd)}\n"
            f"  stdout: {result.stdout.strip()}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    return result


def _resolve_python_executable() -> str:
    """
    Resolve a usable Python executable path for subprocess calls.

    Priority:
      1) project venv Python
      2) current interpreter (sys.executable)
      3) python launcher on PATH
      4) python on PATH
    """
    candidates: list[str] = []
    if VENV_PYTHON.exists():
        candidates.append(str(VENV_PYTHON))
    if sys.executable:
        candidates.append(sys.executable)
    py_launcher = shutil.which("py")
    if py_launcher:
        candidates.append(py_launcher)
    python_on_path = shutil.which("python")
    if python_on_path:
        candidates.append(python_on_path)

    # Deduplicate while preserving order
    seen = set()
    unique_candidates = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            unique_candidates.append(candidate)
            seen.add(candidate)

    for candidate in unique_candidates:
        try:
            probe = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                text=True,
            )
            if probe.returncode == 0:
                return candidate
        except Exception:
            continue

    raise RuntimeError(
        "Could not locate a working Python executable for auto-updater subprocesses."
    )


@contextmanager
def _file_lock():
    """
    Simple file-based lock to prevent concurrent update processes.
    The lock file stores the PID so stale locks can be detected.
    """
    if LOCK_FILE.exists():
        try:
            stale_pid = int(LOCK_FILE.read_text().strip())
            # On Windows, check if the process is still running
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {stale_pid}"],
                capture_output=True, text=True,
            )
            if str(stale_pid) in result.stdout:
                raise RuntimeError(
                    f"Another update process is already running (PID {stale_pid}). "
                    f"If this is stale, delete {LOCK_FILE}"
                )
            else:
                logger.warning(
                    f"Removing stale lock file from PID {stale_pid} (process no longer running)"
                )
                LOCK_FILE.unlink()
        except ValueError:
            logger.warning("Lock file exists but contains invalid PID – removing")
            LOCK_FILE.unlink()

    LOCK_FILE.write_text(str(os.getpid()))
    try:
        yield
    finally:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink(missing_ok=True)


def _has_local_changes() -> bool:
    """Return True if the working tree has uncommitted changes."""
    result = _run(["git", "status", "--porcelain"], check=False)
    return bool(result.stdout.strip())


def _get_current_commit() -> str:
    """Return the current HEAD commit hash."""
    result = _run(["git", "rev-parse", "HEAD"])
    return result.stdout.strip()


def _get_commits_behind() -> int:
    """Return the number of commits the local branch is behind the remote."""
    _run(["git", "fetch", REMOTE, BRANCH])
    result = _run(["git", "rev-list", f"HEAD...{REMOTE}/{BRANCH}", "--count"])
    return int(result.stdout.strip())


# ---------------------------------------------------------------------------
# Core update steps
# ---------------------------------------------------------------------------

def create_pre_update_backup() -> str | None:
    """
    Create a database backup before updating. Uses the existing
    database_backup.py module to ensure consistency.

    Returns:
        Path to the backup file, or None if no SQLite database is in use.

    Raises:
        RuntimeError: If the backup fails.
    """
    try:
        from utils.database_backup import create_archived_backup, cleanup_old_backups

        logger.info("Creating pre-update database backup...")
        backup_path = create_archived_backup()
        if backup_path:
            logger.info(f"Pre-update backup created: {backup_path}")
            cleanup_old_backups(keep_last_n=10)  # keep a few extra around updates
            return backup_path
        else:
            logger.info("No SQLite database to back up (non-SQLite URL) – skipping")
            return None
    except FileNotFoundError:
        logger.info("Database file does not exist yet – skipping backup")
        return None
    except Exception as e:
        raise RuntimeError(f"Database backup failed – aborting update: {e}") from e


def restore_backup(backup_path: str) -> None:
    """Restore a database backup file to the original database location."""
    try:
        from config.config import DATABASE_URL
        from utils.database_backup import _get_source_db_path

        db_path = _get_source_db_path()
        if db_path and backup_path:
            logger.warning(f"Restoring database from backup: {backup_path}")
            shutil.copy2(backup_path, db_path)
            logger.info("Database restored successfully")
    except Exception as e:
        logger.error(f"CRITICAL: Failed to restore database backup: {e}")
        logger.error(f"Manual restore required from: {backup_path}")


def pull_changes() -> str:
    """
    Pull latest changes from origin/main.

    Returns:
        The commit hash *before* the pull (for rollback purposes).
    """
    pre_pull_commit = _get_current_commit()
    logger.info(f"Current commit: {pre_pull_commit[:12]}")
    _run(["git", "pull", REMOTE, BRANCH])
    post_pull_commit = _get_current_commit()
    logger.info(f"Updated to commit: {post_pull_commit[:12]}")
    return pre_pull_commit


def rollback_git(commit_hash: str) -> None:
    """Reset the working tree to a specific commit."""
    logger.warning(f"Rolling back to commit {commit_hash[:12]}...")
    _run(["git", "reset", "--hard", commit_hash])
    logger.info("Git rollback complete")


def install_dependencies() -> None:
    """Install Python dependencies from requirements.txt."""
    python = _resolve_python_executable()
    _run([python, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"])
    logger.info("Dependencies installed")


def run_migrations() -> None:
    """Run any pending Alembic migrations."""
    python = _resolve_python_executable()
    _run([python, "-m", "alembic", "upgrade", "head"])
    logger.info("Alembic migrations applied")


def _find_streamlit_pids() -> list[int]:
    """Find PIDs of running Streamlit processes."""
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True,
    )
    pids = []
    for line in result.stdout.strip().splitlines():
        # Check if this python process is running streamlit
        parts = line.strip('"').split('","')
        if len(parts) >= 2:
            try:
                pid = int(parts[1].strip('"'))
                # Check the command line of this process
                wmic_result = subprocess.run(
                    ["wmic", "process", "where", f"ProcessId={pid}", "get", "CommandLine"],
                    capture_output=True, text=True,
                )
                if "streamlit" in wmic_result.stdout.lower():
                    pids.append(pid)
            except (ValueError, IndexError):
                continue
    return pids


def restart_streamlit() -> None:
    """
    Stop any running Streamlit instances and start a fresh one.
    The new process is started detached so it survives this script exiting.
    """
    # --- Stop existing instances ---
    pids = _find_streamlit_pids()
    if pids:
        logger.info(f"Stopping Streamlit processes: {pids}")
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                # Process may have already exited
                pass
        time.sleep(3)  # give processes time to shut down gracefully

        # Force-kill any that didn't stop
        remaining = _find_streamlit_pids()
        for pid in remaining:
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False)
            except Exception:
                pass
        time.sleep(1)
    else:
        logger.info("No running Streamlit processes found")

    # --- Start a new instance ---
    python = _resolve_python_executable()
    env = os.environ.copy()
    env["STREAMLIT_SERVER_PORT"] = str(STREAMLIT_PORT)
    env["STREAMLIT_SERVER_ADDRESS"] = "0.0.0.0"

    logger.info("Starting Streamlit application...")
    # CREATE_NEW_CONSOLE ensures the Streamlit process survives this script
    subprocess.Popen(
        [python, "-m", "streamlit", "run", "app.py", "--server.fileWatcherType", "none"],
        cwd=str(PROJECT_ROOT),
        env=env,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    logger.info("Streamlit application started in new console window")


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def perform_update() -> bool:
    """
    Execute the full update pipeline with rollback safety.

    Returns:
        True if an update was applied, False if already up-to-date.
    """
    # 1. Check for local changes
    if _has_local_changes():
        logger.error(
            "Local uncommitted changes detected on the production branch. "
            "Resolve these before auto-updating."
        )
        return False

    # 2. Check if updates are available
    commits_behind = _get_commits_behind()
    if commits_behind == 0:
        logger.info("Already up-to-date – nothing to do")
        return False

    logger.info(f"Found {commits_behind} new commit(s) – starting update")

    # 3. Backup database BEFORE touching anything
    backup_path = create_pre_update_backup()

    # 4. Pull changes (save pre-pull commit for rollback)
    pre_pull_commit = None
    try:
        pre_pull_commit = pull_changes()
    except RuntimeError as e:
        logger.error(f"Git pull failed: {e}")
        return False

    # 5. Install dependencies & run migrations
    try:
        install_dependencies()
        run_migrations()
    except RuntimeError as e:
        logger.error(f"Post-pull step failed: {e}")
        logger.error("Rolling back to previous state...")
        if pre_pull_commit:
            rollback_git(pre_pull_commit)
        if backup_path:
            restore_backup(backup_path)
        return False

    # 6. Restart the application
    try:
        restart_streamlit()
    except Exception as e:
        logger.error(f"Failed to restart Streamlit: {e}")
        logger.error("The code is updated but the app may need a manual restart")

    logger.info("Update completed successfully!")
    return True


def poll_for_updates(interval_seconds: int = 300) -> None:
    """
    Continuously poll for updates at the given interval.

    Args:
        interval_seconds: Seconds between polls (default 5 minutes).
    """
    logger.info(
        f"Starting auto-update polling (every {interval_seconds}s). Press Ctrl+C to stop."
    )
    while True:
        try:
            with _file_lock():
                perform_update()
        except RuntimeError as e:
            logger.error(f"Update cycle error: {e}")
        except KeyboardInterrupt:
            logger.info("Polling stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error during update cycle: {e}")

        time.sleep(interval_seconds)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Auto-updater for the Experiment Tracking application"
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Run in continuous polling mode instead of a single check",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Polling interval in seconds (default: 300 = 5 minutes)",
    )
    parser.add_argument(
        "--restart-only",
        action="store_true",
        help="Only restart Streamlit without checking for updates",
    )
    args = parser.parse_args()

    if args.restart_only:
        logger.info("Restart-only mode – restarting Streamlit")
        restart_streamlit()
        return

    if args.poll:
        poll_for_updates(interval_seconds=args.interval)
    else:
        with _file_lock():
            perform_update()


if __name__ == "__main__":
    main()
