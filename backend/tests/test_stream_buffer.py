"""
Tests for the stream buffer management module.

Tests cover StreamBuffer token handling, capacity limits, completion/error
states, StreamBufferManager session isolation, cleanup, and the
get_buffer_manager singleton.
"""

from datetime import datetime, timedelta

import pytest

from app.services.stream_buffer import (
    StreamBuffer,
    StreamBufferManager,
    get_buffer_manager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def buffer():
    """Create a StreamBuffer with default settings."""
    return StreamBuffer(session_id=1)


@pytest.fixture
def small_buffer():
    """Create a StreamBuffer with a small max_size for capacity tests."""
    return StreamBuffer(session_id=2, max_size=20)


@pytest.fixture
def manager():
    """Create a fresh StreamBufferManager."""
    return StreamBufferManager(cleanup_interval=60)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global _buffer_manager singleton between tests."""
    import app.services.stream_buffer as mod
    original = mod._buffer_manager
    mod._buffer_manager = None
    yield
    mod._buffer_manager = original


# ---------------------------------------------------------------------------
# StreamBuffer tests
# ---------------------------------------------------------------------------

class TestStreamBufferInit:
    """Tests for StreamBuffer initialisation."""

    def test_default_state(self, buffer):
        """A new buffer should be empty and incomplete."""
        assert buffer.session_id == 1
        assert buffer.tokens == []
        assert buffer.is_complete is False
        assert buffer.error is None
        assert buffer._total_chars == 0
        assert isinstance(buffer.created_at, datetime)

    def test_custom_max_size(self):
        buf = StreamBuffer(session_id=5, max_size=500)
        assert buf.max_size == 500


class TestAddToken:
    """Tests for StreamBuffer.add_token."""

    @pytest.mark.asyncio
    async def test_add_single_token(self, buffer):
        """Adding a token should return True and store it."""
        result = await buffer.add_token("Hello")
        assert result is True
        assert buffer.tokens == ["Hello"]
        assert buffer._total_chars == 5

    @pytest.mark.asyncio
    async def test_add_multiple_tokens(self, buffer):
        """Multiple tokens accumulate in order."""
        await buffer.add_token("Hello")
        await buffer.add_token(" ")
        await buffer.add_token("World")
        assert buffer.tokens == ["Hello", " ", "World"]
        assert buffer._total_chars == 11

    @pytest.mark.asyncio
    async def test_add_empty_token(self, buffer):
        """An empty string token is still accepted."""
        result = await buffer.add_token("")
        assert result is True
        assert buffer.tokens == [""]
        assert buffer._total_chars == 0

    @pytest.mark.asyncio
    async def test_add_token_rejected_when_complete(self, buffer):
        """Tokens cannot be added after buffer is marked complete."""
        buffer.mark_complete()
        result = await buffer.add_token("late")
        assert result is False
        assert buffer.tokens == []

    @pytest.mark.asyncio
    async def test_add_token_rejected_when_error(self, buffer):
        """Tokens cannot be added after buffer has an error."""
        buffer.mark_error("something failed")
        result = await buffer.add_token("late")
        assert result is False
        assert buffer.tokens == []

    @pytest.mark.asyncio
    async def test_add_token_respects_max_size(self, small_buffer):
        """Token that would exceed max_size is rejected and buffer is completed."""
        # Fill close to capacity (20 chars)
        await small_buffer.add_token("a" * 18)  # 18 chars
        assert small_buffer._total_chars == 18

        # This 3-char token would push to 21 > 20
        result = await small_buffer.add_token("bbb")
        assert result is False
        assert small_buffer.is_complete is True
        # Original tokens are preserved
        assert len(small_buffer.tokens) == 1

    @pytest.mark.asyncio
    async def test_add_token_exactly_at_max_size(self, small_buffer):
        """Token that fills buffer exactly to max_size should be accepted."""
        result = await small_buffer.add_token("a" * 20)
        assert result is True
        assert small_buffer._total_chars == 20

        # Next token (even 1 char) should be rejected
        result = await small_buffer.add_token("b")
        assert result is False
        assert small_buffer.is_complete is True

    @pytest.mark.asyncio
    async def test_add_token_after_capacity_reached(self, small_buffer):
        """Once capacity is hit, all subsequent adds fail."""
        await small_buffer.add_token("a" * 20)
        # Trigger capacity stop
        await small_buffer.add_token("x")

        result = await small_buffer.add_token("y")
        assert result is False


class TestGetTokens:
    """Tests for StreamBuffer.get_tokens."""

    @pytest.mark.asyncio
    async def test_get_all_tokens(self, buffer):
        """Default call returns all tokens."""
        await buffer.add_token("a")
        await buffer.add_token("b")
        await buffer.add_token("c")
        assert buffer.get_tokens() == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_get_tokens_with_offset(self, buffer):
        """Specifying start_index skips earlier tokens."""
        await buffer.add_token("a")
        await buffer.add_token("b")
        await buffer.add_token("c")
        assert buffer.get_tokens(start_index=1) == ["b", "c"]
        assert buffer.get_tokens(start_index=2) == ["c"]

    @pytest.mark.asyncio
    async def test_get_tokens_at_end(self, buffer):
        """start_index past the end returns empty list."""
        await buffer.add_token("a")
        assert buffer.get_tokens(start_index=5) == []

    def test_get_tokens_empty_buffer(self, buffer):
        """Empty buffer returns empty list."""
        assert buffer.get_tokens() == []

    @pytest.mark.asyncio
    async def test_get_tokens_negative_index_treated_as_zero(self, buffer):
        """Negative start_index is clamped to 0."""
        await buffer.add_token("a")
        await buffer.add_token("b")
        assert buffer.get_tokens(start_index=-3) == ["a", "b"]


class TestGetFullText:
    """Tests for StreamBuffer.get_full_text."""

    def test_empty_buffer(self, buffer):
        assert buffer.get_full_text() == ""

    @pytest.mark.asyncio
    async def test_concatenation(self, buffer):
        await buffer.add_token("Hello")
        await buffer.add_token(", ")
        await buffer.add_token("World!")
        assert buffer.get_full_text() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_single_token(self, buffer):
        await buffer.add_token("only")
        assert buffer.get_full_text() == "only"


class TestMarkComplete:
    """Tests for StreamBuffer.mark_complete."""

    def test_sets_is_complete(self, buffer):
        assert buffer.is_complete is False
        buffer.mark_complete()
        assert buffer.is_complete is True

    def test_error_remains_none(self, buffer):
        """mark_complete should not set an error."""
        buffer.mark_complete()
        assert buffer.error is None


class TestMarkError:
    """Tests for StreamBuffer.mark_error."""

    def test_sets_error_and_complete(self, buffer):
        buffer.mark_error("timeout")
        assert buffer.error == "timeout"
        assert buffer.is_complete is True

    def test_error_message_preserved(self, buffer):
        msg = "LLM API rate limited"
        buffer.mark_error(msg)
        assert buffer.error == msg


class TestGetStats:
    """Tests for StreamBuffer.get_stats."""

    @pytest.mark.asyncio
    async def test_stats_structure(self, buffer):
        await buffer.add_token("hello")
        stats = buffer.get_stats()
        assert stats["session_id"] == 1
        assert stats["token_count"] == 1
        assert stats["total_chars"] == 5
        assert stats["is_complete"] is False
        assert stats["has_error"] is False
        assert isinstance(stats["age_seconds"], float)

    @pytest.mark.asyncio
    async def test_stats_after_error(self, buffer):
        buffer.mark_error("fail")
        stats = buffer.get_stats()
        assert stats["is_complete"] is True
        assert stats["has_error"] is True


# ---------------------------------------------------------------------------
# StreamBufferManager tests
# ---------------------------------------------------------------------------

class TestCreateBuffer:
    """Tests for StreamBufferManager.create_buffer."""

    @pytest.mark.asyncio
    async def test_creates_buffer(self, manager):
        buf = await manager.create_buffer(session_id=10)
        assert isinstance(buf, StreamBuffer)
        assert buf.session_id == 10
        assert 10 in manager.buffers

    @pytest.mark.asyncio
    async def test_custom_max_size(self, manager):
        buf = await manager.create_buffer(session_id=10, max_size=500)
        assert buf.max_size == 500

    @pytest.mark.asyncio
    async def test_replaces_existing_buffer(self, manager):
        buf1 = await manager.create_buffer(session_id=10)
        await buf1.add_token("old")

        buf2 = await manager.create_buffer(session_id=10)
        assert buf2.tokens == []
        assert manager.buffers[10] is buf2


class TestGetBuffer:
    """Tests for StreamBufferManager.get_buffer."""

    @pytest.mark.asyncio
    async def test_returns_existing(self, manager):
        created = await manager.create_buffer(session_id=10)
        retrieved = manager.get_buffer(10)
        assert retrieved is created

    def test_returns_none_for_missing(self, manager):
        assert manager.get_buffer(999) is None


class TestRemoveBuffer:
    """Tests for StreamBufferManager.remove_buffer."""

    @pytest.mark.asyncio
    async def test_removes_existing(self, manager):
        await manager.create_buffer(session_id=10)
        result = await manager.remove_buffer(10)
        assert result is True
        assert manager.get_buffer(10) is None

    @pytest.mark.asyncio
    async def test_returns_false_for_missing(self, manager):
        result = await manager.remove_buffer(999)
        assert result is False


class TestMultipleSessions:
    """Tests for managing multiple concurrent session buffers."""

    @pytest.mark.asyncio
    async def test_independent_buffers(self, manager):
        """Buffers for different sessions are fully independent."""
        buf_a = await manager.create_buffer(session_id=1)
        buf_b = await manager.create_buffer(session_id=2)
        buf_c = await manager.create_buffer(session_id=3)

        await buf_a.add_token("alpha")
        await buf_b.add_token("beta")
        await buf_c.add_token("gamma")

        assert manager.get_buffer(1).get_full_text() == "alpha"
        assert manager.get_buffer(2).get_full_text() == "beta"
        assert manager.get_buffer(3).get_full_text() == "gamma"

    @pytest.mark.asyncio
    async def test_removing_one_leaves_others(self, manager):
        await manager.create_buffer(session_id=1)
        await manager.create_buffer(session_id=2)

        await manager.remove_buffer(1)

        assert manager.get_buffer(1) is None
        assert manager.get_buffer(2) is not None


class TestCleanupOldBuffers:
    """Tests for StreamBufferManager.cleanup_old_buffers."""

    @pytest.mark.asyncio
    async def test_removes_old_complete_buffers(self, manager):
        """Complete buffers older than max_age_seconds are removed."""
        buf = await manager.create_buffer(session_id=1)
        buf.mark_complete()
        # Artificially age the buffer
        buf.created_at = datetime.utcnow() - timedelta(seconds=600)

        await manager.cleanup_old_buffers(max_age_seconds=300)
        assert manager.get_buffer(1) is None

    @pytest.mark.asyncio
    async def test_keeps_recent_complete_buffers(self, manager):
        """Complete buffers younger than max_age_seconds are kept."""
        buf = await manager.create_buffer(session_id=1)
        buf.mark_complete()
        # Buffer is brand new, well within age limit

        await manager.cleanup_old_buffers(max_age_seconds=300)
        assert manager.get_buffer(1) is not None

    @pytest.mark.asyncio
    async def test_keeps_incomplete_old_buffers(self, manager):
        """Incomplete buffers are never cleaned up, even if old."""
        buf = await manager.create_buffer(session_id=1)
        buf.created_at = datetime.utcnow() - timedelta(seconds=600)
        # Buffer is NOT marked complete

        await manager.cleanup_old_buffers(max_age_seconds=300)
        assert manager.get_buffer(1) is not None

    @pytest.mark.asyncio
    async def test_selective_cleanup(self, manager):
        """Only old, complete buffers are removed; others are kept."""
        # Old + complete -> should be removed
        buf1 = await manager.create_buffer(session_id=1)
        buf1.mark_complete()
        buf1.created_at = datetime.utcnow() - timedelta(seconds=600)

        # Old + incomplete -> should be kept
        buf2 = await manager.create_buffer(session_id=2)
        buf2.created_at = datetime.utcnow() - timedelta(seconds=600)

        # Recent + complete -> should be kept
        buf3 = await manager.create_buffer(session_id=3)
        buf3.mark_complete()

        await manager.cleanup_old_buffers(max_age_seconds=300)

        assert manager.get_buffer(1) is None
        assert manager.get_buffer(2) is not None
        assert manager.get_buffer(3) is not None


class TestClearAll:
    """Tests for StreamBufferManager.clear_all."""

    @pytest.mark.asyncio
    async def test_removes_all_buffers(self, manager):
        await manager.create_buffer(session_id=1)
        await manager.create_buffer(session_id=2)
        await manager.create_buffer(session_id=3)

        await manager.clear_all()
        assert len(manager.buffers) == 0

    @pytest.mark.asyncio
    async def test_clear_empty_manager(self, manager):
        """Clearing when already empty should not raise."""
        await manager.clear_all()
        assert len(manager.buffers) == 0


class TestManagerGetStats:
    """Tests for StreamBufferManager.get_stats."""

    @pytest.mark.asyncio
    async def test_stats_structure(self, manager):
        await manager.create_buffer(session_id=1)
        await manager.create_buffer(session_id=2)

        stats = manager.get_stats()
        assert stats["total_buffers"] == 2
        assert len(stats["buffers"]) == 2

    def test_empty_stats(self, manager):
        stats = manager.get_stats()
        assert stats["total_buffers"] == 0
        assert stats["buffers"] == []


class TestCleanupTask:
    """Tests for start/stop of the background cleanup task."""

    @pytest.mark.asyncio
    async def test_start_and_stop_cleanup_task(self, manager):
        """Starting and stopping the cleanup task should not raise."""
        await manager.start_cleanup_task()
        assert manager._cleanup_task is not None

        await manager.stop_cleanup_task()
        assert manager._cleanup_task is None

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self, manager):
        """Calling start twice does not create a duplicate task."""
        await manager.start_cleanup_task()
        first_task = manager._cleanup_task

        await manager.start_cleanup_task()
        assert manager._cleanup_task is first_task

        await manager.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self, manager):
        """Stopping when no task is running should not raise."""
        await manager.stop_cleanup_task()
        assert manager._cleanup_task is None


# ---------------------------------------------------------------------------
# get_buffer_manager singleton tests
# ---------------------------------------------------------------------------

class TestGetBufferManager:
    """Tests for the get_buffer_manager singleton function."""

    def test_returns_stream_buffer_manager(self):
        mgr = get_buffer_manager()
        assert isinstance(mgr, StreamBufferManager)

    def test_returns_same_instance(self):
        """Multiple calls return the exact same object."""
        mgr1 = get_buffer_manager()
        mgr2 = get_buffer_manager()
        assert mgr1 is mgr2

    def test_creates_new_after_reset(self):
        """After resetting the global, a fresh instance is created."""
        import app.services.stream_buffer as mod

        mgr1 = get_buffer_manager()
        mod._buffer_manager = None
        mgr2 = get_buffer_manager()

        assert mgr1 is not mgr2
