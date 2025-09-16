"""Job scheduler for running periodic jobs."""

import sqlite3
import time
from typing import Dict, List, Any, Optional


class JobScheduler:
    """Emits run_job envelopes at configured intervals."""

    def __init__(self, db_path: str, job_configs: Optional[Dict[str, int]] = None):
        """
        Initialize the job scheduler.

        Args:
            db_path: Path to the database
            job_configs: Optional dict of job_name -> frequency_ms mappings
        """
        self.db_path = db_path
        # Job configurations (name -> frequency_ms)
        self.job_configs = job_configs or {
            'sync_request': 5000,  # Run every 5 seconds by default
        }

    def tick(self) -> List[Dict[str, Any]]:
        """Check for due jobs and return run_job envelopes."""
        envelopes = []
        time_now_ms = int(time.time() * 1000)

        # Open a fresh connection for this check
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()

        try:
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
        finally:
            db.close()

        return envelopes