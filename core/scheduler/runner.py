"""TaskRunner — discovers and runs BaseScheduledTask instances on schedule."""

import asyncio
import logging
import time
from typing import Any

from core.scheduler.base import BaseScheduledTask

logger = logging.getLogger(__name__)


class TaskRunner:
    """Runs registered background tasks on their configured intervals."""

    def __init__(self) -> None:
        self._tasks: dict[str, BaseScheduledTask] = {}
        self._loop_task: asyncio.Task | None = None
        self._running = False

    def register(self, task: BaseScheduledTask) -> None:
        """Register a background task instance."""
        if not isinstance(task, BaseScheduledTask):
            raise TypeError(f"{type(task).__name__} does not extend BaseScheduledTask")
        self._tasks[task.task_id] = task
        logger.info(
            "Task registered: %s (every %.0fs)",
            task.task_id,
            task.interval_seconds,
        )

    @property
    def task_ids(self) -> list[str]:
        return list(self._tasks.keys())

    async def run_once(self, task_id: str) -> dict[str, Any]:
        """Run a specific task immediately."""
        task = self._tasks.get(task_id)
        if task is None:
            return {"error": f"Unknown task: {task_id}"}

        start = time.time()
        try:
            result = await task.run()
            elapsed = time.time() - start
            logger.info(
                "Task %s completed in %.1fs: %s",
                task_id,
                elapsed,
                result,
            )
            return {"task_id": task_id, "elapsed_s": round(elapsed, 1), **result}
        except Exception as exc:
            logger.error("Task %s failed: %s", task_id, exc)
            return {"task_id": task_id, "error": str(exc)}

    async def start(self) -> None:
        """Start the task runner loop in the background."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._loop())
        logger.info("TaskRunner started with %d tasks", len(self._tasks))

    async def stop(self) -> None:
        """Stop the task runner loop."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
        logger.info("TaskRunner stopped")

    async def _loop(self) -> None:
        """Main runner loop — checks each task against its interval."""
        last_run: dict[str, float] = {}

        while self._running:
            now = time.time()
            for tid, task in self._tasks.items():
                last = last_run.get(tid, 0)

                if now - last >= task.interval_seconds:
                    try:
                        await task.run()
                        last_run[tid] = time.time()
                    except Exception as exc:
                        logger.error("Task %s failed: %s", tid, exc)

            await asyncio.sleep(30)  # Check every 30 seconds
