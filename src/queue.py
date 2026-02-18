"""Background build processing queue with sequential processing and retry logic.

Provides async queue-based build processing with:
- Sequential processing (one build at a time)
- Exponential backoff retry logic
- Idempotency tracking (build ID deduplication)
- Branch filtering using fnmatch patterns
- Queue status reporting
"""

import asyncio
import logging
import random
import time
import fnmatch
from typing import Dict, Optional, Set
from datetime import datetime, timedelta

from src.models import TeamCityBuild
from src.config import get_settings

logger = logging.getLogger(__name__)


class BuildQueue:
    """Background build processing queue with sequential processing."""

    def __init__(self):
        """Initialize the build queue."""
        self._queue: asyncio.Queue[TeamCityBuild] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._processed_ids: Dict[int, float] = {}  # build_id -> timestamp
        self._last_processed: Optional[Dict] = None
        self._running = False
        settings = get_settings()
        self._max_retries = settings.processing.max_retries
        self._retry_base_delay = settings.processing.retry_base_delay
        self._branch_filters = settings.processing.branch_filters
        self._dedup_window = settings.webhook.dedup_window

    async def start(self):
        """Start the background worker task."""
        if self._running:
            logger.warning("BuildQueue worker already running")
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("BuildQueue worker started")

    async def stop(self):
        """Stop the background worker task."""
        if not self._running:
            return

        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("BuildQueue worker stopped")

    def should_process(self, branch: str) -> bool:
        """Check if a branch should be processed based on configured filters.

        Args:
            branch: Branch name from TeamCity build

        Returns:
            True if branch matches any filter pattern, False otherwise
        """
        # Empty branch handling
        if not branch:
            # Accept if "default" or "*" is in filters
            return "default" in self._branch_filters or "*" in self._branch_filters

        # Check against each filter pattern
        for pattern in self._branch_filters:
            if fnmatch.fnmatch(branch, pattern):
                return True

        return False

    def is_duplicate(self, build_id: int) -> bool:
        """Check if a build has already been processed.

        Args:
            build_id: TeamCity build ID

        Returns:
            True if build was already processed, False otherwise
        """
        # Prune old entries if dict is getting large
        if len(self._processed_ids) > 10000:
            self._prune_old_entries()

        return build_id in self._processed_ids

    def _prune_old_entries(self):
        """Remove build IDs older than dedup_window from tracking."""
        cutoff_time = time.time() - self._dedup_window
        old_ids = [build_id for build_id, ts in self._processed_ids.items() if ts < cutoff_time]
        for build_id in old_ids:
            del self._processed_ids[build_id]
        if old_ids:
            logger.debug(f"Pruned {len(old_ids)} old build IDs from dedup tracking")

    async def submit(self, build: TeamCityBuild) -> dict:
        """Submit a build for processing.

        Args:
            build: TeamCity build to process

        Returns:
            Dictionary with status ("queued", "duplicate", or "filtered") and details
        """
        # Check branch filter first
        if not self.should_process(build.branchName):
            logger.info(
                f"Build #{build.buildId} on branch '{build.branchName}' filtered out "
                f"(not in: {self._branch_filters})"
            )
            return {
                "status": "filtered",
                "build_id": build.buildId,
                "branch": build.branchName,
                "message": f"Branch not in filter list: {self._branch_filters}",
            }

        # Check idempotency
        if self.is_duplicate(build.buildId):
            logger.info(f"Build #{build.buildId} is a duplicate (already processed)")
            return {
                "status": "duplicate",
                "build_id": build.buildId,
                "message": "Build already processed",
            }

        # Queue the build
        await self._queue.put(build)
        queue_position = self._queue.qsize()
        logger.info(f"Build #{build.buildId} queued for processing (position: {queue_position})")

        return {
            "status": "queued",
            "build_id": build.buildId,
            "queue_position": queue_position,
        }

    def get_status(self) -> dict:
        """Get current queue status.

        Returns:
            Dictionary with queue_size, processed_count, and last_processed build info
        """
        return {
            "queue_size": self._queue.qsize(),
            "processed_count": len(self._processed_ids),
            "last_processed": self._last_processed,
        }

    async def _worker(self):
        """Background worker that processes builds sequentially."""
        logger.info("BuildQueue worker loop started")

        while self._running:
            try:
                # Wait for next build (with timeout to check _running flag)
                try:
                    build = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Process the build with retry logic
                await self._process_with_retry(build)

            except asyncio.CancelledError:
                logger.info("BuildQueue worker cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in BuildQueue worker: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause before continuing

    async def _process_with_retry(self, build: TeamCityBuild):
        """Process a build with retry logic.

        Args:
            build: TeamCity build to process
        """
        for attempt in range(self._max_retries):
            try:
                # Attempt to process the build
                await self._process_build(build)

                # Success - mark as processed and update tracking
                self._processed_ids[build.buildId] = time.time()
                self._last_processed = {
                    "build_id": build.buildId,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "status": build.buildStatus,
                    "branch": build.branchName,
                }
                logger.info(f"Build #{build.buildId} processing complete")
                return

            except Exception as e:
                if attempt < self._max_retries - 1:
                    # Calculate backoff with jitter
                    backoff = self._retry_base_delay * (2 ** attempt)
                    jitter = random.uniform(0, self._retry_base_delay)
                    delay = backoff + jitter

                    logger.warning(
                        f"Retry {attempt + 1}/{self._max_retries} for build #{build.buildId} "
                        f"after error: {e}. Retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    # All retries exhausted
                    logger.error(
                        f"Build #{build.buildId} processing failed after {self._max_retries} "
                        f"retries: {e}. Would alert Slack.",
                        exc_info=True,
                    )
                    # Mark as processed even on failure to prevent infinite retries
                    self._processed_ids[build.buildId] = time.time()

    async def _process_build(self, build: TeamCityBuild):
        """Process a single build.

        This is where actual build analysis will happen in later phases.
        For Phase 1, this is a placeholder that logs and simulates work.

        Args:
            build: TeamCity build to process

        Raises:
            Exception: If processing fails
        """
        logger.info(
            f"Processing build #{build.buildId} ({build.buildStatus}) on {build.branchName}"
        )

        # Simulate processing work
        await asyncio.sleep(0.1)

        # Special handling for green builds
        if build.buildStatus == "SUCCESS":
            logger.info(
                f"Build #{build.buildId} is green — lightweight summary "
                "(full analysis skipped)"
            )

        # Success (placeholder - real processing in later phases)
        return True

    async def check_missed_builds(self):
        """Check for missed builds on startup (placeholder for Phase 2).

        This will be implemented when the TeamCity API client exists in Phase 2.
        """
        settings = get_settings()
        lookback = settings.startup.poll_lookback_builds

        logger.info(f"Checking for missed builds (lookback: {lookback} builds)...")
        logger.info("Startup poll requires TeamCity API client (Phase 2). Skipping.")


# Module-level singleton
build_queue = BuildQueue()
