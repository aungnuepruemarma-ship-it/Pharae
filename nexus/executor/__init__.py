"""Stage 5 — Runtime Executor.

Spec: docs/volume-2-modules/executor.md. Grows the kernel's minimal
synchronous executor into a full one behind the same capability-type handler
seam: parallel DAG execution, background jobs with pause/cancel (interactive
control), bounded recorded retries, and checkpoint/resume.
"""

from nexus.executor.executor import Executor, ExecutorError, Job, RetryPolicy

__all__ = ["Executor", "ExecutorError", "Job", "RetryPolicy"]
