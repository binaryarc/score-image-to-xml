from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class ProgressState:
    status: str = "idle"
    step: str = ""
    message: str = ""
    logs: list[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)


_LOCK = Lock()
_STORE: dict[str, ProgressState] = {}
_MAX_LOGS = 200


def init_job(job_id: str) -> None:
    with _LOCK:
        _STORE[job_id] = ProgressState(status="processing", step="init", message="시작")


def update_job(
    job_id: str,
    *,
    status: str | None = None,
    step: str | None = None,
    message: str | None = None,
    log: str | None = None,
) -> None:
    with _LOCK:
        state = _STORE.get(job_id)
        if not state:
            state = ProgressState(status="processing")
            _STORE[job_id] = state

        if status is not None:
            state.status = status
        if step is not None:
            state.step = step
        if message is not None:
            state.message = message
        if log:
            state.logs.append(log)
            if len(state.logs) > _MAX_LOGS:
                state.logs = state.logs[-_MAX_LOGS :]
        state.updated_at = time.time()


def get_job(job_id: str) -> dict[str, Any]:
    with _LOCK:
        state = _STORE.get(job_id)
        if not state:
            return {
                "status": "unknown",
                "step": "",
                "message": "작업 정보를 찾을 수 없습니다.",
                "logs": [],
            }

        return {
            "status": state.status,
            "step": state.step,
            "message": state.message,
            "logs": list(state.logs),
            "updated_at": state.updated_at,
        }
