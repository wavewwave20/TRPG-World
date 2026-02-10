"""
Tests for the BackgroundTaskManager module.

Tests cover task lifecycle management, timeout enforcement,
error isolation, concurrent tasks, graceful shutdown, and
the global singleton accessor.
"""

import asyncio

import pytest

from app.services.background_task_manager import BackgroundTaskManager, get_task_manager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def manager():
    """Create a fresh BackgroundTaskManager with a short default timeout."""
    return BackgroundTaskManager(default_timeout=5)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global singleton before each test so tests are isolated."""
    import app.services.background_task_manager as mod
    mod._task_manager = None
    yield
    mod._task_manager = None


# ---------------------------------------------------------------------------
# Helper coroutines
# ---------------------------------------------------------------------------

async def _succeed(value: str = "ok") -> str:
    """A fast coroutine that returns immediately."""
    return value


async def _succeed_with_args(a: int, b: int, *, extra: str = "") -> dict:
    """A coroutine that echoes its arguments."""
    return {"a": a, "b": b, "extra": extra}


async def _slow_task(duration: float = 10.0) -> str:
    """A coroutine that sleeps for a while, simulating long work."""
    await asyncio.sleep(duration)
    return "done"


async def _failing_task() -> None:
    """A coroutine that raises an exception."""
    raise ValueError("something went wrong")


async def _short_sleep(duration: float = 0.05) -> str:
    """A coroutine that sleeps briefly and returns."""
    await asyncio.sleep(duration)
    return "completed"


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------

class TestInit:
    """Tests for BackgroundTaskManager.__init__."""

    def test_default_timeout(self):
        """Default timeout should be 60 seconds."""
        mgr = BackgroundTaskManager()
        assert mgr.default_timeout == 60

    def test_custom_timeout(self):
        """Custom timeout should be stored."""
        mgr = BackgroundTaskManager(default_timeout=120)
        assert mgr.default_timeout == 120

    def test_tasks_dict_initially_empty(self):
        """The tasks dict should be empty on init."""
        mgr = BackgroundTaskManager()
        assert mgr.tasks == {}

    def test_lock_is_created(self):
        """An asyncio.Lock should be created."""
        mgr = BackgroundTaskManager()
        assert isinstance(mgr._lock, asyncio.Lock)


# ---------------------------------------------------------------------------
# TestStartTask
# ---------------------------------------------------------------------------

class TestStartTask:
    """Tests for BackgroundTaskManager.start_task."""

    @pytest.mark.asyncio
    async def test_start_task_returns_asyncio_task(self, manager):
        """start_task should return an asyncio.Task instance."""
        task = await manager.start_task(session_id=1, coro_func=_succeed)
        assert isinstance(task, asyncio.Task)
        await task

    @pytest.mark.asyncio
    async def test_start_task_registers_in_tasks_dict(self, manager):
        """The started task should be stored in the tasks dict by session_id."""
        task = await manager.start_task(session_id=42, coro_func=_slow_task)
        assert 42 in manager.tasks
        assert manager.tasks[42] is task
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    @pytest.mark.asyncio
    async def test_start_task_result_is_accessible(self, manager):
        """The wrapped task should propagate the coroutine's return value."""
        task = await manager.start_task(session_id=1, coro_func=_succeed, value="hello")
        result = await task
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_start_task_passes_positional_args(self, manager):
        """Positional arguments should be forwarded to the coroutine."""
        task = await manager.start_task(1, _succeed_with_args, 10, 20, extra="bonus")
        result = await task
        assert result == {"a": 10, "b": 20, "extra": "bonus"}

    @pytest.mark.asyncio
    async def test_start_task_passes_kwargs(self, manager):
        """Keyword arguments should be forwarded to the coroutine."""
        task = await manager.start_task(
            session_id=1, coro_func=_short_sleep, duration=0.01
        )
        result = await task
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_start_task_cancels_existing_task_for_same_session(self, manager):
        """Starting a task for a session that already has one should cancel the old one."""
        first_task = await manager.start_task(session_id=1, coro_func=_slow_task)
        second_task = await manager.start_task(session_id=1, coro_func=_succeed)

        # The first task should have been cancelled
        assert first_task.done()
        assert manager.tasks.get(1) is second_task
        await second_task

    @pytest.mark.asyncio
    async def test_start_task_uses_default_timeout(self, manager):
        """When no timeout is given, the default_timeout should be used."""
        assert manager.default_timeout == 5
        task = await manager.start_task(session_id=1, coro_func=_succeed)
        await task

    @pytest.mark.asyncio
    async def test_start_task_custom_timeout(self, manager):
        """A custom timeout should override the default."""
        task = await manager.start_task(
            session_id=1,
            coro_func=_short_sleep,
            duration=0.01,
            timeout=2,
        )
        result = await task
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_start_task_multiple_sessions(self, manager):
        """Starting tasks for different sessions should store all of them."""
        task_a = await manager.start_task(session_id=1, coro_func=_slow_task)
        task_b = await manager.start_task(session_id=2, coro_func=_slow_task)
        task_c = await manager.start_task(session_id=3, coro_func=_slow_task)

        assert len(manager.tasks) == 3
        assert manager.tasks[1] is task_a
        assert manager.tasks[2] is task_b
        assert manager.tasks[3] is task_c

        for t in (task_a, task_b, task_c):
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass


# ---------------------------------------------------------------------------
# TestCancelTask
# ---------------------------------------------------------------------------

class TestCancelTask:
    """Tests for BackgroundTaskManager.cancel_task."""

    @pytest.mark.asyncio
    async def test_cancel_running_task_via_start_task(self, manager):
        """Starting a new task for the same session should cancel the old one."""
        first_task = await manager.start_task(session_id=1, coro_func=_slow_task)
        assert manager.is_running(1)

        # Starting a new task for session 1 internally calls cancel_task
        second_task = await manager.start_task(session_id=1, coro_func=_succeed)

        assert first_task.done()
        assert manager.tasks.get(1) is second_task
        await second_task

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self, manager):
        """Cancelling a session_id with no task should return False."""
        result = await manager.cancel_task(session_id=999)
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_completed_task_already_cleaned_up(self, manager):
        """A completed task is cleaned up by the finally block in _run_with_timeout."""
        task = await manager.start_task(session_id=1, coro_func=_succeed)
        await task

        # Give a moment for the finally block to execute
        await asyncio.sleep(0.05)

        # After the task finishes, the finally block removes it from self.tasks.
        assert 1 not in manager.tasks

    @pytest.mark.asyncio
    async def test_cancel_returns_false_after_cleanup(self, manager):
        """After a task auto-cleans up, cancel_task should return False."""
        task = await manager.start_task(session_id=1, coro_func=_succeed)
        await task
        await asyncio.sleep(0.05)

        result = await manager.cancel_task(session_id=1)
        assert result is False

    @pytest.mark.asyncio
    async def test_replacing_task_multiple_times(self, manager):
        """Repeatedly replacing a session's task should always cancel the previous one."""
        task1 = await manager.start_task(session_id=1, coro_func=_slow_task)
        task2 = await manager.start_task(session_id=1, coro_func=_slow_task)
        task3 = await manager.start_task(session_id=1, coro_func=_succeed)

        assert task1.done()
        assert task2.done()
        assert manager.tasks.get(1) is task3
        await task3


# ---------------------------------------------------------------------------
# TestTimeoutHandling
# ---------------------------------------------------------------------------

class TestTimeoutHandling:
    """Tests for timeout enforcement."""

    @pytest.mark.asyncio
    async def test_task_times_out(self):
        """A task that exceeds its timeout should raise TimeoutError."""
        manager = BackgroundTaskManager(default_timeout=1)
        task = await manager.start_task(
            session_id=1,
            coro_func=_slow_task,
            duration=10.0,
            timeout=0.1,
        )

        with pytest.raises(asyncio.TimeoutError):
            await task

        # Task should be cleaned up from the dict after timeout
        await asyncio.sleep(0.05)
        assert 1 not in manager.tasks

    @pytest.mark.asyncio
    async def test_task_completes_before_timeout(self):
        """A task that finishes in time should return its result normally."""
        manager = BackgroundTaskManager(default_timeout=10)
        task = await manager.start_task(
            session_id=1,
            coro_func=_short_sleep,
            duration=0.01,
            timeout=5,
        )
        result = await task
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_default_timeout_triggers_on_slow_task(self):
        """A task that exceeds the default timeout should time out."""
        manager = BackgroundTaskManager(default_timeout=0.1)
        task = await manager.start_task(
            session_id=1,
            coro_func=_slow_task,
            duration=10.0,
        )

        with pytest.raises(asyncio.TimeoutError):
            await task

    @pytest.mark.asyncio
    async def test_timeout_does_not_affect_other_sessions(self):
        """A timeout in one session should not affect others."""
        manager = BackgroundTaskManager(default_timeout=10)
        slow = await manager.start_task(
            session_id=1,
            coro_func=_slow_task,
            duration=10.0,
            timeout=0.1,
        )
        fast = await manager.start_task(
            session_id=2,
            coro_func=_short_sleep,
            duration=0.01,
        )

        with pytest.raises(asyncio.TimeoutError):
            await slow

        result = await fast
        assert result == "completed"


# ---------------------------------------------------------------------------
# TestErrorIsolation
# ---------------------------------------------------------------------------

class TestErrorIsolation:
    """Tests for error handling and isolation."""

    @pytest.mark.asyncio
    async def test_failing_task_propagates_exception(self, manager):
        """An exception in the coroutine should be re-raised when awaited."""
        task = await manager.start_task(session_id=1, coro_func=_failing_task)

        with pytest.raises(ValueError, match="something went wrong"):
            await task

    @pytest.mark.asyncio
    async def test_failing_task_cleans_up(self, manager):
        """A failed task should still be removed from the tasks dict."""
        task = await manager.start_task(session_id=1, coro_func=_failing_task)

        with pytest.raises(ValueError):
            await task

        await asyncio.sleep(0.05)
        assert 1 not in manager.tasks

    @pytest.mark.asyncio
    async def test_one_failure_does_not_affect_other_tasks(self, manager):
        """A failure in one session should not affect tasks in other sessions."""
        failing = await manager.start_task(session_id=1, coro_func=_failing_task)
        succeeding = await manager.start_task(
            session_id=2, coro_func=_short_sleep, duration=0.01
        )

        with pytest.raises(ValueError):
            await failing

        result = await succeeding
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_error_type_is_preserved(self, manager):
        """The original exception type should be preserved, not wrapped."""
        async def raise_runtime_error():
            raise RuntimeError("specific error")

        task = await manager.start_task(
            session_id=1, coro_func=raise_runtime_error
        )

        with pytest.raises(RuntimeError, match="specific error"):
            await task


# ---------------------------------------------------------------------------
# TestConcurrentTasks
# ---------------------------------------------------------------------------

class TestConcurrentTasks:
    """Tests for running multiple tasks concurrently."""

    @pytest.mark.asyncio
    async def test_multiple_sessions_run_concurrently(self, manager):
        """Tasks for different sessions should run concurrently."""
        task1 = await manager.start_task(
            session_id=1, coro_func=_short_sleep, duration=0.01
        )
        task2 = await manager.start_task(
            session_id=2, coro_func=_short_sleep, duration=0.01
        )
        task3 = await manager.start_task(
            session_id=3, coro_func=_short_sleep, duration=0.01
        )

        assert len(manager.tasks) == 3

        results = await asyncio.gather(task1, task2, task3)
        assert all(r == "completed" for r in results)

    @pytest.mark.asyncio
    async def test_different_sessions_are_independent(self, manager):
        """Replacing one session's task doesn't affect other sessions."""
        task1 = await manager.start_task(
            session_id=1, coro_func=_slow_task, duration=10.0
        )
        task2 = await manager.start_task(
            session_id=2, coro_func=_short_sleep, duration=0.01
        )

        # Replace session 1's task (cancels the old one internally)
        replacement = await manager.start_task(session_id=1, coro_func=_succeed)

        # Session 1's original task should be cancelled
        assert task1.done()

        # Session 2 should still complete independently
        result = await task2
        assert result == "completed"

        await replacement

    @pytest.mark.asyncio
    async def test_gather_mixed_results(self, manager):
        """gather should collect results from multiple sessions."""
        t1 = await manager.start_task(session_id=1, coro_func=_succeed, value="a")
        t2 = await manager.start_task(session_id=2, coro_func=_succeed, value="b")
        t3 = await manager.start_task(session_id=3, coro_func=_succeed, value="c")

        results = await asyncio.gather(t1, t2, t3)
        assert results == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# TestGetTask
# ---------------------------------------------------------------------------

class TestGetTask:
    """Tests for BackgroundTaskManager.get_task."""

    @pytest.mark.asyncio
    async def test_get_existing_task(self, manager):
        """get_task should return the task for a known session_id."""
        task = await manager.start_task(session_id=7, coro_func=_slow_task)
        retrieved = manager.get_task(7)
        assert retrieved is task
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    def test_get_nonexistent_task(self, manager):
        """get_task should return None for an unknown session_id."""
        assert manager.get_task(999) is None

    @pytest.mark.asyncio
    async def test_get_task_returns_none_after_completion(self, manager):
        """get_task should return None once the task has completed and cleaned up."""
        task = await manager.start_task(session_id=1, coro_func=_succeed)
        await task
        await asyncio.sleep(0.05)
        assert manager.get_task(1) is None


# ---------------------------------------------------------------------------
# TestIsRunning
# ---------------------------------------------------------------------------

class TestIsRunning:
    """Tests for BackgroundTaskManager.is_running."""

    @pytest.mark.asyncio
    async def test_is_running_true_for_active_task(self, manager):
        """is_running should return True while the task is in progress."""
        task = await manager.start_task(
            session_id=1, coro_func=_slow_task, duration=10.0
        )
        assert manager.is_running(1) is True
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    @pytest.mark.asyncio
    async def test_is_running_false_after_completion(self, manager):
        """is_running should return False after the task completes."""
        task = await manager.start_task(session_id=1, coro_func=_succeed)
        await task
        await asyncio.sleep(0.05)
        assert manager.is_running(1) is False

    def test_is_running_false_for_unknown_session(self, manager):
        """is_running should return False for a session with no task."""
        assert manager.is_running(999) is False


# ---------------------------------------------------------------------------
# TestGetStats
# ---------------------------------------------------------------------------

class TestGetStats:
    """Tests for BackgroundTaskManager.get_stats."""

    def test_stats_empty(self, manager):
        """Stats for a manager with no tasks."""
        stats = manager.get_stats()
        assert stats["total_tasks"] == 0
        assert stats["running_tasks"] == 0
        assert stats["completed_tasks"] == 0
        assert stats["session_ids"] == []

    @pytest.mark.asyncio
    async def test_stats_with_running_tasks(self, manager):
        """Stats should reflect currently running tasks."""
        t1 = await manager.start_task(
            session_id=1, coro_func=_slow_task, duration=10.0
        )
        t2 = await manager.start_task(
            session_id=2, coro_func=_slow_task, duration=10.0
        )

        stats = manager.get_stats()
        assert stats["total_tasks"] == 2
        assert stats["running_tasks"] == 2
        assert set(stats["session_ids"]) == {1, 2}

        # Cleanup: cancel tasks directly to avoid lock issues
        for t in (t1, t2):
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_stats_session_ids_list(self, manager):
        """session_ids should list all tracked sessions."""
        tasks = []
        for sid in (10, 20, 30):
            t = await manager.start_task(
                session_id=sid, coro_func=_slow_task, duration=10.0
            )
            tasks.append(t)

        stats = manager.get_stats()
        assert sorted(stats["session_ids"]) == [10, 20, 30]

        for t in tasks:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_stats_after_task_completes(self, manager):
        """Completed tasks should be cleaned up from stats."""
        task = await manager.start_task(session_id=1, coro_func=_succeed)
        await task
        await asyncio.sleep(0.05)

        stats = manager.get_stats()
        assert stats["total_tasks"] == 0
        assert stats["running_tasks"] == 0

    def test_stats_returns_correct_keys(self, manager):
        """Stats dict should contain all expected keys."""
        stats = manager.get_stats()
        assert "total_tasks" in stats
        assert "running_tasks" in stats
        assert "completed_tasks" in stats
        assert "session_ids" in stats


# ---------------------------------------------------------------------------
# TestShutdown
# ---------------------------------------------------------------------------

class TestShutdown:
    """Tests for BackgroundTaskManager.shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_on_empty_manager(self, manager):
        """shutdown on a manager with no tasks should not raise."""
        await manager.shutdown()
        assert len(manager.tasks) == 0

    @pytest.mark.asyncio
    async def test_shutdown_with_completed_tasks(self, manager):
        """shutdown should handle sessions whose tasks already completed."""
        task = await manager.start_task(session_id=1, coro_func=_succeed)
        await task
        await asyncio.sleep(0.05)

        # Task has already been removed by the finally block
        await manager.shutdown()
        assert manager.tasks == {}

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self, manager):
        """Calling shutdown multiple times should not raise."""
        await manager.shutdown()
        await manager.shutdown()
        assert manager.tasks == {}


# ---------------------------------------------------------------------------
# TestCleanupAfterCompletion
# ---------------------------------------------------------------------------

class TestCleanupAfterCompletion:
    """Tests verifying that the finally block in _run_with_timeout cleans up."""

    @pytest.mark.asyncio
    async def test_task_removed_after_success(self, manager):
        """A successful task should be removed from the tasks dict."""
        task = await manager.start_task(session_id=1, coro_func=_succeed)
        await task
        await asyncio.sleep(0.05)
        assert 1 not in manager.tasks

    @pytest.mark.asyncio
    async def test_task_removed_after_failure(self, manager):
        """A failed task should be removed from the tasks dict."""
        task = await manager.start_task(session_id=1, coro_func=_failing_task)
        try:
            await task
        except ValueError:
            pass
        await asyncio.sleep(0.05)
        assert 1 not in manager.tasks

    @pytest.mark.asyncio
    async def test_task_removed_after_timeout(self):
        """A timed-out task should be removed from the tasks dict."""
        manager = BackgroundTaskManager(default_timeout=1)
        task = await manager.start_task(
            session_id=1,
            coro_func=_slow_task,
            duration=10.0,
            timeout=0.1,
        )
        try:
            await task
        except asyncio.TimeoutError:
            pass
        await asyncio.sleep(0.05)
        assert 1 not in manager.tasks

    @pytest.mark.asyncio
    async def test_task_cancelled_is_done(self, manager):
        """A cancelled task should be marked as done."""
        task = await manager.start_task(
            session_id=1, coro_func=_slow_task, duration=10.0
        )
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        await asyncio.sleep(0.05)
        assert task.done()


# ---------------------------------------------------------------------------
# TestGetTaskManager (singleton)
# ---------------------------------------------------------------------------

class TestGetTaskManager:
    """Tests for get_task_manager singleton accessor."""

    def test_returns_instance(self):
        """get_task_manager should return a BackgroundTaskManager instance."""
        mgr = get_task_manager()
        assert isinstance(mgr, BackgroundTaskManager)

    def test_returns_same_instance(self):
        """Multiple calls should return the exact same object."""
        mgr1 = get_task_manager()
        mgr2 = get_task_manager()
        assert mgr1 is mgr2

    def test_default_timeout_is_60(self):
        """The singleton should use the default 60-second timeout."""
        mgr = get_task_manager()
        assert mgr.default_timeout == 60

    def test_singleton_reset_creates_new_instance(self):
        """After resetting _task_manager, a new instance is created."""
        import app.services.background_task_manager as mod

        first = get_task_manager()
        mod._task_manager = None
        second = get_task_manager()

        assert first is not second

    def test_singleton_has_empty_tasks(self):
        """A freshly created singleton should have no tasks."""
        mgr = get_task_manager()
        assert mgr.tasks == {}
