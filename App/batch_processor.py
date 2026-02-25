import os
import time
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker

from App.background_process import A1DProcessor

# ───────────────────────────────────────────────────────────────────────────
MAX_PARALLEL  = 5    # maksimal worker berjalan bersamaan
STAGGER_DELAY = 15   # detik jeda antar worker start (hindari burst ke a1d.ai)
# ───────────────────────────────────────────────────────────────────────────


class BatchProcessor(QThread):
    """
    Jalankan hingga MAX_PARALLEL (5) A1DProcessor secara paralel.

    Setiap worker distart dengan jeda STAGGER_DELAY detik agar
    tidak semua login ke a1d.ai pada waktu yang sama persis.

    Signals
    -------
    log_signal(str, str)
        (message, level) — log dari semua worker, prefixed [W1/5], [W2/5] dll.

    progress_signal(int, str)
        (0-100, label) — rata-rata progress semua worker.

    worker_done(int, bool, str)
        (worker_index, success, output_path_or_error)
        Dipancarkan setiap kali satu worker selesai.

    finished_signal(bool, str, list)
        (all_ok, summary_text, [(ok, path_or_err), ...])
        Dipancarkan setelah SEMUA worker selesai.
    """

    log_signal      = Signal(str, str)
    progress_signal = Signal(int, str)
    worker_done     = Signal(int, bool, str)
    finished_signal = Signal(bool, str, list)

    def __init__(self, base_dir: str, video_paths: list, config: dict):
        super().__init__()
        if not video_paths:
            raise ValueError("video_paths tidak boleh kosong")
        self.base_dir    = base_dir
        self.video_paths = video_paths[:MAX_PARALLEL]   # potong maks 5
        self.config      = config
        self._workers: list[A1DProcessor] = []
        self._cancelled  = False
        self._mutex      = QMutex()
        self._results: dict[int, tuple[bool, str]] = {}     # {idx: (ok, path_or_err)}
        self._pct_map:  dict[int, int]             = {}     # {idx: pct}  progress tiap worker

    # ══ PUBLIC ═════════════════════════════════════════════════════════════════════
    def cancel(self):
        """Cancel semua worker yang sedang berjalan."""
        self._cancelled = True
        for w in self._workers:
            try:
                w.cancel()
            except Exception:
                pass

    # ══ HELPERS ════════════════════════════════════════════════════════════════════
    def _log(self, msg: str, level: str = "INFO"):
        self.log_signal.emit(msg, level)

    def _prog(self, pct: int, msg: str = ""):
        self.progress_signal.emit(pct, msg)

    def _avg_pct(self) -> int:
        """Hitung rata-rata progress semua worker (thread-safe)."""
        with QMutexLocker(self._mutex):
            vals = list(self._pct_map.values())
        return int(sum(vals) / max(len(vals), 1))

    # ══ SLOT: per-worker events ═════════════════════════════════════════════════
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
        self._prog(
            min(99, self._avg_pct()),
            f"Selesai {done}/{n} video"
        )

    # ══ MAIN RUN ══════════════════════════════════════════════════════════════════
    def run(self):
        n = len(self.video_paths)
        self._log(f"🚀 Batch START — {n} video, max {MAX_PARALLEL} paralel", "INFO")
        self._log(f"   Stagger: {STAGGER_DELAY}s antar worker", "INFO")
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

            # Hubungkan sinyal (gunakan default arg capture agar lambda tidak shared)
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

            # Stagger: jeda sebelum start worker berikutnya
            if idx < n - 1 and not self._cancelled:
                self._log(
                    f"   ⏸ Tunggu {STAGGER_DELAY}s sebelum start Worker {idx+2}/{n}...",
                    "INFO"
                )
                # Sleep dalam potongan kecil agar cancel bisa segera dideteksi
                for _ in range(STAGGER_DELAY):
                    if self._cancelled:
                        break
                    time.sleep(1)

        # ─ Tunggu semua worker selesai ──────────────────────────────────────────
        self._log("⏳ Menunggu semua worker selesai...", "INFO")
        for w in self._workers:
            w.wait()  # block hingga QThread selesai

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
            ok, val    = self._results.get(i, (False, "tidak diproses"))
            icon       = "✅" if ok else "❌"
            vname      = os.path.basename(self.video_paths[i])
            self._log(f"  {icon} [W{i+1}] {vname}", "INFO")
            self._log(f"       └ {val}", "SUCCESS" if ok else "ERROR")
        self._log("=" * 56, "INFO")

        self._prog(100, summary)
        results_list = [
            self._results.get(i, (False, "tidak diproses")) for i in range(n)
        ]
        self.finished_signal.emit(all_ok, summary, results_list)
