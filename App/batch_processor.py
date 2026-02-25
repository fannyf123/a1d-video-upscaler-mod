import os
import time
import threading
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker, Qt

from App.background_process import A1DProcessor

# ─ Hard limits ──────────────────────────────────────────────────────────────
MAX_PARALLEL_LIMIT = 5
DEFAULT_WORKERS    = 3
DEFAULT_STAGGER    = 15


class BatchProcessor(QThread):
    """
    Jalankan beberapa A1DProcessor secara paralel.

    BUG-FIX v2.4.1:
    ----------------
    Sebelumnya memakai w.wait() di dalam QThread.run() yang memblokir
    event queue BatchProcessor — sehingga queued signals dari worker
    tidak bisa diproses dan log tidak muncul di UI.

    Fix:
      1. Qt.DirectConnection → slot langsung dipanggil di thread worker
         (tidak perlu event-loop BatchProcessor).
      2. threading.Event  → ganti w.wait() agar tidak blokir sama sekali.
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
        self.video_paths   = video_paths[:self.max_workers]
        self.config        = config

        self._workers:  list[A1DProcessor]          = []
        self._cancelled = False
        self._mutex     = QMutex()
        self._results:  dict[int, tuple[bool, str]] = {}
        self._pct_map:  dict[int, int]              = {}

        # ✔ FIX 1: threading.Event menggantikan w.wait() yang memblokir
        self._all_done = threading.Event()

    # ═ PUBLIC ═════════════════════════════════════════════════════
    def cancel(self):
        self._cancelled = True
        self._all_done.set()   # unblock waiting thread
        for w in self._workers:
            try: w.cancel()
            except: pass

    @staticmethod
    def clamp_workers(value) -> int:
        try:    return max(1, min(int(value), MAX_PARALLEL_LIMIT))
        except: return DEFAULT_WORKERS

    # ═ HELPERS ══════════════════════════════════════════════════
    def _log(self, msg: str, level: str = "INFO"):
        self.log_signal.emit(msg, level)

    def _prog(self, pct: int, msg: str = ""):
        self.progress_signal.emit(pct, msg)

    def _avg_pct(self) -> int:
        with QMutexLocker(self._mutex):
            vals = list(self._pct_map.values())
        return int(sum(vals) / max(len(vals), 1))

    # ═ SLOTS ═ dipanggil via Qt.DirectConnection (langsung dari thread worker) ════
    def _on_worker_log(self, idx: int, n: int, msg: str, level: str):
        # Emitting dari worker-thread → ke main-thread via QueuedConnection otomatis
        self.log_signal.emit(f"[W{idx+1}/{n}] {msg}", level)

    def _on_worker_progress(self, idx: int, pct: int, msg: str):
        with QMutexLocker(self._mutex):
            self._pct_map[idx] = pct
        n = len(self.video_paths)
        self._prog(min(99, self._avg_pct()), f"[W{idx+1}/{n}] {msg}")

    def _on_worker_finished(self, idx: int, ok: bool, path_or_err: str):
        with QMutexLocker(self._mutex):
            self._results[idx] = (ok, path_or_err)
            self._pct_map[idx] = 100
            done = len(self._results)

        n    = len(self.video_paths)
        icon = "✅" if ok else "❌"
        self.log_signal.emit(
            f"{icon} W{idx+1}/{n} SELESAI — {path_or_err}",
            "SUCCESS" if ok else "ERROR"
        )
        self.worker_done.emit(idx, ok, path_or_err)
        self.progress_signal.emit(min(99, self._avg_pct()), f"Selesai {done}/{n} video")

        # ✔ FIX 1: Set event ketika SEMUA worker sudah selesai
        if done >= n:
            self._all_done.set()

    # ═ MAIN RUN ══════════════════════════════════════════════════════
    def run(self):
        n = len(self.video_paths)

        self._log("🚀 Batch START", "INFO")
        self._log(f"├ Workers  : {self.max_workers} (max {MAX_PARALLEL_LIMIT})", "INFO")
        self._log(f"├ Video     : {n} file", "INFO")
        self._log(f"└ Stagger   : {self.stagger_delay}s antar worker", "INFO")
        self._log("-" * 56, "INFO")
        self._prog(0, f"Batch: 0/{n} selesai")

        for i in range(n):
            self._pct_map[i] = 0

        # ─ Start workers satu per satu dengan stagger ───────────────────────────
        for idx, vpath in enumerate(self.video_paths):
            if self._cancelled:
                self._log("⚠️ Batch dibatalkan sebelum semua worker start", "WARNING")
                break

            worker = A1DProcessor(self.base_dir, vpath, self.config)

            # ✔ FIX 2: Qt.DirectConnection → slot dipanggil LANGSUNG di worker-thread
            #    Tidak bergantung pada event-loop BatchProcessor yang sedang berjalan
            worker.log_signal.connect(
                lambda msg, lvl, i=idx, total=n: self._on_worker_log(i, total, msg, lvl),
                Qt.DirectConnection
            )
            worker.progress_signal.connect(
                lambda pct, msg, i=idx: self._on_worker_progress(i, pct, msg),
                Qt.DirectConnection
            )
            worker.finished_signal.connect(
                lambda ok, msg, path, i=idx:
                    self._on_worker_finished(i, ok, path if ok else msg),
                Qt.DirectConnection
            )

            self._workers.append(worker)
            worker.start()
            self._log(
                f"▶️  Worker {idx+1}/{n} dimulai — {os.path.basename(vpath)}",
                "INFO"
            )

            if self.stagger_delay > 0 and idx < n - 1 and not self._cancelled:
                self._log(
                    f"  ⏸ Stagger {self.stagger_delay}s sebelum Worker {idx+2}/{n}...",
                    "INFO"
                )
                for _ in range(self.stagger_delay):
                    if self._cancelled:
                        break
                    time.sleep(1)

        # ─ Tunggu sampai semua worker selesai ──────────────────────────────────
        # ✔ FIX 1: threading.Event.wait() — TIDAK memblokir Qt event queue.
        #    Sinyal log & progress dari worker tetap mengalir ke UI selama menunggu.
        self._log("⏳ Menunggu semua worker selesai...", "INFO")
        max_wait_sec = self.config.get("processing_hang_timeout", 1800) + 300
        finished_in_time = self._all_done.wait(timeout=max_wait_sec)

        if not finished_in_time and not self._cancelled:
            self._log(
                f"⚠️ Timeout {max_wait_sec // 60} menit — ada worker yang tidak selesai!",
                "WARNING"
            )

        # Graceful cleanup: tunggu thread benar-benar berhenti (max 10s per worker)
        for w in self._workers:
            if w.isRunning():
                w.wait(msecs=10_000)

        # ─ Summary ──────────────────────────────────────────────────────────────
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
            self._log(f"  {icon} [W{i+1}] {vname}", "INFO")
            self._log(f"       └ {val}", "SUCCESS" if ok else "ERROR")
        self._log("=" * 56, "INFO")

        self._prog(100, summary)
        results_list = [
            self._results.get(i, (False, "tidak diproses")) for i in range(n)
        ]
        self.finished_signal.emit(all_ok, summary, results_list)
