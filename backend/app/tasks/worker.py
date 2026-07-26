from __future__ import annotations

import queue
import threading

from ..db.repositories import import_repo
from ..services import import_service


class ImportWorker:
    def __init__(self) -> None:
        self._queue: queue.Queue[int] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stopped = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stopped.clear()
        # The database is the durable queue. Rebuild the in-memory queue so a
        # sentinel left by a previous stop cannot terminate the new worker.
        self._queue = queue.Queue()
        for run_id in import_repo.recoverable_run_ids():
            self.enqueue(run_id)
        self._thread = threading.Thread(target=self._run_loop, name="dfi-import-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        self._queue.put(-1)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def enqueue(self, run_id: int) -> None:
        self._queue.put(run_id)

    def _run_loop(self) -> None:
        while not self._stopped.is_set():
            run_id = self._queue.get()
            if run_id == -1:
                return
            try:
                import_service.process_run(run_id)
            except Exception as exc:  # pragma: no cover
                import_repo.mark_run_failed(run_id, str(exc))
