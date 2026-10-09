import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from core.db import get_db_connection


TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}


def create_job(job_type: str, payload: dict, *, progress_total: int = 0) -> str:
    job_id = uuid.uuid4().hex
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO jobs (
                   id, job_type, payload_json, status,
                   progress_current, progress_total
               ) VALUES (?, ?, ?, 'PENDING', 0, ?)""",
            (
                job_id,
                str(job_type),
                json.dumps(payload or {}, ensure_ascii=False),
                max(0, int(progress_total or 0)),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return job_id


def _decode_row(row):
    if row is None:
        return None
    item = dict(row)
    for source_key, target_key in (
        ("payload_json", "payload"),
        ("result_json", "result"),
    ):
        raw = item.pop(source_key, None)
        if raw:
            try:
                item[target_key] = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                item[target_key] = None
        else:
            item[target_key] = None
    item["stop_requested"] = bool(item.get("stop_requested"))
    return item


def get_job(job_id: str):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM jobs WHERE id=?",
            (str(job_id),),
        ).fetchone()
        return _decode_row(row)
    finally:
        conn.close()


def list_jobs(*, limit: int = 20, active_only: bool = False):
    conn = get_db_connection()
    try:
        if active_only:
            rows = conn.execute(
                """SELECT * FROM jobs
                   WHERE status IN ('PENDING', 'RUNNING')
                   ORDER BY created_at ASC
                   LIMIT ?""",
                (max(1, min(100, int(limit))),),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM jobs
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (max(1, min(100, int(limit))),),
            ).fetchall()
        return [_decode_row(row) for row in rows]
    finally:
        conn.close()


def request_job_stop(job_id: str) -> bool:
    conn = get_db_connection()
    try:
        cur = conn.execute(
            """UPDATE jobs
               SET stop_requested=1,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=?
                 AND status IN ('PENDING', 'RUNNING')""",
            (str(job_id),),
        )
        conn.commit()
        return int(cur.rowcount or 0) > 0
    finally:
        conn.close()


def update_job_progress(
    job_id: str,
    current: int,
    total: int,
    message: str = "",
):
    conn = get_db_connection()
    try:
        conn.execute(
            """UPDATE jobs
               SET progress_current=?,
                   progress_total=?,
                   progress_message=?,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (
                max(0, int(current or 0)),
                max(0, int(total or 0)),
                str(message or ""),
                str(job_id),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def is_stop_requested(job_id: str) -> bool:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT stop_requested FROM jobs WHERE id=?",
            (str(job_id),),
        ).fetchone()
        return bool(row and row["stop_requested"])
    finally:
        conn.close()


def recover_interrupted_jobs():
    conn = get_db_connection()
    try:
        conn.execute(
            """UPDATE jobs
               SET status='PENDING',
                   progress_message='Uygulama yeniden açıldı; iş devam için kuyruğa alındı.',
                   started_at=NULL,
                   updated_at=CURRENT_TIMESTAMP
               WHERE status='RUNNING'"""
        )
        conn.commit()
    finally:
        conn.close()


class PersistentJobEngine:
    def __init__(self, handlers: dict, *, max_workers: int = 2):
        self.handlers = dict(handlers)
        self.max_workers = max(1, min(2, int(max_workers)))
        self._stop = threading.Event()
        self._dispatcher = None
        self._pool = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="persistent-job",
        )
        self._active = set()
        self._guard = threading.Lock()

    def start(self):
        if self._dispatcher and self._dispatcher.is_alive():
            return
        recover_interrupted_jobs()
        self._stop.clear()
        self._dispatcher = threading.Thread(
            target=self._dispatch_loop,
            name="persistent-job-dispatcher",
            daemon=True,
        )
        self._dispatcher.start()

    def _dispatch_loop(self):
        while not self._stop.is_set():
            with self._guard:
                free_slots = self.max_workers - len(self._active)
            if free_slots > 0:
                for _ in range(free_slots):
                    claimed = self._claim_next()
                    if claimed is None:
                        break
                    job_id = claimed["id"]
                    with self._guard:
                        self._active.add(job_id)
                    future = self._pool.submit(
                        self._execute_claimed,
                        claimed,
                    )
                    future.add_done_callback(
                        lambda _f, jid=job_id: self._mark_inactive(jid)
                    )
            self._stop.wait(0.20)

    def _mark_inactive(self, job_id):
        with self._guard:
            self._active.discard(job_id)

    def _claim_next(self):
        conn = get_db_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """SELECT *
                   FROM jobs
                   WHERE status='PENDING'
                   ORDER BY created_at ASC
                   LIMIT 1"""
            ).fetchone()
            if row is None:
                conn.rollback()
                return None

            if bool(row["stop_requested"]):
                conn.execute(
                    """UPDATE jobs
                       SET status='CANCELLED',
                           finished_at=CURRENT_TIMESTAMP,
                           updated_at=CURRENT_TIMESTAMP,
                           progress_message='İş başlamadan iptal edildi.'
                       WHERE id=?""",
                    (row["id"],),
                )
                conn.commit()
                return None

            cur = conn.execute(
                """UPDATE jobs
                   SET status='RUNNING',
                       started_at=COALESCE(started_at, CURRENT_TIMESTAMP),
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND status='PENDING'""",
                (row["id"],),
            )
            if int(cur.rowcount or 0) != 1:
                conn.rollback()
                return None
            conn.commit()
            return _decode_row(row)
        finally:
            conn.close()

    def _execute_claimed(self, job):
        job_id = job["id"]
        job_type = str(job["job_type"])
        handler = self.handlers.get(job_type)
        if handler is None:
            self._finish(
                job_id,
                "FAILED",
                error=f"Bilinmeyen job type: {job_type}",
            )
            return

        try:
            result = handler(
                job_id,
                job.get("payload") or {},
                lambda current, total, message="": update_job_progress(
                    job_id,
                    current,
                    total,
                    message,
                ),
                lambda: is_stop_requested(job_id),
            )
            if is_stop_requested(job_id) and not (
                isinstance(result, dict)
                and result.get("completed")
            ):
                self._finish(
                    job_id,
                    "CANCELLED",
                    result=result,
                )
            else:
                self._finish(
                    job_id,
                    "SUCCEEDED",
                    result=result,
                )
        except Exception as exc:
            self._finish(
                job_id,
                "FAILED",
                error=str(exc),
            )

    @staticmethod
    def _finish(job_id, status, *, result=None, error=None):
        conn = get_db_connection()
        try:
            conn.execute(
                """UPDATE jobs
                   SET status=?,
                       result_json=?,
                       error_text=?,
                       finished_at=CURRENT_TIMESTAMP,
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    str(status),
                    (
                        json.dumps(result, ensure_ascii=False)
                        if result is not None
                        else None
                    ),
                    str(error) if error else None,
                    str(job_id),
                ),
            )
            conn.commit()
        finally:
            conn.close()
