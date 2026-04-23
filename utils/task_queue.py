# File: utils/task_queue.py — @2026 v1.0
"""
Async task queue for long-running reconciliation jobs.

Supports two backends:
1. Celery + Redis (production) — full async with worker processes
2. ThreadPoolExecutor (development) — simple async without Redis dependency

Usage:
    # Submit a task
    task_id = task_queue.submit_reconciliation(input_dir, output_dir)
    
    # Check status
    status = task_queue.get_task_status(task_id)
    
    # Get result
    result = task_queue.get_task_result(task_id)
"""

import dataclasses
import logging
import os
import uuid
import threading
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, Callable
from pathlib import Path
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, Future


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Result of an async task."""
    task_id: str
    status: TaskStatus
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: int = 0
    status_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": str(self.result) if self.result else None,
            "error": self.error,
            "progress": self.progress,
            "status_message": self.status_message,
        }


class InMemoryTaskQueue:
    """
    Simple in-memory task queue using ThreadPoolExecutor.
    
    Suitable for development and single-server deployments.
    For production with multiple workers, use CeleryTaskQueue.
    """
    
    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, TaskResult] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
    
    def submit_reconciliation(
        self,
        input_dir: Path,
        output_dir: Path,
        **kwargs
    ) -> str:
        """
        Submit a reconciliation job.
        
        Args:
            input_dir: Input data directory
            output_dir: Output directory for reports
            **kwargs: Additional arguments passed to pipeline
        
        Returns:
            task_id: Unique identifier for tracking the task
        """
        task_id = str(uuid.uuid4())
        
        task_result = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
            status_message="Task queued"
        )
        
        with self._lock:
            self._tasks[task_id] = task_result
        
        # Submit to thread pool
        future = self._executor.submit(
            self._run_reconciliation,
            task_id, input_dir, output_dir, **kwargs
        )
        
        with self._lock:
            self._futures[task_id] = future
        
        logging.info(f"Submitted reconciliation task: {task_id}")
        return task_id
    
    def _run_reconciliation(
        self,
        task_id: str,
        input_dir: Path,
        output_dir: Path,
        **kwargs
    ):
        """Execute reconciliation in background thread."""
        with self._lock:
            task = self._tasks[task_id]
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            task.status_message = "Running reconciliation..."
        
        try:
            from core.pipeline import ReconciliationPipeline, PipelineContext
            
            def update_status(msg: str):
                with self._lock:
                    self._tasks[task_id].status_message = msg
            
            def update_progress(pct: int):
                with self._lock:
                    self._tasks[task_id].progress = pct
            
            # Only pass known PipelineContext fields from kwargs
            ctx_fields = {f.name for f in dataclasses.fields(PipelineContext)}
            safe_kwargs = {k: v for k, v in kwargs.items() if k in ctx_fields}
            
            ctx = PipelineContext(
                input_dir=input_dir,
                output_dir=output_dir,
                update_status=update_status,
                update_progress=update_progress,
                **safe_kwargs
            )
            
            pipeline = ReconciliationPipeline()
            result_ctx = pipeline.run(ctx)
            
            with self._lock:
                task = self._tasks[task_id]
                task.status = TaskStatus.SUCCESS
                task.completed_at = datetime.utcnow()
                task.result = str(result_ctx.report_folder)
                task.progress = 100
                task.status_message = "Completed successfully"
            
            logging.info(f"Task {task_id} completed: {result_ctx.report_folder}")
            
        except Exception as e:
            logging.error(f"Task {task_id} failed: {e}", exc_info=True)
            with self._lock:
                task = self._tasks[task_id]
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.utcnow()
                task.error = str(e)
                task.status_message = f"Failed: {e}"
    
    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get current status of a task."""
        with self._lock:
            return self._tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        with self._lock:
            future = self._futures.get(task_id)
            task = self._tasks.get(task_id)
            
            if not future or not task:
                return False
            
            if task.status == TaskStatus.PENDING:
                cancelled = future.cancel()
                if cancelled:
                    task.status = TaskStatus.CANCELLED
                    task.status_message = "Cancelled by user"
                return cancelled
            
            return False
    
    def list_tasks(self, limit: int = 20) -> list:
        """List recent tasks."""
        with self._lock:
            tasks = sorted(
                self._tasks.values(),
                key=lambda t: t.created_at,
                reverse=True
            )
            return [t.to_dict() for t in tasks[:limit]]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove old completed tasks from memory."""
        cutoff = datetime.utcnow().timestamp() - (max_age_hours * 3600)
        with self._lock:
            to_remove = [
                task_id for task_id, task in self._tasks.items()
                if task.status in (TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED)
                and task.created_at.timestamp() < cutoff
            ]
            for task_id in to_remove:
                del self._tasks[task_id]
                self._futures.pop(task_id, None)
        
        return len(to_remove)
    
    def shutdown(self):
        """Shutdown the executor."""
        self._executor.shutdown(wait=False)


# ============ CELERY BACKEND (Optional) ============

try:
    from celery import Celery
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False


def _create_celery_app() -> "Celery":
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    result_backend = os.getenv("CELERY_RESULT_BACKEND", broker_url)

    app = Celery(
        "reconciliation",
        broker=broker_url,
        backend=result_backend
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
    )
    return app


celery_app = _create_celery_app() if CELERY_AVAILABLE else None


if CELERY_AVAILABLE:
    @celery_app.task(bind=True, name="reconciliation.run")
    def run_reconciliation_task(self, input_dir_str: str, output_dir_str: str):
        """Celery task for running reconciliation."""
        from core.pipeline import ReconciliationPipeline, PipelineContext

        def update_progress(pct: int):
            self.update_state(
                state="PROGRESS",
                meta={"progress": pct}
            )

        ctx = PipelineContext(
            input_dir=Path(input_dir_str),
            output_dir=Path(output_dir_str),
            update_progress=update_progress
        )

        pipeline = ReconciliationPipeline()
        result_ctx = pipeline.run(ctx)

        return {"report_folder": str(result_ctx.report_folder)}


class CeleryTaskQueue:
    """
    Celery-based task queue for production deployments.
    
    Requires: pip install celery redis
    Requires: Redis server running
    
    Environment variables:
        CELERY_BROKER_URL: Redis URL (default: redis://localhost:6379/0)
        CELERY_RESULT_BACKEND: Redis URL for results (default: same as broker)
    """
    
    def __init__(self):
        if not CELERY_AVAILABLE:
            raise ImportError("Celery not installed. Run: pip install celery redis")

        self._app = celery_app
        self._reconciliation_task = run_reconciliation_task
    
    def _register_tasks(self):
        """Register Celery tasks."""
        self._reconciliation_task = run_reconciliation_task
    
    def submit_reconciliation(self, input_dir: Path, output_dir: Path, **kwargs) -> str:
        """Submit reconciliation task to Celery."""
        result = self._reconciliation_task.delay(str(input_dir), str(output_dir))
        return result.id
    
    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get task status from Celery."""
        result = self._app.AsyncResult(task_id)
        
        status_map = {
            "PENDING": TaskStatus.PENDING,
            "STARTED": TaskStatus.RUNNING,
            "PROGRESS": TaskStatus.RUNNING,
            "SUCCESS": TaskStatus.SUCCESS,
            "FAILURE": TaskStatus.FAILED,
            "REVOKED": TaskStatus.CANCELLED,
        }
        
        task_result = TaskResult(
            task_id=task_id,
            status=status_map.get(result.state, TaskStatus.PENDING),
        )
        
        if result.state == "PROGRESS":
            task_result.progress = result.info.get("progress", 0)
        elif result.state == "SUCCESS":
            task_result.result = result.result.get("report_folder") if result.result else None
            task_result.progress = 100
        elif result.state == "FAILURE":
            task_result.error = str(result.result)
        
        return task_result


# ============ FACTORY ============

def create_task_queue() -> InMemoryTaskQueue:
    """
    Create appropriate task queue based on environment.
    
    Uses Celery if CELERY_BROKER_URL is set, otherwise InMemoryTaskQueue.
    """
    if os.getenv("CELERY_BROKER_URL"):
        if not CELERY_AVAILABLE:
            raise ImportError("CELERY_BROKER_URL is set but Celery is not installed. Install celery and redis.")
        logging.info("Using Celery task queue")
        return CeleryTaskQueue()
    else:
        logging.info("Using in-memory task queue (ThreadPoolExecutor)")
        return InMemoryTaskQueue()


# Global task queue instance
_task_queue: Optional[InMemoryTaskQueue] = None


def get_task_queue() -> InMemoryTaskQueue:
    """Get global task queue instance (singleton)."""
    global _task_queue
    if _task_queue is None:
        _task_queue = create_task_queue()
    return _task_queue
