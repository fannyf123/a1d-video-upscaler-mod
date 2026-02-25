import os
import time
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker

from App.background_process import A1DProcessor

# ── Batas absolut ──────────────────────────────────────────────────────────────────
MAX_PARALLEL_LIMIT  = 5    # hard cap — tidak bisa melebihi angka ini
DEFAULT_WORKERS     = 3    # default jika tidak di-set di config
DEFAULT_STAGGER     = 15   # detik jeda antar worker (default)
# ──────────────────────────────────────────────────────────────────

# Keys yang dibaca dari config dict
# ------------------------------------------------
# "max_workers"         int  1–5   jumlah worker paralel
# "batch_stagger_delay" int  ≥0    jeda detik antar worker start
# ------------------------------------------------


class BatchProcessor(QThread):
    """
    Jalankan beberapa A1DProcessor secara paralel.

    Jumlah worker dan stagger delay dikontrol dari config:

        config["max_workers"]         = 1–5   (default 3)
        config["batch_stagger_delay"] = detik  (default 15)

    Signals
    -------
    log_signal(str, str)
        Log dari semua worker, prefix [W1/N] dll.

    progress_signal(int, str)
        Rata-rata progress semua worker (0–100).

    worker_done(int, bool, str)
        Dipancarkan setiap kali satu worker selesai.
        (worker_index, success, output_path_or_error)

    finished_signal(bool, str, list)
        Dipancarkan setelah SEMUA worker selesai.
        (all_ok, summary_text, [(ok, path_or_err), ...])
    """

    log_signal      = Signal(str, str)
    progress_signal = Signal(int, str)
    worker_done     = Signal(int, bool, str)
    finished_signal = Signal(bool, str, list)

    def __init__(self, base_dir: str, video_paths: list, config: dict):
        super().__init__()
        if not video_paths:
            raise ValueError("video_paths tidak boleh kosong")

        # ─ Baca setting dari config, clamp ke batas aman ───────────────────
        cfg_workers = config.get("max_workers", DEFAULT_WORKERS)
        try:
            cfg_workers = int(cfg_workers)
        except (TypeError, ValueError):
            cfg_workers = DEFAULT_WORKERS

        cfg_stagger = config.get("batch_stagger_delay", DEFAULT_STAGGER)
        try:
            cfg_stagger = int(cfg_stagger)
        except (TypeError, ValueError):
            cfg_stagger = DEFAULT_STAGGER

        # Clamp
        self.max_workers   = max(1, min(cfg_workers, MAX_PARALLEL_LIMIT))  # 1–5
        self.stagger_delay = max(0, cfg_stagger)                            # ≥0 detik

        self.base_dir    = base_dir
        self.video_paths = video_paths[:self.max_workers]   # potong sesuai max_workers
        self.config      = config

        self._workers:  list[A1DProcessor]          = []
        self._cancelled = False
        self._mutex     = QMutex()
        self._results:  dict[int, tuple[bool, str]] = {}    # {idx: (ok, path_or_err)}
        self._pct_map:  dict[int, int]              = {}    # {idx: pct}

    # ══ PUBLIC ════════════════════════════════════════════════════════════════════
    def cancel(self):
        """Cancel semua worker yang sedang berjalan."""
        self._cancelled = True
        for w in self._workers:
            try:
                w.cancel()
            except Exception:
                pass

    @staticmethod
    def clamp_workers(value) -> int:
        """Helper: clamp nilai worker ke 1–5 (berguna untuk validasi di UI)."""
        try:
            return max(1, min(int(value), MAX_PARALLEL_LIMIT))
        except (TypeError, ValueError):
            return DEFAULT_WORKERS

    # ══ HELPERS ════════════════════════════════════════════════════════════════════
    def _log(self, msg: str, level: str = "INFO"):
        self.log_signal.emit(msg, level)

    def _prog(self, pct: int, msg: str = ""):
        self.progress_signal.emit(pct, msg)

    def _avg_pct(self) -> int:
        with QMutexLocker(self._mutex):
            vals = list(self._pct_map.values())
        return int(sum(vals) / max(len(vals), 1))

    # ══ SLOT ─ per-worker events ════════════════════════════════════════════════
    def _on_worker_log(self, idx: int, n: int, msg: str, level: str):
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
        self._log(
            f"{icon} W{idx+1}/{n} SELESAI — {path_or_err}",
            "SUCCESS" if ok else "ERROR"
        )
        self.worker_done.emit(idx, ok, path_or_err)
        self._prog(min(99, self._avg_pct()), f"Selesai {done}/{n} video")

    # ══ MAIN RUN ══════════════════════════════════════════════════════════════════
    def run(self):
        n = len(self.video_paths)

        self._log(f"🚀 Batch START", "INFO")
        self._log(f"   ├ Workers  : {self.max_workers} (max {MAX_PARALLEL_LIMIT})", "INFO")
        self._log(f"   ├ Video     : {n} file", "INFO")
        self._log(f"   └ Stagger   : {self.stagger_delay}s antar worker", "INFO")
        self._log("-" * 56, "INFO")
        self._prog(0, f"Batch: 0/{n} selesai")

        # Init pct map
        for i in range(n):
            self._pct_map[i] = 0

        # ─ Buat & start worker satu-per-satu dengan stagger ──────────────────────
        for idx, vpath in enumerate(self.video_paths):
            if self._cancelled:
                self._log("⚠️ Batch dibatalkan sebelum semua worker start", "WARNING")
                break

            worker = A1DProcessor(self.base_dir, vpath, self.config)

            worker.log_signal.connect(
                lambda msg, lvl, i=idx, total=n:
                    self._on_worker_log(i, total, msg, lvl)
            )
            worker.progress_signal.connect(
                lambda pct, msg, i=idx:
                    self._on_worker_progress(i, pct, msg)
            )
            worker.finished_signal.connect(
                lambda ok, msg, path, i=idx:
                    self._on_worker_finished(i, ok, path if ok else msg)
            )

            self._workers.append(worker)
            worker.start()
            self._log(
                f"▶️  Worker {idx+1}/{n} dimulai — {os.path.basename(vpath)}",
                "INFO"
            )

            # Stagger (0 = tidak ada jeda)
            if self.stagger_delay > 0 and idx < n - 1 and not self._cancelled:
                self._log(
                    f"   ⏸ Stagger {self.stagger_delay}s sebelum Worker {idx+2}/{n}...",
                    "INFO"
                )
                for _ in range(self.stagger_delay):
                    if self._cancelled:
                        break
                    time.sleep(1)

        # ─ Tunggu semua worker selesai ──────────────────────────────────────────
        self._log("⏳ Menunggu semua worker selesai...", "INFO")
        for w in self._workers:
            w.wait()

        # ─ Summary ────────────────────────────────────────────────────────────────
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
