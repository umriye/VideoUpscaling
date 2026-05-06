"""
upscaler.py - Modul AI Upscaling menggunakan Real-ESRGAN (ncnn-vulkan) + Bicubic (FFmpeg)

Catatan: Menggunakan realesrgan-ncnn-vulkan binary (tidak butuh PyTorch).
         Kompatibel dengan Python 3.14+.
"""

import logging
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from config import (
    FFMPEG_PATH, FFPROBE_PATH, OUTPUT_DIR, TEMP_DIR, TOOLS_DIR,
    TARGET_WIDTH, TARGET_HEIGHT, REALESRGAN_CONFIG,
    REALESRGAN_NCNN_DIRECT_URL,
)

logger = logging.getLogger(__name__)

# ─── Download & Setup Binary ─────────────────────────────────────────────────

BINARY_NAME = "realesrgan-ncnn-vulkan"
BINARY_PATH = Path(REALESRGAN_CONFIG["binary_path"])
MODELS_ZIP_URL = REALESRGAN_NCNN_DIRECT_URL


def _download_realesrgan_binary(callback=None) -> bool:
    """
    Unduh dan ekstrak binary realesrgan-ncnn-vulkan dari GitHub Release.
    Returns True bila berhasil.
    """
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = TOOLS_DIR / "realesrgan-ncnn-vulkan.zip"

    logger.info(f"Mengunduh realesrgan-ncnn-vulkan dari:\n  {MODELS_ZIP_URL}")
    if callback:
        callback("Mengunduh realesrgan-ncnn-vulkan binary...")

    try:
        # Hanya emit callback saat persentase berubah (hindari spam log)
        _last_pct = [-1]

        def _reporthook(block_num, block_size, total_size):
            if callback and total_size > 0:
                pct = min(100, block_num * block_size * 100 // total_size)
                if pct != _last_pct[0]:
                    _last_pct[0] = pct
                    callback(f"  Download: {pct}%")

        urllib.request.urlretrieve(MODELS_ZIP_URL, zip_path, reporthook=_reporthook)

        if callback:
            callback("Mengekstrak binary...")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(TOOLS_DIR)

        zip_path.unlink(missing_ok=True)

        # Pastikan semua binary yang ditemukan punya execute permission
        for candidate in TOOLS_DIR.rglob(BINARY_NAME + "*"):
            if candidate.is_file():
                try:
                    candidate.chmod(
                        candidate.stat().st_mode
                        | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
                    )
                    logger.info(f"chmod +x: {candidate}")
                except Exception as ce:
                    logger.warning(f"chmod gagal untuk {candidate}: {ce}")

        # Pastikan BINARY_PATH juga executable jika ada
        if BINARY_PATH.exists():
            BINARY_PATH.chmod(
                BINARY_PATH.stat().st_mode
                | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
            )

        logger.info(f"Binary berhasil diekstrak ke: {TOOLS_DIR}")
        return True

    except Exception as e:
        logger.error(f"Gagal mengunduh realesrgan-ncnn-vulkan: {e}")
        if zip_path.exists():
            zip_path.unlink()
        return False


def _get_realesrgan_binary() -> Path | None:
    """
    Mencari binary realesrgan-ncnn-vulkan yang executable.
    Prioritas: config path → TOOLS_DIR (rglob) → PATH sistem
    """
    # 1. Path dari config — pastikan executable
    if BINARY_PATH.exists():
        if not os.access(BINARY_PATH, os.X_OK):
            # Coba perbaiki permission
            try:
                BINARY_PATH.chmod(
                    BINARY_PATH.stat().st_mode
                    | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
                )
            except Exception:
                pass
        if os.access(BINARY_PATH, os.X_OK):
            return BINARY_PATH

    # 2. Cari di TOOLS_DIR (rglob, nama persis)
    for f in TOOLS_DIR.rglob(BINARY_NAME):
        if f.is_file():
            if not os.access(f, os.X_OK):
                try:
                    f.chmod(f.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                except Exception:
                    pass
            if os.access(f, os.X_OK):
                return f

    # 3. Cari di PATH sistem
    found = shutil.which(BINARY_NAME)
    if found:
        return Path(found)

    return None


def ensure_realesrgan_binary(callback=None) -> Path | None:
    """Pastikan binary tersedia, download jika belum ada."""
    binary = _get_realesrgan_binary()
    if binary:
        logger.info(f"Binary ditemukan: {binary}")
        return binary

    logger.warning("Binary realesrgan-ncnn-vulkan tidak ditemukan, mencoba mengunduh...")
    success = _download_realesrgan_binary(callback=callback)
    if success:
        return _get_realesrgan_binary()
    return None


# ─── Upscaler Utama ──────────────────────────────────────────────────────────

class Upscaler:
    """Kelas utama untuk melakukan upscaling video."""

    def __init__(self, callback=None):
        """
        callback: fungsi opsional untuk melaporkan progress (dipanggil dengan string pesan)
        """
        self.callback = callback

    def _log(self, msg: str):
        logger.info(msg)
        if self.callback:
            self.callback(msg)

    # ── Bicubic dengan FFmpeg ──────────────────────────────────────────────

    def upscale_bicubic(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        width: int = TARGET_WIDTH,
        height: int = TARGET_HEIGHT,
    ) -> Path:
        """Upscale video menggunakan algoritma Bicubic via FFmpeg."""
        input_path  = Path(input_path)
        output_path = Path(output_path) if output_path else (
            OUTPUT_DIR / f"{input_path.stem}_upscaled_bicubic.mp4"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self._log(f"[Bicubic] Upscaling {input_path.name} → {width}x{height}")

        cmd = [
            FFMPEG_PATH, "-y",
            "-i", str(input_path),
            "-vf", f"scale={width}:{height}:flags=bicubic",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "copy",
            str(output_path),
        ]
        self._run_ffmpeg(cmd, "Bicubic upscaling")
        self._log(f"[Bicubic] Selesai: {output_path}")
        return output_path

    # ── Real-ESRGAN ────────────────────────────────────────────────────────

    def upscale_realesrgan(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        width: int = TARGET_WIDTH,
        height: int = TARGET_HEIGHT,
    ) -> Path:
        """
        Upscale video menggunakan Real-ESRGAN (ncnn-vulkan).
        Pipeline: ekstrak frame → ESRGAN per frame → gabungkan → resize akhir.
        """
        input_path  = Path(input_path)
        output_path = Path(output_path) if output_path else (
            OUTPUT_DIR / f"{input_path.stem}_upscaled_realesrgan.mp4"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        binary = ensure_realesrgan_binary(callback=self.callback)
        if not binary:
            self._log(
                "[ESRGAN] ⚠ Binary tidak tersedia, fallback ke Bicubic."
            )
            return self.upscale_bicubic(input_path, output_path, width, height)

        # Buat temp dir untuk frame
        with tempfile.TemporaryDirectory(dir=TEMP_DIR, prefix="esrgan_") as tmpdir:
            tmp = Path(tmpdir)
            frames_in  = tmp / "frames_in"
            frames_out = tmp / "frames_out"
            frames_in.mkdir()
            frames_out.mkdir()

            # 1. Ekstrak audio
            audio_path = tmp / "audio.aac"
            has_audio  = self._extract_audio(input_path, audio_path)

            # 2. Ekstrak frame
            self._log("[ESRGAN] Mengekstrak frame...")
            fps = self._get_fps(input_path)
            self._extract_frames(input_path, frames_in)

            frame_list = sorted(frames_in.glob("*.png"))
            total = len(frame_list)
            self._log(f"[ESRGAN] Total frame: {total}")
            if total == 0:
                raise RuntimeError("Tidak ada frame yang diekstrak.")

            # 3. Jalankan Real-ESRGAN
            # Estimasi waktu: ~8-15 detik per frame pada GPU mid-range
            est_min = max(1, int(total * 8 / 60))
            est_max = max(2, int(total * 15 / 60))
            self._log(
                f"[ESRGAN] Menjalankan AI upscaling "
                f"(estimasi {est_min}–{est_max} menit, harap tunggu)..."
            )
            self._run_realesrgan(binary, frames_in, frames_out)

            # 4. Gabung frame → video sementara
            self._log("[ESRGAN] Menggabungkan frame menjadi video...")
            temp_video = tmp / "temp_video.mp4"
            # Tentukan resolusi output esrgan (scale factor 4x)
            sample_frame = next(frames_out.glob("*.png"), None)
            if sample_frame:
                esrgan_w, esrgan_h = self._get_image_resolution(sample_frame)
            else:
                esrgan_w, esrgan_h = TARGET_WIDTH * 4, TARGET_HEIGHT * 4

            self._frames_to_video(frames_out, temp_video, fps, audio_path if has_audio else None)

            # 5. Resize ke target resolusi (jika berbeda)
            if esrgan_w != width or esrgan_h != height:
                self._log(f"[ESRGAN] Resize {esrgan_w}x{esrgan_h} → {width}x{height}")
                self._resize_video(temp_video, output_path, width, height)
            else:
                shutil.copy2(temp_video, output_path)

        self._log(f"[ESRGAN] Selesai: {output_path}")
        return output_path

    # ── Fungsi Pembantu ────────────────────────────────────────────────────

    def _run_ffmpeg(self, cmd: list, label: str = "FFmpeg"):
        """Jalankan perintah FFmpeg dan tangani error."""
        logger.debug(f"{label}: {' '.join(cmd)}")
        proc = subprocess.run(
            cmd, capture_output=True, text=True
        )
        if proc.returncode != 0:
            raise RuntimeError(f"{label} gagal:\n{proc.stderr[-2000:]}")

    def _run_realesrgan(self, binary: Path, input_dir: Path, output_dir: Path):
        """
        Jalankan binary realesrgan-ncnn-vulkan pada folder frame.
        Urutan percobaan: GPU yang dikonfigurasi → GPU lain → llvmpipe (software renderer).
        Setiap GPU dicoba dengan tile cascade: tile_size default → 256 → 128 jika blank.
        llvmpipe selalu dimulai dari tile=256 untuk mencegah SIGSEGV (exit=-11).
        """
        import re as _re
        import tempfile as _tempfile

        cfg      = REALESRGAN_CONFIG
        model    = cfg.get("model_name", "realesrgan-x4plus")
        scale    = str(cfg.get("scale", 4))
        tile_cfg = str(cfg.get("tile_size", 0))
        use_gpu  = cfg.get("use_gpu", True)
        pref_gpu = int(cfg.get("gpu_id", 1))

        # Cari folder models (model params)
        model_dir = TOOLS_DIR / "models"
        for candidate in [Path(str(binary)).parent / "models", TOOLS_DIR / "models", TOOLS_DIR]:
            if candidate.exists() and any(candidate.glob("*.bin")):
                model_dir = candidate
                break
        logger.debug(f"Model dir: {model_dir}")

        # Hitung rata-rata ukuran frame INPUT untuk deteksi blank yang akurat
        in_frames  = list(input_dir.glob("*.png"))
        avg_in_size = (
            sum(f.stat().st_size for f in in_frames) / len(in_frames)
            if in_frames else 0
        )
        logger.debug(f"Avg input frame size: {avg_in_size/1024:.0f} KB")

        # ── Helper functions ───────────────────────────────────────────────

        def _build_cmd(gpu_flag: str, tile: str, low_mem: bool = False) -> list:
            cmd = [
                str(binary),
                "-i", str(input_dir),
                "-o", str(output_dir),
                "-n", model,
                "-s", scale,
                "-t", tile,
                "-g", gpu_flag,
                "-m", str(model_dir),
                "-f", "png",
            ]
            if low_mem:
                # Kurangi thread untuk hemat memori (terutama llvmpipe)
                cmd += ["-j", "1:1:1"]
            return cmd

        def _has_gpu_error(stderr: str, stdout: str) -> bool:
            keywords = [
                "vkqueuesubmit failed",
                "vkcreatedevice failed",
                "context is lost",
                "vulkan error",
                "vk_error",
                "invalid gpu device",
            ]
            combined = (stderr + stdout).lower()
            return any(kw in combined for kw in keywords)

        def _read_png_dims(path: Path) -> tuple[int, int] | None:
            """
            Baca dimensi PNG dari header (24 byte pertama) tanpa load seluruh file.
            Format: signature(8) + IHDR_length(4) + 'IHDR'(4) + width(4) + height(4)
            """
            try:
                import struct
                with open(path, "rb") as f:
                    header = f.read(24)
                if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
                    return None
                w = struct.unpack(">I", header[16:20])[0]
                h = struct.unpack(">I", header[20:24])[0]
                return w, h
            except Exception:
                return None

        def _output_ok(out_dir: Path) -> bool:
            """
            Cek frame output valid menggunakan tiga kriteria:
            1. Jumlah frame = jumlah input
            2. Resolusi output = input × scale (cek via PNG header, cepat)
            3. Ukuran file output cukup besar (bukan frame hitam/kosong)
               Frame hitam 2880×1920 PNG ≈ <50KB; konten nyata >>100KB.
            Fallback ke cek ukuran file jika pembacaan header gagal.
            """
            out_frames = list(out_dir.glob("*.png"))
            if not out_frames:
                return False
            # Jumlah frame harus sama dengan input
            if len(out_frames) != len(in_frames):
                logger.debug(
                    f"Frame count mismatch: out={len(out_frames)}, in={len(in_frames)}"
                )
                return False

            expected_scale = int(scale)  # biasanya 4

            # Cek ukuran file output
            avg_out = sum(f.stat().st_size for f in out_frames) / len(out_frames)

            # Cek resolusi output menggunakan PNG header (sangat cepat, hanya baca 24 byte)
            sample_out = out_frames[0]
            out_dims = _read_png_dims(sample_out)
            if out_dims:
                out_w, out_h = out_dims
                # Cek dimensi input juga
                if in_frames:
                    in_dims = _read_png_dims(in_frames[0])
                    if in_dims:
                        in_w, in_h = in_dims
                        expected_w = in_w * expected_scale
                        expected_h = in_h * expected_scale
                        dim_ok = (out_w >= expected_w * 0.9) and (out_h >= expected_h * 0.9)
                        if not dim_ok:
                            self._log(
                                f"[ESRGAN] ✗ Resolusi output {out_w}×{out_h} tidak sesuai "
                                f"(harusnya ~{expected_w}×{expected_h}, model tidak berhasil diaplikasikan)"
                            )
                            return False

                        # Dimensi OK — verifikasi konten bukan hitam/kosong.
                        # Frame hitam 2880×1920 PNG ≈ 5–50 KB (sangat kompres).
                        # Frame nyata 2880×1920 PNG >> ukuran frame input (720×480).
                        # Threshold konservatif: max(100KB, 1.5× rata-rata ukuran frame input).
                        content_threshold = max(100 * 1024, avg_in_size * 1.5)
                        if avg_in_size > 0 and avg_out < content_threshold:
                            self._log(
                                f"[ESRGAN] ✗ Frame output terdeteksi hitam/kosong "
                                f"(avg={avg_out/1024:.0f}KB, threshold={content_threshold/1024:.0f}KB) — "
                                f"kemungkinan bug GPU/Vulkan, akan mencoba GPU/tile lain"
                            )
                            return False

                        logger.debug(
                            f"Resolusi output {out_w}×{out_h} ✓, "
                            f"avg size {avg_out/1024:.0f}KB ✓"
                        )
                        return True

            # Fallback: cek ukuran file jika header gagal dibaca
            if avg_in_size > 0:
                ok = avg_out > avg_in_size * 2.0
                logger.debug(
                    f"Frame size fallback: out={avg_out/1024:.0f}KB, "
                    f"in={avg_in_size/1024:.0f}KB → {'OK' if ok else 'BLANK'}"
                )
                return ok
            return avg_out > 64 * 1024

        def _clean_output():
            for f in output_dir.glob("*.png"):
                f.unlink(missing_ok=True)

        # Return values untuk _try_gpu
        _OK         = "ok"
        _HARD_FAIL  = "hard_fail"   # Error Vulkan/GPU keras → jangan retry tile
        _SIGSEGV    = "sigsegv"     # exit=-11, kemungkinan memory → coba tile lebih kecil
        _BLANK      = "blank"       # Exit 0 tapi blank → retry dengan tile lebih kecil

        def _try_gpu(gpu_id: int, label: str, tile: str, low_mem: bool = False) -> str:
            """
            Coba satu GPU dengan tile_size tertentu.
            Returns: _OK | _HARD_FAIL | _SIGSEGV | _BLANK
            """
            mem_tag = " [low-mem]" if low_mem else ""
            self._log(f"[ESRGAN] Mencoba {label} (tile={tile}{mem_tag})...")
            cmd = _build_cmd(str(gpu_id), tile, low_mem=low_mem)
            logger.debug(f"CMD: {' '.join(cmd)}")

            # Gunakan Popen untuk menampilkan progress real-time (ESRGAN output "X.XX%")
            proc_obj = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            stdout_lines: list[str] = []
            last_pct = [-1]
            try:
                for line in proc_obj.stdout:  # type: ignore[union-attr]
                    line = line.rstrip()
                    stdout_lines.append(line)
                    # Tampiilkan persentase kemajuan setiap 10%
                    try:
                        pct = int(float(line.strip().replace("%", "")))
                        if pct != last_pct[0] and pct % 10 == 0:
                            self._log(f"[ESRGAN]   {label}: {pct}%")
                            last_pct[0] = pct
                    except (ValueError, AttributeError):
                        pass
            except Exception:
                pass
            proc_obj.wait()

            # Buat objek yang kompatibel dengan kode lama
            all_output = "\n".join(stdout_lines)
            _rc = proc_obj.returncode

            class _ProcResult:
                returncode = _rc
                stderr = all_output
                stdout = ""
            proc = _ProcResult()

            # SIGSEGV (exit=-11) → kemungkinan OOM, coba tile lebih kecil
            if proc.returncode == -11:
                self._log(f"[ESRGAN] ✗ {label} crash (SIGSEGV/OOM, tile={tile})")
                _clean_output()
                return _SIGSEGV

            if proc.returncode != 0 or _has_gpu_error(proc.stderr, proc.stdout):
                reason = (
                    "Vulkan/GPU error"
                    if _has_gpu_error(proc.stderr, proc.stdout)
                    else f"exit={proc.returncode}"
                )
                self._log(f"[ESRGAN] ✗ {label} gagal ({reason})")
                last_lines = [
                    l for l in proc.stderr.strip().splitlines()
                    if l.strip() and not l.startswith("[")
                ]
                if last_lines:
                    logger.debug(f"  stderr: {last_lines[-1]}")
                _clean_output()
                return _HARD_FAIL

            if not _output_ok(output_dir):
                # _output_ok sudah log pesan detail; tambahkan ukuran file sebagai info tambahan
                out_frames = list(output_dir.glob("*.png"))
                if out_frames and not any("Resolusi output" in msg for msg in [""]):
                    avg_out = sum(f.stat().st_size for f in out_frames) / len(out_frames)
                    logger.debug(
                        f"  avg output size: {avg_out/1024:.0f}KB "
                        f"(threshold: {avg_in_size*2/1024:.0f}KB)"
                    )
                _clean_output()
                return _BLANK

            self._log(f"[ESRGAN] ✓ Berhasil dengan {label}")
            return _OK

        # ── Deteksi GPU yang tersedia ────────────────────────────────────────
        with _tempfile.NamedTemporaryFile(suffix=".png", delete=False) as _tf:
            dummy_png = Path(_tf.name)
        detect_proc = subprocess.run(
            [str(binary), "-i", str(dummy_png), "-o", str(dummy_png)],
            capture_output=True, text=True
        )
        try:
            dummy_png.unlink(missing_ok=True)
        except Exception:
            pass
        combined_out  = detect_proc.stderr + detect_proc.stdout
        detected_ids  = sorted(set(
            int(m) for m in _re.findall(r"^\[(\d+) ", combined_out, _re.M)
        ))
        if not detected_ids:
            detected_ids = [0, 1, 2]
        logger.debug(f"GPU terdeteksi: {detected_ids}")

        # llvmpipe = ID tertinggi (software renderer)
        LLVMPIPE_ID = max(detected_ids)

        # Urutan: GPU pilihan → GPU hardware lain → llvmpipe
        preferred = [pref_gpu] if use_gpu else []
        others    = [g for g in detected_ids if g != pref_gpu and g != LLVMPIPE_ID]
        gpu_order = preferred + others + [LLVMPIPE_ID]
        seen = set()
        gpu_order = [g for g in gpu_order if not (g in seen or seen.add(g))]

        logger.debug(f"Urutan GPU yang akan dicoba: {gpu_order}")

        # ── Tile size cascade per GPU ─────────────────────────────────────────
        # tile_cfg=0 (auto): coba 0 → 256 → 128 jika blank/sigsegv
        # tile_cfg!=0: coba nilai user saja (tanpa cascade)
        # llvmpipe: mulai dari 256 (hindari SIGSEGV dengan tile=0), pakai low_mem=True
        hw_tiles = (
            [tile_cfg, "256", "128"] if tile_cfg == "0" else [tile_cfg]
        )
        sw_tiles = ["256", "128", "64"]  # llvmpipe: mulai kecil, turun terus jika crash

        # ── Coba GPU satu per satu dengan cascade tile ────────────────────────
        for gid in gpu_order:
            is_software = gid == LLVMPIPE_ID
            label       = "llvmpipe/CPU" if is_software else f"GPU {gid}"
            tile_list   = sw_tiles if is_software else hw_tiles

            for tile in tile_list:
                result = _try_gpu(gid, label, tile, low_mem=is_software)
                if result == _OK:
                    return  # Berhasil
                if result == _HARD_FAIL:
                    break   # Error keras (Vulkan/GPU error) → skip ke GPU berikutnya
                # _BLANK atau _SIGSEGV → lanjut ke tile lebih kecil
                if tile != tile_list[-1]:
                    self._log(
                        f"[ESRGAN] Mencoba ulang {label} dengan tile_size lebih kecil..."
                    )

        # Semua GPU & tile gagal
        raise RuntimeError(
            f"realesrgan-ncnn-vulkan gagal di semua GPU ({gpu_order}). "
            "Periksa driver Vulkan atau coba set tile_size=128 di config.py."
        )

    def _extract_frames(self, video: Path, output_dir: Path) -> None:
        """
        Ekstrak semua frame dari video sebagai PNG RGB24 standar.
        `-pix_fmt rgb24` penting untuk kompatibilitas ESRGAN — mencegah
        output blank yang disebabkan oleh colorspace/alpha/bit-depth non-standar.
        """
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", str(video),
            "-q:v", "1",
            "-pix_fmt", "rgb24",   # Paksa RGB 8-bit standar (wajib untuk ESRGAN)
            str(output_dir / "frame_%08d.png"),
        ]
        self._run_ffmpeg(cmd, "Ekstrak frame")

    def _frames_to_video(
        self,
        frames_dir: Path,
        output: Path,
        fps: float,
        audio_path: Path | None = None,
    ) -> None:
        """Gabungkan folder frame PNG menjadi video MP4."""
        cmd = [
            FFMPEG_PATH, "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%08d.png"),
        ]
        if audio_path and audio_path.exists():
            cmd += ["-i", str(audio_path), "-c:a", "aac", "-b:a", "128k"]

        cmd += [
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            str(output),
        ]
        self._run_ffmpeg(cmd, "Gabung frame")

    def _resize_video(self, input: Path, output: Path, width: int, height: int) -> None:
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", str(input),
            "-vf", f"scale={width}:{height}:flags=lanczos",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "copy",
            str(output),
        ]
        self._run_ffmpeg(cmd, "Resize video")

    def _extract_audio(self, video: Path, output_audio: Path) -> bool:
        """Ekstrak audio track. Returns True jika ada audio."""
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", str(video),
            "-vn",
            "-acodec", "aac",
            "-b:a", "128k",
            str(output_audio),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode == 0 and output_audio.exists() and output_audio.stat().st_size > 0

    def _get_fps(self, video: Path) -> float:
        """Dapatkan FPS dari video menggunakan ffprobe."""
        from metadata_extractor import extract_metadata
        try:
            meta = extract_metadata(video)
            return meta["video"]["fps"] or 25.0
        except Exception:
            return 25.0

    def _get_image_resolution(self, image_path: Path) -> tuple[int, int]:
        """Dapatkan resolusi gambar PNG dengan ffprobe."""
        cmd = [
            FFPROBE_PATH,
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            str(image_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            import json
            data = json.loads(result.stdout)
            stream = data["streams"][0]
            return int(stream["width"]), int(stream["height"])
        except Exception:
            return TARGET_WIDTH, TARGET_HEIGHT


# ─── Fungsi Helper Publik ─────────────────────────────────────────────────────

def upscale_video(
    input_path: str | Path,
    method: str = "realesrgan",
    output_path: str | Path | None = None,
    callback=None,
) -> Path:
    """
    Fungsi utama upscaling video.

    Args:
        input_path: Path video input SD
        method: "realesrgan" atau "bicubic"
        output_path: Path output (opsional, auto-generate jika None)
        callback: fungsi(str) untuk pelaporan progress

    Returns:
        Path file output
    """
    upscaler = Upscaler(callback=callback)
    method = method.lower().strip()

    if method == "realesrgan":
        return upscaler.upscale_realesrgan(input_path, output_path)
    elif method == "bicubic":
        return upscaler.upscale_bicubic(input_path, output_path)
    else:
        raise ValueError(f"Method tidak dikenal: '{method}'. Pilih 'realesrgan' atau 'bicubic'.")


# ─── CLI Standalone ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import logging as _logging
    from config import LOG_FORMAT, LOG_DATE

    _logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE, level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python upscaler.py <video_file> [realesrgan|bicubic]")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    method = sys.argv[2] if len(sys.argv) > 2 else "realesrgan"

    print(f"Upscaling '{input_file.name}' menggunakan metode: {method}")
    result = upscale_video(input_file, method=method, callback=print)
    print(f"\n✓ Output: {result}")

