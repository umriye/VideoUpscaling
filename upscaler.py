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
            self._log("[ESRGAN] Menjalankan AI upscaling...")
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
        Tidak menggunakan -g -1 karena tidak didukung binary ini.
        """
        cfg     = REALESRGAN_CONFIG
        model   = cfg.get("model_name", "realesrgan-x4plus")
        scale   = str(cfg.get("scale", 4))
        tile    = str(cfg.get("tile_size", 0))
        use_gpu = cfg.get("use_gpu", True)
        pref_gpu = int(cfg.get("gpu_id", 1))

        # Cari folder models (model params)
        model_dir = TOOLS_DIR / "models"  # default
        for candidate in [Path(str(binary)).parent / "models", TOOLS_DIR / "models", TOOLS_DIR]:
            if candidate.exists() and any(candidate.glob("*.bin")):
                model_dir = candidate
                break
        logger.debug(f"Model dir: {model_dir}")

        def _build_cmd(gpu_flag: str) -> list:
            return [
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

        def _has_gpu_error(stderr: str, stdout: str) -> bool:
            """Deteksi kegagalan GPU dari output binary."""
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

        def _output_ok(out_dir: Path) -> bool:
            """
            Cek hasil frame ESRGAN valid (tidak kosong & tidak blank).
            Frame 4x upscale nyata untuk video SD umumnya > 1MB per PNG.
            """
            frames = list(out_dir.glob("*.png"))
            if not frames:
                return False
            # File blank/hitam sangat kecil (< 256KB), real content biasanya > 1MB
            avg_size = sum(f.stat().st_size for f in frames) / len(frames)
            ok = avg_size > 256 * 1024  # > 256KB per frame
            if not ok:
                logger.debug(f"Output frame avg size {avg_size/1024:.0f}KB → dianggap blank")
            return ok

        def _clean_output():
            for f in output_dir.glob("*.png"):
                f.unlink(missing_ok=True)

        def _try_gpu(gpu_id: int, label: str) -> bool:
            """Coba satu GPU. Return True jika berhasil."""
            self._log(f"[ESRGAN] Mencoba {label}...")
            cmd = _build_cmd(str(gpu_id))
            logger.debug(f"CMD: {' '.join(cmd)}")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            combined_out = proc.stderr + proc.stdout

            if proc.returncode != 0 or _has_gpu_error(proc.stderr, proc.stdout):
                reason = f"exit={proc.returncode}"
                if _has_gpu_error(proc.stderr, proc.stdout):
                    reason = "Vulkan/GPU error"
                self._log(f"[ESRGAN] ✗ GPU {gpu_id} gagal ({reason})")
                logger.debug(f"ESRGAN stderr (GPU {gpu_id}): {combined_out[-500:]}")
                _clean_output()
                return False

            if not _output_ok(output_dir):
                self._log(f"[ESRGAN] ✗ GPU {gpu_id} menghasilkan frame blank/kosong")
                _clean_output()
                return False

            self._log(f"[ESRGAN] ✓ Berhasil dengan {label} (GPU {gpu_id})")
            return True

        # ── Bangun urutan GPU yang akan dicoba ──────────────────────────────
        # Deteksi GPU yang tersedia: jalankan binary dengan input dummy PNG → GPU list muncul di stderr
        import re
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as _tf:
            dummy_png = Path(_tf.name)
        detect_proc = subprocess.run(
            [str(binary), "-i", str(dummy_png), "-o", str(dummy_png)],
            capture_output=True, text=True
        )
        combined_out = detect_proc.stderr + detect_proc.stdout
        detected_ids = sorted(set(
            int(m) for m in re.findall(r"^\[(\d+) ", combined_out, re.M)
        ))
        if not detected_ids:
            detected_ids = [0, 1, 2]  # default fallback
        logger.debug(f"GPU terdeteksi: {detected_ids}")

        # Urutkan: GPU pilihan dulu, lalu sisanya, llvmpipe/software selalu terakhir
        LLVMPIPE_ID = max(detected_ids)  # biasanya ID tertinggi = software renderer
        preferred = [pref_gpu] if use_gpu else []
        others = [g for g in detected_ids if g != pref_gpu and g != LLVMPIPE_ID]
        gpu_order = preferred + others + [LLVMPIPE_ID]
        # Hapus duplikat sambil pertahankan urutan
        seen = set()
        gpu_order = [g for g in gpu_order if not (g in seen or seen.add(g))]

        labels = {LLVMPIPE_ID: "llvmpipe/CPU"}
        logger.debug(f"Urutan GPU yang akan dicoba: {gpu_order}")

        # ── Coba GPU satu per satu ──────────────────────────────────────────
        for gid in gpu_order:
            label = labels.get(gid, f"GPU {gid}")
            if _try_gpu(gid, label):
                return  # Berhasil

        # Semua GPU gagal
        raise RuntimeError(
            f"realesrgan-ncnn-vulkan gagal di semua GPU ({gpu_order}). "
            "Coba kurangi tile_size (misal 256) atau periksa driver Vulkan."
        )

    def _extract_frames(self, video: Path, output_dir: Path) -> None:
        """Ekstrak semua frame dari video."""
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", str(video),
            "-q:v", "1",
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

