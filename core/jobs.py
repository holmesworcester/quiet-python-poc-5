"""Core job scheduling system for periodic tasks."""

import sqlite3
import time
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_job_definitions(path: str = "protocols/quiet/jobs.yaml") -> List[Dict[str, Any]]:
    """
    Load job definitions from YAML file.

    Args:
        path: Path to jobs.yaml file

    Returns:
        List of job definitions
    """
    yaml_path = Path(path)
    if not yaml_path.exists():
        return []

    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)
        return config.get('jobs', [])


def is_job_due(db: sqlite3.Connection, job_name: str, frequency_ms: int) -> bool:
    """
    Check if a job should run based on last run time in database.

    Args:
        db: Database connection
        job_name: Name of the job
        frequency_ms: How often the job should run (milliseconds)

    Returns:
        True if job should run, False otherwise
    """
    cursor = db.cursor()
    result = cursor.execute(
        "SELECT last_run_ms FROM job_runs WHERE job_name = ?",
        (job_name,)
    ).fetchone()

    if not result:
        # Job has never run
        return True

    last_run_ms = result[0]
    current_ms = int(time.time() * 1000)
    time_since_last_run = current_ms - last_run_ms

    return time_since_last_run >= frequency_ms


def mark_job_run(db: sqlite3.Connection, job_name: str, time_ms: Optional[int] = None) -> None:
    """
    Update job's last run time in database.

    Args:
        db: Database connection
        job_name: Name of the job
        time_ms: Time of run in milliseconds (defaults to current time)
    """
    if time_ms is None:
        time_ms = int(time.time() * 1000)

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO job_runs (job_name, last_run_ms, run_count)
        VALUES (?, ?, 1)
        ON CONFLICT(job_name) DO UPDATE SET
            last_run_ms = excluded.last_run_ms,
            run_count = run_count + 1
    """, (job_name, time_ms))
    db.commit()


def get_job_stats(db: sqlite3.Connection, job_name: str) -> Optional[Dict[str, Any]]:
    """
    Get statistics for a job.

    Args:
        db: Database connection
        job_name: Name of the job

    Returns:
        Dictionary with job statistics or None if job not found
    """
    cursor = db.cursor()
    result = cursor.execute(
        "SELECT last_run_ms, run_count FROM job_runs WHERE job_name = ?",
        (job_name,)
    ).fetchone()

    if not result:
        return None

    return {
        'job_name': job_name,
        'last_run_ms': result[0],
        'run_count': result[1],
        'last_run_ago_ms': int(time.time() * 1000) - result[0]
    }


def get_all_job_stats(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Get statistics for all jobs.

    Args:
        db: Database connection

    Returns:
        List of job statistics
    """
    cursor = db.cursor()
    results = cursor.execute(
        "SELECT job_name, last_run_ms, run_count FROM job_runs ORDER BY last_run_ms DESC"
    ).fetchall()

    current_ms = int(time.time() * 1000)
    stats = []
    for job_name, last_run_ms, run_count in results:
        stats.append({
            'job_name': job_name,
            'last_run_ms': last_run_ms,
            'run_count': run_count,
            'last_run_ago_ms': current_ms - last_run_ms
        })

    return stats


def cleanup_old_job_runs(db: sqlite3.Connection, older_than_ms: int) -> int:
    """
    Remove job run records older than specified time.

    Args:
        db: Database connection
        older_than_ms: Remove records with last_run_ms older than this

    Returns:
        Number of records deleted
    """
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM job_runs WHERE last_run_ms < ?",
        (older_than_ms,)
    )
    deleted = cursor.rowcount
    db.commit()
    return deleted


def reset_job(db: sqlite3.Connection, job_name: str) -> bool:
    """
    Reset a job's run history.

    Args:
        db: Database connection
        job_name: Name of the job to reset

    Returns:
        True if job was reset, False if not found
    """
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM job_runs WHERE job_name = ?",
        (job_name,)
    )
    deleted = cursor.rowcount > 0
    db.commit()
    return deleted


def init_job_tables(db: sqlite3.Connection) -> None:
    """
    Initialize job-related tables in the database.

    Args:
        db: Database connection
    """
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_runs (
            job_name TEXT PRIMARY KEY,
            last_run_ms INTEGER NOT NULL,
            run_count INTEGER DEFAULT 0
        )
    """)

    # Index for querying by last_run_ms (for cleanup)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_job_runs_last_run
        ON job_runs(last_run_ms)
    """)

    db.commit()