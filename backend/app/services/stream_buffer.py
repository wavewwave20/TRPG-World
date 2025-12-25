"""
Stream Buffer Management for Narrative Generation

This module provides classes for buffering LLM streaming tokens during
narrative generation, enabling parallel processing and replay functionality.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("ai_gm.stream_buffer")


class StreamBuffer:
    """
    Buffer for storing LLM streaming tokens for a single session.
    
    This class stores tokens as they arrive from the LLM streaming API,
    allowing them to be replayed to clients later. It enforces size limits
    and tracks completion status.
    
    Attributes:
        session_id: Unique identifier for the game session
        tokens: Ordered list of text tokens from LLM
        is_complete: Whether LLM generation has finished
        error: Error message if generation failed, None otherwise
        created_at: Timestamp when buffer was created
        max_size: Maximum total characters allowed (default 100,000)
        
    Requirements: 5.1, 5.2
    """
    
    def __init__(self, session_id: int, max_size: int = 100_000):
        """
        Initialize a new stream buffer.
        
        Args:
            session_id: Game session identifier
            max_size: Maximum total characters allowed in buffer
        """
        self.session_id = session_id
        self.tokens: list[str] = []
        self.is_complete = False
        self.error: Optional[str] = None
        self.created_at = datetime.utcnow()
        self.max_size = max_size
        self._lock = asyncio.Lock()
        self._total_chars = 0
        
        logger.info(f"StreamBuffer 생성: 세션={session_id}, max_size={max_size}")
    
    async def add_token(self, token: str) -> bool:
        """
        Add a token to the buffer.
        
        This method is thread-safe and enforces the maximum size limit.
        If adding the token would exceed the limit, the token is not added
        and the buffer is marked as complete.
        
        Args:
            token: Text token to add to buffer
            
        Returns:
            True if token was added, False if buffer is full
            
        Requirements: 5.1, 5.2
        """
        async with self._lock:
            # Check if buffer is already complete or has error
            if self.is_complete or self.error:
                logger.warning(f"완료/에러 상태 버퍼에 토큰 추가 시도 (세션={self.session_id})")
                return False
            
            # Check size limit
            token_length = len(token)
            if self._total_chars + token_length > self.max_size:
                logger.warning(
                    f"버퍼 크기 한도 도달: 세션={self.session_id}, "
                    f"{self._total_chars} + {token_length} > {self.max_size}"
                )
                self.is_complete = True
                return False
            
            # Add token
            self.tokens.append(token)
            self._total_chars += token_length
            
            return True
    
    def get_tokens(self, start_index: int = 0) -> list[str]:
        """
        Get tokens starting from the specified index.
        
        This method is used for streaming replay, allowing clients to
        request tokens they haven't seen yet.
        
        Args:
            start_index: Index to start retrieving tokens from (0-based)
            
        Returns:
            List of tokens from start_index to end
            
        Requirements: 7.5, 10.1
        """
        if start_index < 0:
            start_index = 0
        
        return self.tokens[start_index:]
    
    def mark_complete(self):
        """
        Mark the buffer as complete.
        
        This should be called when the LLM has finished generating
        all tokens successfully.
        
        Requirements: 7.2
        """
        self.is_complete = True
        logger.info(f"버퍼 완료: 세션={self.session_id}, 토큰={len(self.tokens)}개, {self._total_chars}자")
    
    def mark_error(self, error: str):
        """
        Mark the buffer with an error.
        
        This should be called when LLM generation fails. The error
        message will be propagated to clients.
        
        Args:
            error: Error message describing what went wrong
            
        Requirements: 7.3, 7.4
        """
        self.error = error
        self.is_complete = True
        logger.error(f"버퍼 에러: 세션={self.session_id}, {error}")
    
    def get_full_text(self) -> str:
        """
        Get the complete narrative text by joining all tokens.
        
        Returns:
            Full narrative text
        """
        return "".join(self.tokens)
    
    def get_stats(self) -> dict:
        """
        Get buffer statistics for monitoring.
        
        Returns:
            Dictionary with buffer stats
        """
        return {
            "session_id": self.session_id,
            "token_count": len(self.tokens),
            "total_chars": self._total_chars,
            "is_complete": self.is_complete,
            "has_error": self.error is not None,
            "age_seconds": (datetime.utcnow() - self.created_at).total_seconds(),
        }


class StreamBufferManager:
    """
    Manages stream buffers for multiple concurrent sessions.
    
    This class provides session isolation, automatic cleanup of old buffers,
    and thread-safe access to buffers.
    
    Attributes:
        buffers: Dictionary mapping session_id to StreamBuffer
        cleanup_interval: Seconds between cleanup runs (default 300 = 5 minutes)
        
    Requirements: 5.3, 5.4, 5.5
    """
    
    def __init__(self, cleanup_interval: int = 300):
        """
        Initialize the buffer manager.
        
        Args:
            cleanup_interval: Seconds between automatic cleanup runs
        """
        self.buffers: dict[int, StreamBuffer] = {}
        self.cleanup_interval = cleanup_interval
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(f"StreamBufferManager 초기화: cleanup_interval={cleanup_interval}초")
    
    async def create_buffer(self, session_id: int, max_size: int = 100_000) -> StreamBuffer:
        """
        Create a new buffer for a session.
        
        If a buffer already exists for this session, it will be replaced.
        
        Args:
            session_id: Game session identifier
            max_size: Maximum buffer size in characters
            
        Returns:
            Newly created StreamBuffer
            
        Requirements: 5.5
        """
        async with self._lock:
            if session_id in self.buffers:
                logger.warning(f"기존 버퍼 교체: 세션={session_id}")
            
            buffer = StreamBuffer(session_id, max_size)
            self.buffers[session_id] = buffer
            
            logger.info(f"버퍼 생성: 세션={session_id}")
            return buffer
    
    def get_buffer(self, session_id: int) -> Optional[StreamBuffer]:
        """
        Get the buffer for a session.
        
        Args:
            session_id: Game session identifier
            
        Returns:
            StreamBuffer if exists, None otherwise
            
        Requirements: 5.5
        """
        return self.buffers.get(session_id)
    
    async def remove_buffer(self, session_id: int) -> bool:
        """
        Remove a buffer for a session.
        
        Args:
            session_id: Game session identifier
            
        Returns:
            True if buffer was removed, False if not found
            
        Requirements: 5.3
        """
        async with self._lock:
            if session_id in self.buffers:
                del self.buffers[session_id]
                logger.info(f"버퍼 제거: 세션={session_id}")
                return True
            return False
    
    async def cleanup_old_buffers(self, max_age_seconds: int = 300):
        """
        Remove buffers older than max_age_seconds.
        
        This is called periodically to prevent memory leaks from
        abandoned sessions.
        
        Args:
            max_age_seconds: Maximum age in seconds (default 300 = 5 minutes)
            
        Requirements: 5.3, 5.4
        """
        async with self._lock:
            now = datetime.utcnow()
            to_remove = []
            
            for session_id, buffer in self.buffers.items():
                age = (now - buffer.created_at).total_seconds()
                
                if buffer.is_complete and age > max_age_seconds:
                    to_remove.append(session_id)
                    logger.info(f"오래된 버퍼 정리: 세션={session_id}, 경과={age:.1f}초")
            
            for session_id in to_remove:
                del self.buffers[session_id]
            
            if to_remove:
                logger.info(f"오래된 버퍼 {len(to_remove)}개 정리 완료")
    
    async def start_cleanup_task(self):
        """
        Start the background cleanup task.
        
        This should be called when the application starts.
        
        Requirements: 5.3
        """
        if self._cleanup_task is not None:
            logger.warning("정리 태스크 이미 실행 중")
            return
        
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("버퍼 정리 태스크 시작")
    
    async def stop_cleanup_task(self):
        """
        Stop the background cleanup task.
        
        This should be called when the application shuts down.
        
        Requirements: 9.4
        """
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("버퍼 정리 태스크 중지")
    
    async def _cleanup_loop(self):
        """
        Background loop that periodically cleans up old buffers.
        """
        try:
            while True:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_old_buffers()
        except asyncio.CancelledError:
            logger.info("정리 루프 취소됨")
            raise
        except Exception as e:
            logger.error(f"정리 루프 에러: {e}", exc_info=True)
    
    def get_stats(self) -> dict:
        """
        Get statistics about all buffers.
        
        Returns:
            Dictionary with manager stats
        """
        return {
            "total_buffers": len(self.buffers),
            "buffers": [buffer.get_stats() for buffer in self.buffers.values()],
        }
    
    async def clear_all(self):
        """
        Remove all buffers.
        
        This is useful for testing or server restart.
        
        Requirements: 5.4
        """
        async with self._lock:
            count = len(self.buffers)
            self.buffers.clear()
            logger.info(f"모든 버퍼 삭제: {count}개")


# Global buffer manager instance
_buffer_manager: Optional[StreamBufferManager] = None


def get_buffer_manager() -> StreamBufferManager:
    """
    Get the global buffer manager instance.
    
    Returns:
        Global StreamBufferManager instance
    """
    global _buffer_manager
    if _buffer_manager is None:
        _buffer_manager = StreamBufferManager()
    return _buffer_manager
