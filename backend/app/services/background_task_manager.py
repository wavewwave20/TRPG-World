"""
Background Task Management for Narrative Generation

This module manages asyncio background tasks for LLM narrative generation,
providing timeout handling, error isolation, and graceful shutdown.

Requirements: 4.2, 9.1, 9.2, 9.3, 9.4, 9.5
"""

import asyncio
import logging
from typing import Callable, Optional, Any

logger = logging.getLogger("ai_gm.background_task")


class BackgroundTaskManager:
    """
    Manages background tasks for narrative generation.
    
    This class provides lifecycle management for asyncio tasks, including:
    - Task registration and tracking
    - Timeout enforcement (60 seconds default)
    - Error isolation and logging
    - Graceful shutdown
    
    Attributes:
        tasks: Dictionary mapping session_id to running asyncio.Task
        default_timeout: Default timeout in seconds (default 60)
        
    Requirements: 9.1, 9.2, 9.4, 9.5
    """
    
    def __init__(self, default_timeout: int = 60):
        """
        Initialize the background task manager.
        
        Args:
            default_timeout: Default timeout for tasks in seconds
        """
        self.tasks: dict[int, asyncio.Task] = {}
        self.default_timeout = default_timeout
        self._lock = asyncio.Lock()
        
        logger.info(f"BackgroundTaskManager 초기화: timeout={default_timeout}초")
    
    async def start_task(
        self,
        session_id: int,
        coro_func: Callable,
        *args,
        timeout: Optional[int] = None,
        **kwargs
    ) -> asyncio.Task:
        """
        Start a background task for a session.
        
        The task will be wrapped with timeout and error handling. If a task
        already exists for this session, it will be cancelled first.
        
        Args:
            session_id: Game session identifier
            coro_func: Async function to execute
            *args: Positional arguments for coro_func
            timeout: Timeout in seconds (uses default if None)
            **kwargs: Keyword arguments for coro_func
            
        Returns:
            The created asyncio.Task
            
        Requirements: 9.1, 9.2
        """
        async with self._lock:
            if session_id in self.tasks:
                logger.warning(f"기존 태스크 취소: 세션={session_id}")
                await self.cancel_task(session_id)
            
            # Use default timeout if not specified
            if timeout is None:
                timeout = self.default_timeout
            
            # Create wrapped task
            task = asyncio.create_task(
                self._run_with_timeout(
                    session_id=session_id,
                    coro_func=coro_func,
                    timeout=timeout,
                    args=args,
                    kwargs=kwargs
                )
            )
            
            self.tasks[session_id] = task
            
            logger.info(f"백그라운드 태스크 시작: 세션={session_id}, timeout={timeout}초")
            
            return task
    
    async def _run_with_timeout(
        self,
        session_id: int,
        coro_func: Callable,
        timeout: int,
        args: tuple,
        kwargs: dict
    ):
        """
        Run a coroutine with timeout and error handling.
        
        This wrapper:
        1. Enforces timeout
        2. Catches and logs exceptions
        3. Cleans up task registration
        
        Args:
            session_id: Game session identifier
            coro_func: Async function to execute
            timeout: Timeout in seconds
            args: Positional arguments
            kwargs: Keyword arguments
            
        Requirements: 4.2, 9.3, 9.5
        """
        try:
            async with asyncio.timeout(timeout):
                result = await coro_func(*args, **kwargs)
                logger.info(f"백그라운드 태스크 완료: 세션={session_id}")
                return result
                
        except asyncio.TimeoutError:
            logger.error(f"백그라운드 태스크 타임아웃: 세션={session_id}, {timeout}초 초과")
            raise
            
        except asyncio.CancelledError:
            logger.info(f"백그라운드 태스크 취소됨: 세션={session_id}")
            raise
            
        except Exception as e:
            logger.error(f"백그라운드 태스크 실패: 세션={session_id}, {e}", exc_info=True)
            raise
            
        finally:
            async with self._lock:
                if session_id in self.tasks:
                    del self.tasks[session_id]
                    logger.debug(f"태스크 정리 완료: 세션={session_id}")
    
    async def cancel_task(self, session_id: int) -> bool:
        """
        Cancel a running task for a session.
        
        Args:
            session_id: Game session identifier
            
        Returns:
            True if task was cancelled, False if not found
            
        Requirements: 9.4
        """
        # Note: Lock is already held by caller (start_task or shutdown)
        if session_id not in self.tasks:
            return False
        
        task = self.tasks[session_id]
        
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"태스크 취소 중 에러: 세션={session_id}, {e}", exc_info=True)
        
        del self.tasks[session_id]
        logger.info(f"태스크 취소됨: 세션={session_id}")
        
        return True
    
    async def shutdown(self):
        """
        Cancel all running tasks.
        
        This should be called when the application shuts down to ensure
        all background tasks are properly terminated.
        
        Requirements: 9.4, 9.5
        """
        async with self._lock:
            logger.info(f"BackgroundTaskManager 종료 중: {len(self.tasks)}개 태스크")
            
            session_ids = list(self.tasks.keys())
            for session_id in session_ids:
                await self.cancel_task(session_id)
            
            logger.info("BackgroundTaskManager 종료 완료")
    
    def get_task(self, session_id: int) -> Optional[asyncio.Task]:
        """
        Get the task for a session.
        
        Args:
            session_id: Game session identifier
            
        Returns:
            asyncio.Task if exists, None otherwise
        """
        return self.tasks.get(session_id)
    
    def is_running(self, session_id: int) -> bool:
        """
        Check if a task is running for a session.
        
        Args:
            session_id: Game session identifier
            
        Returns:
            True if task exists and is not done
        """
        task = self.tasks.get(session_id)
        return task is not None and not task.done()
    
    def get_stats(self) -> dict:
        """
        Get statistics about running tasks.
        
        Returns:
            Dictionary with task stats
        """
        running_count = sum(1 for task in self.tasks.values() if not task.done())
        
        return {
            "total_tasks": len(self.tasks),
            "running_tasks": running_count,
            "completed_tasks": len(self.tasks) - running_count,
            "session_ids": list(self.tasks.keys()),
        }


# Global task manager instance
_task_manager: Optional[BackgroundTaskManager] = None


def get_task_manager() -> BackgroundTaskManager:
    """
    Get the global task manager instance.
    
    Returns:
        Global BackgroundTaskManager instance
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager()
    return _task_manager
