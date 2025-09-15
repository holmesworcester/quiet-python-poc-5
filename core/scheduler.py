"""Job scheduler for running periodic jobs."""

import sqlite3
import time
from typing import Dict, List, Any


class JobScheduler:
    """Manages scheduled job execution."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        # Job configurations (name -> frequency_ms)
        self.job_configs = {
            'sync_request': 5000,  # Run every 5 seconds
        }

    def check_due_jobs(self, time_now_ms: int) -> List[Dict[str, Any]]:
        """Check which jobs are due and return run_job envelopes."""
        envelopes = []
        cursor = self.db.cursor()

        for job_name, frequency_ms in self.job_configs.items():
            # Check when job last ran
            cursor.execute("""
                SELECT last_run_ms FROM job_runs WHERE job_name = ?
            """, (job_name,))
            row = cursor.fetchone()

            if row:
                last_run_ms = row[0]
                if time_now_ms - last_run_ms < frequency_ms:
                    continue  # Not due yet
            # else: Never run, so it's due

            # Create run_job envelope
            envelope = {
                'event_type': 'run_job',
                'job_name': job_name,
                'timestamp_ms': time_now_ms
            }
            envelopes.append(envelope)

            print(f"[JobScheduler] Job {job_name} is due")

        return envelopes

    def tick(self) -> List[Dict[str, Any]]:
        """Called periodically to check for due jobs."""
        time_now_ms = int(time.time() * 1000)
        return self.check_due_jobs(time_now_ms)