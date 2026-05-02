"""
config.py - Konfigurasi global pipeline AI Video Upscaling
"""

import os
from pathlib import Path

# ─── Direktori Proyek ────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.resolve()
INPUT_DIR    = BASE_DIR / "input"
OUTPUT_DIR   = BASE_DIR / "output"
TEMP_DIR     = BASE_DIR / "temp"
REPORTS_DIR  = BASE_DIR / "reports"
MODELS_DIR   = BASE_DIR / "models"
TOOLS_DIR    = BASE_DIR / "tools"

# Buat direktori jika belum ada
for _d in [INPUT_DIR, OUTPUT_DIR, TEMP_DIR, REPORTS_DIR, MODELS_DIR, TOOLS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ─── Target Resolusi Output ──────────────────────────────────────────────────
TARGET_WIDTH  = 1920   # Full HD 1080p
TARGET_HEIGHT = 1080

# ─── Path FFmpeg ─────────────────────────────────────────────────────────────
# Kosongkan / set "ffmpeg" agar dicari di PATH, atau isi path absolut
FFMPEG_PATH  = "ffmpeg"
FFPROBE_PATH = "ffprobe"

# ─── Pengaturan Real-ESRGAN (menggunakan binary realesrgan-ncnn-vulkan) ──────
REALESRGAN_CONFIG = {
    # Nama model: realesrgan-x4plus | realesrgan-x4plus-anime | realesr-animevideov3 | realesrnet-x4plus
    "model_name":    "realesrgan-x4plus",
    # Faktor skala: 2 atau 4
    "scale":         4,
    # Ukuran tile untuk VRAM rendah (0 = auto). Gunakan 256/128 jika OOM.
    "tile_size":     0,
    # Gunakan GPU Vulkan (True) atau CPU (False)
    "use_gpu":       True,
    # GPU id (0=AMD RADV Renoir - bermasalah Vulkan, 1=NVIDIA GTX 1650)
    "gpu_id":        1,
    # Path binary realesrgan-ncnn-vulkan (kosong = auto-download)
    "binary_path":   str(TOOLS_DIR / "realesrgan-ncnn-vulkan"),
}

# ─── Pengaturan HEVC Compression ─────────────────────────────────────────────
HEVC_CONFIG = {
    "codec":      "libx265",
    "preset":     "medium",            # ultrafast/fast/medium/slow/veryslow
    "crf_values": [18, 23, 28],        # Variasi CRF untuk eksperimen
    "audio_codec": "aac",
    "audio_bitrate": "128k",
}

# ─── Pengaturan Analisis Kualitas ─────────────────────────────────────────────
QUALITY_CONFIG = {
    # Aktifkan analisis VMAF (butuh libvmaf di ffmpeg)
    "enable_vmaf":  True,
    # Aktifkan PSNR dan SSIM
    "enable_psnr":  True,
    "enable_ssim":  True,
    # Subsample frame untuk VMAF (1=semua frame, 5=setiap 5 frame - lebih cepat)
    "vmaf_subsample": 1,
}

# ─── URL Download realesrgan-ncnn-vulkan ──────────────────────────────────────
REALESRGAN_NCNN_RELEASE_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/latest/download/"
    "realesrgan-ncnn-vulkan-{version}-ubuntu.zip"
)
REALESRGAN_NCNN_DIRECT_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/"
    "v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip"
)

# ─── Format Video yang Didukung ───────────────────────────────────────────────
SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv",
    ".flv", ".webm", ".m4v", ".ts", ".mpg", ".mpeg",
}

# ─── Logging ─────────────────────────────────────────────────────────────────
LOG_FORMAT  = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE    = "%Y-%m-%d %H:%M:%S"

