"""
main.py - CLI Entry Point: Pipeline AI Video Upscaling
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from config import (
    INPUT_DIR, OUTPUT_DIR, REPORTS_DIR, TEMP_DIR,
    SUPPORTED_VIDEO_EXTENSIONS, HEVC_CONFIG,
    LOG_FORMAT, LOG_DATE,
)
from metadata_extractor import extract_metadata, save_metadata
from upscaler import upscale_video
from compressor import Compressor
from quality_analyzer import QualityAnalyzer, ReportGenerator

logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE, level=logging.INFO)
logger = logging.getLogger(__name__)


def _find_input_videos(input_dir: Path) -> list[Path]:
    """Cari semua video di folder input."""
    videos = []
    for ext in SUPPORTED_VIDEO_EXTENSIONS:
        videos.extend(input_dir.glob(f"*{ext}"))
        videos.extend(input_dir.glob(f"*{ext.upper()}"))
    return sorted(set(videos))


def process_video(video_path: Path, args: argparse.Namespace) -> dict:
    """Jalankan pipeline lengkap pada satu video."""
    stem = video_path.stem
    logger.info(f"\n{'='*60}")
    logger.info(f"📹 Memproses: {video_path.name}")
    logger.info(f"{'='*60}")

    pipeline_results = {
        "input_video": str(video_path),
        "stem": stem,
        "metadata": None,
        "upscaling": {},
        "compression": {},
        "quality": [],
        "report_paths": {},
        "errors": [],
        "duration_sec": 0,
    }
    start_time = time.time()

    # ── Tahap 1: Ekstraksi Metadata ──────────────────────────────────────────
    logger.info("\n🔍 Tahap 1: Ekstraksi Metadata")
    try:
        metadata = extract_metadata(video_path)
        pipeline_results["metadata"] = metadata
        save_metadata(metadata, REPORTS_DIR / f"{stem}_metadata.json")
        w, h, fps = metadata["video"]["width"], metadata["video"]["height"], metadata["video"]["fps"]
        logger.info(f"  ✓ {w}x{h} @ {fps}fps | Durasi: {metadata['duration_str']}")
    except Exception as e:
        logger.error(f"  ✗ Metadata gagal: {e}")
        pipeline_results["errors"].append(f"metadata: {e}")

    # ── Tahap 2: AI Upscaling ────────────────────────────────────────────────
    logger.info("\n🚀 Tahap 2: AI Upscaling")
    upscaled_realesrgan = upscaled_bicubic = None

    try:
        logger.info("  → Real-ESRGAN upscaling...")
        t0 = time.time()
        upscaled_realesrgan = upscale_video(video_path, method="realesrgan")
        logger.info(f"  ✓ ESRGAN: {upscaled_realesrgan.name} ({round(time.time()-t0,1)}s)")
        pipeline_results["upscaling"]["realesrgan"] = str(upscaled_realesrgan)
    except Exception as e:
        logger.error(f"  ✗ Real-ESRGAN gagal: {e}")
        pipeline_results["errors"].append(f"realesrgan: {e}")

    if not args.no_bicubic:
        try:
            logger.info("  → Bicubic upscaling (baseline)...")
            t0 = time.time()
            upscaled_bicubic = upscale_video(video_path, method="bicubic")
            logger.info(f"  ✓ Bicubic: {upscaled_bicubic.name} ({round(time.time()-t0,1)}s)")
            pipeline_results["upscaling"]["bicubic"] = str(upscaled_bicubic)
        except Exception as e:
            logger.error(f"  ✗ Bicubic gagal: {e}")
            pipeline_results["errors"].append(f"bicubic: {e}")

    # ── Tahap 3: Rekompresi HEVC ─────────────────────────────────────────────
    logger.info("\n💾 Tahap 3: Rekompresi HEVC")
    comp = Compressor()
    source = upscaled_realesrgan or upscaled_bicubic or video_path
    for crf in HEVC_CONFIG["crf_values"]:
        try:
            out = comp.compress(source, crf)
            pipeline_results["compression"][f"crf{crf}"] = str(out)
        except Exception as e:
            logger.error(f"  ✗ CRF {crf} gagal: {e}")
            pipeline_results["errors"].append(f"compress_crf{crf}: {e}")

    # ── Tahap 4: Analisis Kualitas ────────────────────────────────────────────
    if not args.skip_vmaf:
        logger.info("\n📊 Tahap 4: Analisis Kualitas VMAF")
        analyzer = QualityAnalyzer()
        quality_results = []
        ref_video = upscaled_realesrgan or upscaled_bicubic
        if ref_video:
            for crf_key, comp_path in pipeline_results["compression"].items():
                try:
                    r = analyzer.analyze(ref_video, Path(comp_path), label=f"{stem}_{crf_key}")
                    quality_results.append(r)
                except Exception as e:
                    logger.error(f"  ✗ VMAF {crf_key}: {e}")
                    pipeline_results["errors"].append(f"vmaf_{crf_key}: {e}")
            if upscaled_bicubic and upscaled_realesrgan:
                try:
                    r = analyzer.analyze(upscaled_realesrgan, upscaled_bicubic,
                                         label=f"{stem}_bicubic_vs_esrgan")
                    quality_results.append(r)
                except Exception as e:
                    logger.error(f"  ✗ Perbandingan ESRGAN vs Bicubic: {e}")
        else:
            logger.warning("  ⚠ Tidak ada referensi untuk VMAF, dilewati.")
        pipeline_results["quality"] = quality_results

    # ── Tahap 5: Generate Laporan ─────────────────────────────────────────────
    logger.info("\n📄 Tahap 5: Generate Laporan")
    try:
        if pipeline_results["quality"]:
            gen = ReportGenerator()
            rp = gen.generate(pipeline_results["quality"], stem=stem)
            pipeline_results["report_paths"] = {k: str(v) for k, v in rp.items()}
            for fmt, path in rp.items():
                logger.info(f"  ✓ {fmt.upper()}: {path}")
        pipeline_json = REPORTS_DIR / f"{stem}_pipeline_results.json"
        with open(pipeline_json, "w", encoding="utf-8") as f:
            json.dump(pipeline_results, f, indent=2, ensure_ascii=False)
        logger.info(f"  ✓ Pipeline results: {pipeline_json}")
    except Exception as e:
        logger.error(f"  ✗ Laporan gagal: {e}")
        pipeline_results["errors"].append(f"report: {e}")

    pipeline_results["duration_sec"] = round(time.time() - start_time, 1)
    logger.info(f"\n✅ Selesai dalam {pipeline_results['duration_sec']}s")
    if pipeline_results["errors"]:
        logger.warning(f"  ⚠ {len(pipeline_results['errors'])} error(s)")
    return pipeline_results


def main():
    parser = argparse.ArgumentParser(
        description="AI Video Upscaling Pipeline – SD ke HD menggunakan Real-ESRGAN",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python main.py                           # Proses semua video di input/
  python main.py -i video.mp4             # Satu video spesifik
  python main.py -i video.mp4 --skip-vmaf # Tanpa VMAF
  python main.py --no-bicubic             # Tanpa perbandingan Bicubic
        """,
    )
    parser.add_argument("-i", "--input", type=str, default=None,
                        help="Path video input (default: semua di input/)")
    parser.add_argument("--skip-vmaf", action="store_true",
                        help="Skip analisis VMAF/PSNR/SSIM")
    parser.add_argument("--no-bicubic", action="store_true",
                        help="Skip Bicubic comparison")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Log detail")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║    AI Video Upscaling Pipeline v1.0          ║")
    logger.info("║    SD → HD | Real-ESRGAN + HEVC + VMAF       ║")
    logger.info("╚══════════════════════════════════════════════╝")

    if args.input:
        videos = [Path(args.input)]
        if not videos[0].exists():
            logger.error(f"File tidak ditemukan: {videos[0]}")
            sys.exit(1)
    else:
        videos = _find_input_videos(INPUT_DIR)
        if not videos:
            logger.error(
                f"Tidak ada video di '{INPUT_DIR}'.\n"
                "Letakkan video SD di input/ atau: python main.py -i <video>"
            )
            sys.exit(1)

    logger.info(f"\n📂 {len(videos)} video akan diproses:")
    for v in videos:
        logger.info(f"  - {v.name}")

    all_results = []
    for video in videos:
        all_results.append(process_video(video, args))

    logger.info(f"\n{'='*60}")
    logger.info(f"🏁 SELESAI — {len(all_results)} video diproses")
    total_err = sum(len(r["errors"]) for r in all_results)
    if total_err:
        logger.warning(f"⚠ Total error: {total_err}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()
