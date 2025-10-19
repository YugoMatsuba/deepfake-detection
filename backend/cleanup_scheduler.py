"""
Background scheduler for automatic cleanup of old analysis files.

Runs periodic cleanup job to delete video/frame files from completed analyses
while preserving database records for historical reporting.
"""

import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from storage import cleanup_old_analysis_files

logger = logging.getLogger(__name__)

# Configuration from environment
CLEANUP_INTERVAL_MINUTES = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "30"))
FILE_RETENTION_HOURS = int(os.getenv("FILE_RETENTION_HOURS", "1"))


def cleanup_job():
    """Scheduled job to clean up old analysis files."""
    logger.info(f"Starting scheduled cleanup (retention: {FILE_RETENTION_HOURS}h)")
    stats = cleanup_old_analysis_files(retention_hours=FILE_RETENTION_HOURS)
    logger.info(f"Cleanup job completed: {stats}")


def init_scheduler():
    """
    Initialize and start the background scheduler for file cleanup.

    Runs cleanup immediately on startup, then periodically based on schedule.

    Returns:
        BackgroundScheduler instance (already started)
    """
    # Run cleanup immediately on startup
    logger.info("Running initial cleanup on startup")
    cleanup_job()

    scheduler = BackgroundScheduler(daemon=True)

    # Schedule cleanup job to run every CLEANUP_INTERVAL_MINUTES
    scheduler.add_job(
        func=cleanup_job,
        trigger=IntervalTrigger(minutes=CLEANUP_INTERVAL_MINUTES),
        id="cleanup_old_files",
        name="Clean up old analysis files",
        replace_existing=True
    )

    scheduler.start()
    logger.info(
        f"Cleanup scheduler started: running every {CLEANUP_INTERVAL_MINUTES} minutes, "
        f"retaining files for {FILE_RETENTION_HOURS} hours after completion"
    )

    return scheduler
