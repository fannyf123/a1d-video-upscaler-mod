# App/ffmpeg_postprocessor.py
"""
FFmpeg Post-Processor untuk A1D Video Upscaler
Preset Adobe Stock 4K (H.264 & H.265), mute audio, dan custom mode.
"""
import os
import subprocess
import shutil
import datetime

# ══════════════════════════════════════════════════════════════════════════════
#  PRESET DEFINITIONS  — setiap preset sesuai spesifikasi platform
# ══════════════════════════════════════════════════════════════════════════════
FFMPEG_PRESETS = {
    # ─── Adobe Stock 4K H.264 ────────────────────────────────────────────────
    # Requirement: H.264 High Profile, 4K UHD, yuv420p, AAC 48 kHz, faststart
    "adobe_stock_4k_h264": {
        "_label":        "Adobe Stock 4K — H.264 (Rekomendasi)",
        "video_codec":   "libx264",
        "profile":       "high",
        "level":         "5.2",
        "crf":           18,
        "encode_preset": "slow",
        "pix_fmt":       "yuv420p",
        "scale":         "3840:2160",
        "audio_codec":   "aac",
        "audio_rate":    "48000",
        "audio_bitrate": "320k",
        "extra_args":    "-movflags +faststart",
    },
    # ─── Adobe Stock 4K H.265 / HEVC ─────────────────────────────────────────
    # Lebih kecil ukuran file, kompatibel Adobe Stock sejak 2020
    "adobe_stock_4k_h265": {
        "_label":        "Adobe Stock 4K — H.265/HEVC",
        "video_codec":   "libx265",
        "profile":       "",
        "level":         "",
        "crf":           18,
        "encode_preset": "slow",
        "pix_fmt":       "yuv420p",
        "scale":         "3840:2160",
        "audio_codec":   "aac",
        "audio_rate":    "48000",
        "audio_bitrate": "320k",
        "extra_args":    "-tag:v hvc1 -movflags +faststart",
    },
    # ─── Adobe Stock 2K H.264 ────────────────────────────────────────────────
    "adobe_stock_2k_h264": {
        "_label":        "Adobe Stock 2K — H.264 (1440p)",
        "video_codec":   "libx264",
        "profile":       "high",
        "level":         "4.2",
        "crf":           18,
        "encode_preset": "slow",
        "pix_fmt":       "yuv420p",
        "scale":         "2560:1440",
        "audio_codec":   "aac",
        "audio_rate":    "48000",
        "audio_bitrate": "320k",
        "extra_args":    "-movflags +faststart",
    },
    # ─── Adobe Stock 1080p H.264 ──────────────────────────────────────────────
    "adobe_stock_1080p_h264": {
        "_label":        "Adobe Stock 1080p — H.264 (Full HD)",
        "video_codec":   "libx264",
        "profile":       "high",
        "level":         "4.1",
        "crf":           18,
        "encode_preset": "slow",
        "pix_fmt":       "yuv420p",
        "scale":         "1920:1080",
        "audio_codec":   "aac",
        "audio_rate":    "48000",
        "audio_bitrate": "320k",
        "extra_args":    "-movflags +faststart",
    },
    # ─── Custom / Manual ──────────────────────────────────────────────────────
    "custom": {
        "_label":        "Custom (setting manual)",
        "video_codec":   "libx264",
        "profile":       "",
        "level":         "",
        "crf":           18,
        "encode_preset": "slow",
        "pix_fmt":       "yuv420p",
        "scale":         "",
        "audio_codec":   "aac",
        "audio_rate":    "48000",
        "audio_bitrate": "320k",
        "extra_args":    "-movflags +faststart",
    },
}

# Human-readable label map untuk UI
PRESET_LABELS = {k: v["_label"] for k, v in FFMPEG_PRESETS.items()}
PRESET_KEYS   = list(FFMPEG_PRESETS.keys())


class FFmpegPostProcessor:
    """
    Post-processor FFmpeg yang dipanggil setelah A1D selesai.
    
    Usage:
        ff = FFmpegPostProcessor(out_path, config, log_fn, prog_fn, cancelled_fn)
        ok, result_path = ff.run()
    """

    def __init__(self, input_path: str, config: dict,
                 log_fn=None, progress_fn=None, cancelled_fn=None):
        self.input_path    = input_path
        self.config        = config
        self.log_fn        = log_fn
        self.progress_fn   = progress_fn
        self.cancelled_fn  = cancelled_fn or (lambda: False)

    # ── Internal helpers ────────────────────────────────────────────────────
    def _log(self, msg, level="INFO"):
        if self.log_fn:
            self.log_fn(msg, level)

    def _prog(self, pct, msg=""):
        if self.progress_fn:
            self.progress_fn(pct, msg)

    def _build_output_path(self, suffix="_ffmpeg") -> str:
        base, _ = os.path.splitext(self.input_path)
        out = f"{base}{suffix}.mp4"
        cnt = 1
        while os.path.exists(out):
            out = f"{base}{suffix}_{cnt}.mp4"
            cnt += 1
        return out

    # ── Public run ──────────────────────────────────────────────────────────
    def run(self) -> tuple:
        """Returns (success: bool, output_path: str)"""
        # Cek ketersediaan FFmpeg
        if not shutil.which("ffmpeg"):
            self._log("⚠️ FFmpeg tidak ditemukan di PATH. Post-processing dilewati.", "WARNING")
            self._log("   Install FFmpeg: https://ffmpeg.org/download.html", "WARNING")
            return False, self.input_path

        if not os.path.exists(self.input_path):
            self._log(f"❌ File input tidak ditemukan: {self.input_path}", "ERROR")
            return False, self.input_path

        ff_cfg      = self.config.get("ffmpeg", {})
        preset_name = ff_cfg.get("preset_name", "adobe_stock_4k_h264")
        preset      = dict(FFMPEG_PRESETS.get(preset_name, FFMPEG_PRESETS["adobe_stock_4k_h264"]))

        # Jika custom, override dengan nilai dari UI
        if preset_name == "custom":
            preset["video_codec"]   = ff_cfg.get("video_codec",   preset["video_codec"])
            preset["crf"]           = ff_cfg.get("crf",           preset["crf"])
            preset["encode_preset"] = ff_cfg.get("encode_preset", preset["encode_preset"])
            preset["pix_fmt"]       = ff_cfg.get("pix_fmt",       preset["pix_fmt"])
            preset["scale"]         = ff_cfg.get("scale",         preset["scale"])
            preset["audio_codec"]   = ff_cfg.get("audio_codec",   preset["audio_codec"])
            preset["audio_rate"]    = ff_cfg.get("audio_rate",    preset["audio_rate"])
            preset["audio_bitrate"] = ff_cfg.get("audio_bitrate", preset["audio_bitrate"])
            preset["extra_args"]    = ff_cfg.get("extra_args",    preset["extra_args"])

        mute         = ff_cfg.get("mute_audio",       False)
        replace_orig = ff_cfg.get("replace_original", False)
        output_path  = self._build_output_path("_ffmpeg")

        label = PRESET_LABELS.get(preset_name, preset_name)
        self._log(f"  Preset  : {label}", "INFO")
        self._log(f"  Codec   : {preset['video_codec']}  CRF:{preset['crf']}  Preset:{preset['encode_preset']}", "INFO")
        self._log(f"  Scale   : {preset.get('scale') or '(original)'}", "INFO")
        self._log(f"  Audio   : {'🔇 MUTED' if mute else preset.get('audio_codec','aac') + ' ' + preset.get('audio_bitrate','320k') + ' @ ' + preset.get('audio_rate','48000') + ' Hz'}", "INFO")

        cmd = self._build_cmd(preset, output_path, mute)
        return self._execute(cmd, output_path, replace_orig)

    # ── Build FFmpeg command ─────────────────────────────────────────────────
    def _build_cmd(self, preset: dict, output_path: str, mute: bool) -> list:
        cmd = ["ffmpeg", "-y", "-i", self.input_path]

        # ─ Video track ──────────────────────────────────────────────────────
        cmd += ["-c:v", preset["video_codec"]]
        if preset.get("profile"):
            cmd += ["-profile:v", preset["profile"]]
        if preset.get("level"):
            cmd += ["-level:v", preset["level"]]
        cmd += ["-crf", str(preset["crf"])]
        cmd += ["-preset", preset["encode_preset"]]
        if preset.get("pix_fmt"):
            cmd += ["-pix_fmt", preset["pix_fmt"]]

        # ─ Scale filter ─────────────────────────────────────────────────────
        # Gunakan scale + pad agar rasio aspek tetap terjaga (no stretch)
        if preset.get("scale"):
            w, h = preset["scale"].split(":")
            vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
            )
            cmd += ["-vf", vf]

        # ─ Audio track ──────────────────────────────────────────────────────
        if mute:
            cmd += ["-an"]
        else:
            cmd += ["-c:a", preset.get("audio_codec", "aac")]
            if preset.get("audio_rate"):
                cmd += ["-ar", preset["audio_rate"]]
            if preset.get("audio_bitrate"):
                cmd += ["-b:a", preset["audio_bitrate"]]

        # ─ Extra args ───────────────────────────────────────────────────────
        extra = preset.get("extra_args", "").strip()
        if extra:
            cmd.extend(extra.split())

        cmd.append(output_path)
        return cmd

    # ── Execute & stream stderr ──────────────────────────────────────────────
    def _execute(self, cmd: list, output_path: str, replace_orig: bool) -> tuple:
        ff_cfg  = self.config.get("ffmpeg", {})
        timeout = ff_cfg.get("timeout", 7200)

        self._log(f"▶ CMD: {' '.join(cmd)}", "INFO")
        self._prog(93, "🎬 FFmpeg encoding...")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            last_progress_log = datetime.datetime.now()
            recent_lines      = []

            while True:
                if self.cancelled_fn():
                    proc.kill()
                    self._log("🛑 FFmpeg dihentikan (user cancel)", "WARNING")
                    return False, self.input_path

                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if line:
                    line = line.rstrip()
                    recent_lines.append(line)
                    # Log progress setiap 15 detik agar tidak flood
                    now = datetime.datetime.now()
                    if (now - last_progress_log).seconds >= 15:
                        last_progress_log = now
                        for l in reversed(recent_lines[-30:]):
                            if "time=" in l:
                                self._log(f"  ⏱ {l.strip()}", "INFO")
                                break
                        recent_lines.clear()

            retcode = proc.wait(timeout=30)

            if retcode == 0 and os.path.exists(output_path):
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                self._log(
                    f"✅ FFmpeg selesai → {os.path.basename(output_path)} ({size_mb:.1f} MB)",
                    "SUCCESS",
                )
                self._prog(98, f"FFmpeg selesai ({size_mb:.1f} MB)")

                if replace_orig:
                    os.replace(output_path, self.input_path)
                    self._log("  ♻️ File A1D diganti dengan hasil FFmpeg (replace mode)", "INFO")
                    return True, self.input_path
                return True, output_path

            else:
                self._log(f"❌ FFmpeg gagal (exit code {retcode})", "ERROR")
                if recent_lines:
                    self._log("  — FFmpeg stderr (tail 30 lines) —", "ERROR")
                    for l in recent_lines[-30:]:
                        if l.strip():
                            self._log(f"  {l}", "ERROR")
                return False, self.input_path

        except subprocess.TimeoutExpired:
            self._log("❌ FFmpeg timeout! Proses dihentikan.", "ERROR")
            return False, self.input_path
        except FileNotFoundError:
            self._log("❌ FFmpeg binary tidak ditemukan. Pastikan FFmpeg sudah di-install dan ada di PATH.", "ERROR")
            return False, self.input_path
        except Exception as e:
            self._log(f"❌ FFmpeg exception: {e}", "ERROR")
            return False, self.input_path
