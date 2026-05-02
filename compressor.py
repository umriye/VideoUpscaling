"""
compressor.py - Kompresi video dengan HEVC/H.265 menggunakan FFmpeg
"""

import logging
import subprocess
import sys
from pathlib import Path

from config import (
    FFMPEG_PATH, OUTPUT_DIR, HEVC_CONFIG,
    LOG_FORMAT, LOG_DATE,
)

logger = logging.getLogger(__name__)


class Compressor:
    """Kompresi video HEVC dengan variasi CRF."""

    def __init__(self, callback=None):
        self.callback = callback

    def _log(self, msg: str):
        logger.info(msg)
        if self.callback:
            self.callback(msg)

    def compress(
        self,
        input_path: str | Path,
        crf: int,
        output_path: str | Path | None = None,
        codec: str | None = None,
        preset: str | None = None,
    ) -> Path:
        """
        Kompres video ke HEVC dengan CRF tertentu.

        Args:
            input_path: Path video input
            crf: Constant Rate Factor (18=high quality, 23=balanced, 28=small)
            output_path: Path output (auto jika None)
            codec: Override codec (default dari config: libx265)
            preset: Override preset (default dari config: medium)

        Returns:
            Path file output
        """
        input_path  = Path(input_path)
        codec       = codec  or HEVC_CONFIG["codec"]
        preset      = preset or HEVC_CONFIG["preset"]

        output_path = Path(output_path) if output_path else (
            OUTPUT_DIR / f"{input_path.stem}_hevc_crf{crf}.mp4"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self._log(
            f"[Compressor] Mengompres {input_path.name} | "
            f"codec={codec} | preset={preset} | CRF={crf}"
        )

        cmd = [
            FFMPEG_PATH, "-y",
            "-i", str(input_path),
            "-c:v", codec,
            "-preset", preset,
            "-crf", str(crf),
            "-c:a", HEVC_CONFIG.get("audio_codec", "aac"),
            "-b:a", HEVC_CONFIG.get("audio_bitrate", "128k"),
            "-movflags", "+faststart",
            str(output_path),
        ]

        logger.debug(f"CMD: {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            raise RuntimeError(
                f"FFmpeg kompresi gagal (CRF {crf}):\n{proc.stderr[-2000:]}"
            )

        in_size  = input_path.stat().st_size
        out_size = output_path.stat().st_size
        ratio    = round(in_size / out_size, 2) if out_size > 0 else 0
        saving   = round((1 - out_size / in_size) * 100, 1) if in_size > 0 else 0

        self._log(
            f"[Compressor] ✓ CRF {crf} selesai | "
            f"{in_size // 1024 // 1024}MB → {out_size // 1024 // 1024}MB | "
            f"Kompresi {ratio}x ({saving}% lebih kecil) | {output_path.name}"
        )
        return output_path

    def compress_all_crf(
        self,
        input_path: str | Path,
        crf_values: list[int] | None = None,
        output_dir: str | Path | None = None,
    ) -> dict[int, Path]:
        """
        Kompres video dengan semua nilai CRF yang dikonfigurasi.

        Returns:
            dict {crf_value: output_path}
        """
        input_path  = Path(input_path)
        crf_values  = crf_values or HEVC_CONFIG["crf_values"]
        output_dir  = Path(output_dir) if output_dir else OUTPUT_DIR
        results     = {}

        self._log(
            f"[Compressor] Multi-CRF compression: {crf_values} pada {input_path.name}"
        )

        for crf in crf_values:
            out = output_dir / f"{input_path.stem}_hevc_crf{crf}.mp4"
            try:
                results[crf] = self.compress(input_path, crf, out)
            except RuntimeError as e:
                logger.error(f"Gagal CRF {crf}: {e}")
                results[crf] = None

        return results


def compress_video(
    input_path: str | Path,
    crf: int | None = None,
    callback=None,
) -> dict[int, Path] | Path:
    """
    Fungsi helper untuk kompresi video.
    - Jika crf=None: kompres semua nilai CRF dari config
    - Jika crf diberikan: kompres hanya CRF tersebut
    """
    comp = Compressor(callback=callback)
    if crf is None:
        return comp.compress_all_crf(input_path)
    return comp.compress(input_path, crf)


# ─── CLI Standalone ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE, level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python compressor.py <video_file> [crf]")
        sys.exit(1)

    vpath = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        crf_val = int(sys.argv[2])
        result = compress_video(vpath, crf=crf_val, callback=print)
        print(f"\n✓ Output: {result}")
    else:
        results = compress_video(vpath, callback=print)
        print("\n✓ Semua CRF selesai:")
        for crf, path in results.items():
            print(f"  CRF {crf}: {path}")

