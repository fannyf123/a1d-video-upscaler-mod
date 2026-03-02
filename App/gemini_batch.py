"""
gemini_batch.py

Batch processor untuk generate banyak video sekaligus
di Gemini Enterprise menggunakan GeminiEnterpriseProcessor.

Setiap prompt dijalankan di worker thread terpisah,
dengan stagger delay antar worker.
"""

import threading
import time
import os
from typing import List, Callable, Optional

from App.gemini_enterprise import GeminiEnterpriseProcessor

GEMINI_MAX_WORKERS = 3   # max paralel generate video


class GeminiBatchProcessor(threading.Thread):
    """
    Jalankan banyak prompt generate video secara paralel.

    Tiap worker:
        1. Buat email mask baru via Firefox Relay
        2. Login ke Gemini Enterprise
        3. Generate video sesuai prompt
        4. Download video ke output_dir
    """

    def __init__(
        self,
        base_dir:          str,
        prompts:           List[str],
        config:            dict,
        log_callback:      Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        finished_callback: Optional[Callable] = None,
    ):
        super().__init__(daemon=True)
        self.base_dir     = base_dir
        self.prompts      = prompts
        self.config       = config
        self.log_cb       = log_callback
        self.progress_cb  = progress_callback
        self.finished_cb  = finished_callback
        self._cancelled   = False
        self._workers: List[GeminiEnterpriseProcessor] = []
        self._lock        = threading.Lock()
        self._results     = {}   # {prompt_index: output_path or None}

    def _log(self, msg: str, level: str = "INFO"):
        if self.log_cb:
            self.log_cb(msg, level)

    def _progress(self, pct: int, msg: str):
        if self.progress_cb:
            self.progress_cb(pct, msg)

    def cancel(self):
        self._cancelled = True
        for w in self._workers:
            w.cancel()

    def run(self):
        relay_api_key = self.config.get("relay_api_key", "")
        output_dir    = self.config.get("output_dir", "")
        stagger       = self.config.get("batch_stagger_delay", 15)
        max_workers   = min(
            self.config.get("max_workers", GEMINI_MAX_WORKERS),
            GEMINI_MAX_WORKERS
        )

        total      = len(self.prompts)
        semaphore  = threading.Semaphore(max_workers)
        done_count = [0]
        threads    = []

        self._log("-" * 52)
        self._log(
            f"GEMINI BATCH START — {total} prompt(s) "
            f"| max {max_workers} worker paralel",
            "SUCCESS"
        )
        self._log("-" * 52)

        def run_single(idx: int, prompt: str):
            with semaphore:
                if self._cancelled:
                    return

                # Masking dibuat oleh prosesor itu sendiri

                # Jalankan generate video
                def worker_log(msg, level="INFO"):
                    self.log_cb(f"[Worker {idx+1}] {msg}", level)

                def worker_progress(pct, msg):
                    pass  # batch tidak update progress per-worker

                def worker_done(ok, msg, path):
                    with self._lock:
                        self._results[idx] = path if ok else None
                        done_count[0] += 1
                    lvl = "SUCCESS" if ok else "ERROR"
                    self.log_cb(f"[Worker {idx+1}] {'✅' if ok else '❌'} {msg}", lvl)

                    # Update progress keseluruhan
                    pct = int((done_count[0] / total) * 100)
                    self._progress(pct, f"{done_count[0]}/{total} video selesai")

                    if done_count[0] == total:
                        self._finalize()

                proc = GeminiEnterpriseProcessor(
                    base_dir          = self.base_dir,
                    prompt            = prompt,
                    output_dir        = output_dir,
                    config            = self.config,
                    log_callback      = worker_log,
                    progress_callback = worker_progress,
                    finished_callback = worker_done,
                )
                with self._lock:
                    self._workers.append(proc)

                proc.start()
                proc.join()

        for i, prompt in enumerate(self.prompts):
            if self._cancelled:
                break
            t = threading.Thread(target=run_single, args=(i, prompt), daemon=True)
            threads.append(t)
            t.start()
            if i < len(self.prompts) - 1:
                self._log(f"⏳ Stagger delay {stagger}s sebelum worker berikutnya...")
                time.sleep(stagger)

        for t in threads:
            t.join()

    def _finalize(self):
        success = [p for p in self._results.values() if p]
        failed  = [i for i, p in self._results.items() if not p]

        self._log("-" * 52)
        self._log(
            f"BATCH SELESAI — ✅ {len(success)} berhasil, ❌ {len(failed)} gagal",
            "SUCCESS" if not failed else "WARNING"
        )
        if success:
            self._log("📁 File tersimpan:")
            for p in success:
                self._log(f"   → {p}")
        self._log("-" * 52)

        if self.finished_cb:
            ok  = len(success) > 0
            msg = f"{len(success)}/{len(self.prompts)} video berhasil di-generate"
            self.finished_cb(ok, msg, ";".join(success))
