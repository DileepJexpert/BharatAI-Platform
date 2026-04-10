"""Tests for core/scheduler/ — BaseScheduledTask ABC and TaskRunner."""

import asyncio
import pytest

from core.scheduler.base import BaseScheduledTask
from core.scheduler.runner import TaskRunner


class MockTask(BaseScheduledTask):
    """Test task implementation."""

    def __init__(self, tid: str = "test_task", interval: float = 60.0):
        self._id = tid
        self._interval = interval
        self.call_count = 0

    @property
    def task_id(self) -> str:
        return self._id

    @property
    def interval_seconds(self) -> float:
        return self._interval

    async def run(self) -> dict:
        self.call_count += 1
        return {"processed": 5, "errors": []}


class FailingTask(BaseScheduledTask):
    """Task that always fails."""

    @property
    def task_id(self) -> str:
        return "failing_task"

    @property
    def interval_seconds(self) -> float:
        return 60.0

    async def run(self) -> dict:
        raise RuntimeError("Task failed")


class TestBaseScheduledTask:
    """Test the BaseScheduledTask ABC."""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseScheduledTask()

    def test_concrete_implementation(self):
        task = MockTask()
        assert task.task_id == "test_task"
        assert task.interval_seconds == 60.0

    def test_repr(self):
        task = MockTask("my_task", 3600)
        assert "my_task" in repr(task)
        assert "3600" in repr(task)

    @pytest.mark.asyncio
    async def test_run_returns_dict(self):
        task = MockTask()
        result = await task.run()
        assert result["processed"] == 5


class TestTaskRunner:
    """Test the TaskRunner."""

    def test_register_task(self):
        runner = TaskRunner()
        task = MockTask()
        runner.register(task)
        assert "test_task" in runner.task_ids

    def test_register_invalid_type(self):
        runner = TaskRunner()
        with pytest.raises(TypeError):
            runner.register("not a task")

    def test_register_multiple_tasks(self):
        runner = TaskRunner()
        runner.register(MockTask("t1"))
        runner.register(MockTask("t2"))
        assert len(runner.task_ids) == 2

    @pytest.mark.asyncio
    async def test_run_once_success(self):
        runner = TaskRunner()
        task = MockTask()
        runner.register(task)

        result = await runner.run_once("test_task")
        assert result["task_id"] == "test_task"
        assert result["processed"] == 5
        assert "elapsed_s" in result
        assert task.call_count == 1

    @pytest.mark.asyncio
    async def test_run_once_unknown_task(self):
        runner = TaskRunner()
        result = await runner.run_once("nonexistent")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_run_once_failing_task(self):
        runner = TaskRunner()
        runner.register(FailingTask())

        result = await runner.run_once("failing_task")
        assert result["task_id"] == "failing_task"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_start_stop(self):
        runner = TaskRunner()
        runner.register(MockTask())

        await runner.start()
        assert runner._running is True
        assert runner._loop_task is not None

        await runner.stop()
        assert runner._running is False
        assert runner._loop_task is None

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        runner = TaskRunner()
        runner.register(MockTask())

        await runner.start()
        task1 = runner._loop_task
        await runner.start()  # Should not create new task
        assert runner._loop_task is task1

        await runner.stop()
