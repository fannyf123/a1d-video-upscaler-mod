import os
import re
import time
import threading
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker, Qt

from App.background_process import A1DProcessor

# ─ Hard limits ───────────────────────────────────────────────────────────────
MAX_PARALLEL_LIMIT = 5
DEFAULT_WORKERS    = 3
DEFAULT_STAGGER    = 15


class BatchProcessor(QThread):
    """
    Queue-based batch processor.

    Semua video dimasukkan ke antrian.  Sebanyak `max_workers` worker
    berjalan paralel.  Saat satu worker selesai, ia langsung mengambil
    job berikutnya dari antrian — sehingga 4 video dengan 3 worker
    akan: proses 3 dulu, lalu worker yang selesai duluan otomatis
    melanjutkan video ke-4.
    """

    log_signal      = Signal(str, str)
    progress_signal = Signal(int, str)
    worker_done     = Signal(int, bool, str)
    finished_signal = Signal(bool, str, list)

    def __init__(self, base_dir: str, video_paths: list, config: dict):
        super().__init__()
        if not video_paths:
            raise ValueError("video_paths tidak boleh kosong")

        cfg_workers = config.get("max_workers", DEFAULT_WORKERS)
        try:    cfg_workers = int(cfg_workers)
        except: cfg_workers = DEFAULT_WORKERS

        cfg_stagger = config.get("batch_stagger_delay", DEFAULT_STAGGER)
        try:    cfg_stagger = int(cfg_stagger)
        except: cfg_stagger = DEFAULT_STAGGER

        self.max_workers   = max(1, min(cfg_workers, MAX_PARALLEL_LIMIT))
        self.stagger_delay = max(0, cfg_stagger)
        self.base_dir      = base_dir
        self.video_paths   = list(video_paths)  # ALL videos — no longer sliced!
        self.config        = config
        self._total        = len(self.video_paths)

        self._mutex     = QMutex()
        self._cancelled = False
        self._results:   dict[int, tuple[bool, str]] = {}
        self._pct_map:   dict[int, int]              = {}
        self._slots:     dict[int, A1DProcessor]     = {}    # slot_id → active worker

        # Job queue: list of (job_index, video_path) not yet started
        self._job_queue: list[tuple[int, str]] = [
            (i, p) for i, p in enumerate(self.video_paths)
        ]

        self._all_done = threading.Event()

    # ═ PUBLIC ═════════════════════════════════════════════════════
    def cancel(self):
        self._cancelled = True
        self._all_done.set()
        with QMutexLocker(self._mutex):
            workers = list(self._slots.values())
        for w in workers:
            try: w.cancel()
            except: pass

    @staticmethod
    def clamp_workers(value) -> int:
        try:    return max(1, min(int(value), MAX_PARALLEL_LIMIT))
        except: return DEFAULT_WORKERS

    # ═ HELPERS ════════════════════════════════════════════════════
    def _log(self, msg: str, level: str = "INFO"):
        self.log_signal.emit(msg, level)

    def _prog(self, pct: int, msg: str = ""):
        self.progress_signal.emit(pct, msg)

    def _avg_pct(self) -> int:
        """Average progress across ALL jobs (not just active ones)."""
        with QMutexLocker(self._mutex):
            vals = list(self._pct_map.values())
        return int(sum(vals) / max(len(vals), 1))

    def _pop_next_job(self) -> tuple[int, str] | None:
        """Thread-safe: pop the next (job_idx, vpath) or return None."""
        with QMutexLocker(self._mutex):
            if self._job_queue and not self._cancelled:
                return self._job_queue.pop(0)
        return None

    def _connect_and_start(self, slot_id: int, job_idx: int, vpath: str):
        """Wire up signals and start a new worker for job_idx in slot_id."""
        n      = self._total
        worker = A1DProcessor(self.base_dir, vpath, self.config)

        worker.log_signal.connect(
            lambda msg, lvl, ji=job_idx, tot=n:
                self.log_signal.emit(f"[{ji+1}/{tot}] {msg}", lvl),
            Qt.DirectConnection,
        )
        worker.progress_signal.connect(
            lambda pct, msg, ji=job_idx:
                self._on_worker_progress(ji, pct, msg),
            Qt.DirectConnection,
        )
        worker.finished_signal.connect(
            lambda ok, msg, path, si=slot_id, ji=job_idx:
                self._on_worker_finished(si, ji, ok, path if ok else msg),
            Qt.DirectConnection,
        )

        with QMutexLocker(self._mutex):
            self._slots[slot_id] = worker

        worker.start()
        self._log(
            f"▶️  Slot {slot_id+1} → Video [{job_idx+1}/{n}]: "
            f"{os.path.basename(vpath)}",
            "INFO",
        )

    # ═ SLOTS ─────────────────────────────────────────────────────
    def _on_worker_progress(self, job_idx: int, pct: int, msg: str):
        with QMutexLocker(self._mutex):
            self._pct_map[job_idx] = pct
        n = self._total
        self._prog(min(99, self._avg_pct()), f"[{job_idx+1}/{n}] {msg}")

    def _on_worker_finished(self, slot_id: int, job_idx: int,
                            ok: bool, path_or_err: str):
        n = self._total

        with QMutexLocker(self._mutex):
            self._results[job_idx]  = (ok, path_or_err)
            self._pct_map[job_idx]  = 100
            done                    = len(self._results)

        icon  = "✅" if ok else "❌"
        vname = os.path.basename(self.video_paths[job_idx])
        self.log_signal.emit(
            f"{icon} [{job_idx+1}/{n}] {vname} SELESAI — {path_or_err}",
            "SUCCESS" if ok else "ERROR",
        )
        self.worker_done.emit(job_idx, ok, path_or_err)
        self.progress_signal.emit(
            min(99, self._avg_pct()), f"Selesai {done}/{n} video"
        )

        # All jobs done → signal main run() to finish
        if done >= n:
            self._all_done.set()
            return

        # Spawn background thread: (optional stagger) → pop next job → start
        # Running this in a daemon thread avoids blocking the worker’s own
        # finally block (cleanup_mask / quit_browser).
        threading.Thread(
            target  = self._start_next_in_slot,
            args    = (slot_id,),
            daemon  = True,
            name    = f"slot-{slot_id}-next",
        ).start()

    def _start_next_in_slot(self, slot_id: int):
        """Background: apply stagger delay, then pick and start the next job."""
        if self._cancelled:
            return
        if self.stagger_delay > 0:
            for _ in range(self.stagger_delay):
                if self._cancelled:
                    return
                time.sleep(1)
        job = self._pop_next_job()
        if job is None:
            return   # Queue empty — another slot already took the last job
        job_idx, vpath = job
        self._connect_and_start(slot_id, job_idx, vpath)

    # ═ MAIN RUN ══════════════════════════════════════════════════════
    def run(self):
        n       = self._total
        initial = min(self.max_workers, n)   # number of slots to open initially

        self._log("🚀 Batch START", "INFO")
        self._log(f"├ Workers : {self.max_workers} paralel (max {MAX_PARALLEL_LIMIT})", "INFO")
        self._log(f"├ Video   : {n} file", "INFO")
        self._log(f"└ Stagger : {self.stagger_delay}s antar start", "INFO")
        self._log("-" * 56, "INFO")
        self._prog(0, f"Batch: 0/{n} selesai")

        # Initialise progress map for ALL jobs
        for i in range(n):
            self._pct_map[i] = 0

        # ─ Start the first wave (up to max_workers) ──────────────────────
        for slot_id in range(initial):
            if self._cancelled:
                self._log("⚠️ Batch dibatalkan sebelum semua slot start", "WARNING")
                break
            job = self._pop_next_job()
            if job is None:
                break
            job_idx, vpath = job
            self._connect_and_start(slot_id, job_idx, vpath)

            # Stagger between initial worker starts
            if self.stagger_delay > 0 and slot_id < initial - 1 and not self._cancelled:
                self._log(
                    f"  ⏸ Stagger {self.stagger_delay}s sebelum slot {slot_id+2}...",
                    "INFO",
                )
                for _ in range(self.stagger_delay):
                    if self._cancelled:
                        break
                    time.sleep(1)

        # ─ Wait until every job emits finished_signal ─────────────────────
        self._log("⏳ Menunggu semua video selesai...", "INFO")
        max_wait = self.config.get("processing_hang_timeout", 1800) + 300
        if not self._all_done.wait(timeout=max_wait) and not self._cancelled:
            self._log(
                f"⚠️ Timeout {max_wait // 60} menit — ada video yang tidak selesai!",
                "WARNING",
            )

        # ─ Summary + unlock UI ──────────────────────────────────────────
        n_ok   = sum(1 for ok, _ in self._results.values() if ok)
        n_fail = n - n_ok
        all_ok = n_fail == 0
        summary = (
            f"Batch selesai — ✅ {n_ok} berhasil  ❌ {n_fail} gagal  (total {n} video)"
        )

        self._log("=" * 56, "INFO")
        self._log(summary, "SUCCESS" if all_ok else "WARNING")
        for i in range(n):
            ok, val = self._results.get(i, (False, "tidak diproses"))
            icon    = "✅" if ok else "❌"
            vname   = os.path.basename(self.video_paths[i])
            self._log(f"  {icon} [{i+1}/{n}] {vname}", "INFO")
            self._log(f"       └ {val}", "SUCCESS" if ok else "ERROR")
        self._log("=" * 56, "INFO")

        self._prog(100, summary)
        results_list = [
            self._results.get(i, (False, "tidak diproses")) for i in range(n)
        ]
        self.finished_signal.emit(all_ok, summary, results_list)

        # Brief grace period so browser cleanup threads can finish
        with QMutexLocker(self._mutex):
            workers = list(self._slots.values())
        for w in workers:
            if w.isRunning():
                w.wait(3_000)
