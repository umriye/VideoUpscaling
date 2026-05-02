"""
metadata_extractor.py - Ekstraksi metadata video menggunakan ffprobe
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

from config import FFPROBE_PATH

logger = logging.getLogger(__name__)


def extract_metadata(video_path: str | Path) -> dict:
    """
    Ekstrak metadata lengkap dari file video menggunakan ffprobe.

    Returns:
        dict berisi informasi video: resolusi, fps, codec, durasi, bitrate, dll.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {video_path}")

    cmd = [
        FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]

    logger.info(f"Mengekstrak metadata: {video_path.name}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe gagal: {e.stderr}") from e
    except FileNotFoundError:
        raise RuntimeError(
            f"ffprobe tidak ditemukan di '{FFPROBE_PATH}'. "
            "Pastikan FFmpeg terinstall dan ada di PATH."
        )

    raw = json.loads(result.stdout)
    return _parse_metadata(raw, video_path)


def _parse_metadata(raw: dict, video_path: Path) -> dict:
    """Parse output ffprobe mentah menjadi dict yang rapi."""
    fmt = raw.get("format", {})
    streams = raw.get("streams", [])

    video_stream = next(
        (s for s in streams if s.get("codec_type") == "video"), {}
    )
    audio_stream = next(
        (s for s in streams if s.get("codec_type") == "audio"), {}
    )

    # Hitung FPS
    fps_raw = video_stream.get("r_frame_rate", "0/1")
    try:
        num, den = fps_raw.split("/")
        fps = round(int(num) / int(den), 3) if int(den) != 0 else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0

    # Durasi
    duration = float(fmt.get("duration", video_stream.get("duration", 0)))

    # File size
    file_size_bytes = int(fmt.get("size", 0))
    file_size_mb = round(file_size_bytes / (1024 ** 2), 2)

    # Bitrate
    bitrate_bps = int(fmt.get("bit_rate", 0))
    bitrate_kbps = round(bitrate_bps / 1000, 1)

    # Jumlah frame
    nb_frames_raw = video_stream.get("nb_frames", "")
    if nb_frames_raw and nb_frames_raw.isdigit():
        nb_frames = int(nb_frames_raw)
    elif fps > 0 and duration > 0:
        nb_frames = int(fps * duration)
    else:
        nb_frames = 0

    # Aspect ratio
    width  = int(video_stream.get("width",  0))
    height = int(video_stream.get("height", 0))
    dar    = video_stream.get("display_aspect_ratio", "N/A")

    metadata = {
        "file_path":     str(video_path.resolve()),
        "file_name":     video_path.name,
        "file_size_mb":  file_size_mb,
        "file_size_bytes": file_size_bytes,
        "format_name":   fmt.get("format_name", "N/A"),
        "format_long":   fmt.get("format_long_name", "N/A"),
        "duration_sec":  round(duration, 3),
        "duration_str":  _seconds_to_hms(duration),
        "bitrate_kbps":  bitrate_kbps,
        "nb_streams":    int(fmt.get("nb_streams", 0)),
        "video": {
            "codec":        video_stream.get("codec_name", "N/A"),
            "codec_long":   video_stream.get("codec_long_name", "N/A"),
            "profile":      video_stream.get("profile", "N/A"),
            "width":        width,
            "height":       height,
            "resolution":   f"{width}x{height}",
            "fps":          fps,
            "fps_raw":      fps_raw,
            "pix_fmt":      video_stream.get("pix_fmt", "N/A"),
            "dar":          dar,
            "nb_frames":    nb_frames,
            "bit_depth":    video_stream.get("bits_per_raw_sample", "N/A"),
        },
        "audio": {
            "codec":        audio_stream.get("codec_name", "N/A"),
            "sample_rate":  audio_stream.get("sample_rate", "N/A"),
            "channels":     audio_stream.get("channels", 0),
            "bitrate_kbps": round(int(audio_stream.get("bit_rate", 0)) / 1000, 1),
        } if audio_stream else None,
    }

    logger.info(
        f"Metadata: {width}x{height} @ {fps}fps | "
        f"{metadata['video']['codec']} | {duration:.1f}s | {file_size_mb}MB"
    )
    return metadata


def _seconds_to_hms(seconds: float) -> str:
    """Konversi detik ke format HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def save_metadata(metadata: dict, output_path: str | Path) -> None:
    """Simpan metadata ke file JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    logger.info(f"Metadata disimpan: {output_path}")


# ─── CLI standalone ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import logging as _logging
    from config import LOG_FORMAT, LOG_DATE, REPORTS_DIR

    _logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE, level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python metadata_extractor.py <video_file>")
        sys.exit(1)

    vpath = Path(sys.argv[1])
    meta  = extract_metadata(vpath)

    print(json.dumps(meta, indent=2, ensure_ascii=False))

    out = REPORTS_DIR / f"{vpath.stem}_metadata.json"
    save_metadata(meta, out)
    print(f"\n✓ Metadata disimpan ke: {out}")

