"""
quality_analyzer.py - Analisis kualitas video: VMAF, PSNR, SSIM via FFmpeg
"""

import csv
import json
import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import jinja2
import pandas as pd

from config import (
    FFMPEG_PATH, REPORTS_DIR, QUALITY_CONFIG,
    LOG_FORMAT, LOG_DATE,
)

logger = logging.getLogger(__name__)

# ─── VMAF Interpretasi ────────────────────────────────────────────────────────
VMAF_GRADES = [
    (95, "Excellent", "Visually lossless, tidak terlihat perbedaan"),
    (85, "Good",      "Perbedaan minor, acceptable untuk broadcast"),
    (70, "Fair",      "Kompresi terlihat, masih acceptable"),
    (0,  "Poor",      "Artefak terlihat jelas"),
]


def vmaf_grade(score: float) -> tuple[str, str]:
    """Kembalikan (grade, keterangan) berdasarkan skor VMAF."""
    for threshold, grade, desc in VMAF_GRADES:
        if score >= threshold:
            return grade, desc
    return "Poor", "Artefak terlihat jelas"


# ─── Kelas Analyzer ──────────────────────────────────────────────────────────

class QualityAnalyzer:
    """Analisis kualitas video menggunakan FFmpeg (VMAF, PSNR, SSIM)."""

    def __init__(self, callback=None):
        self.callback = callback

    def _log(self, msg: str):
        logger.info(msg)
        if self.callback:
            self.callback(msg)

    def analyze(
        self,
        reference_path: str | Path,
        distorted_path: str | Path,
        label: str = "",
    ) -> dict:
        """
        Analisis kualitas distorted video vs reference.

        Args:
            reference_path: Video referensi (original/upscaled)
            distorted_path: Video terkompresi yang diuji
            label: Label untuk laporan

        Returns:
            dict berisi skor VMAF, PSNR, SSIM, dll.
        """
        ref  = Path(reference_path)
        dist = Path(distorted_path)
        label = label or dist.stem

        if not ref.exists():
            raise FileNotFoundError(f"Reference tidak ditemukan: {ref}")
        if not dist.exists():
            raise FileNotFoundError(f"Distorted tidak ditemukan: {dist}")

        self._log(f"[Quality] Menganalisis: {dist.name} vs {ref.name}")

        results = {
            "label":            label,
            "reference":        str(ref),
            "distorted":        str(dist),
            "timestamp":        datetime.now().isoformat(),
            "vmaf":             None,
            "psnr":             None,
            "ssim":             None,
            "vmaf_grade":       None,
            "vmaf_description": None,
            "file_size_ref_mb":  round(ref.stat().st_size / 1024**2, 2),
            "file_size_dist_mb": round(dist.stat().st_size / 1024**2, 2),
            "compression_ratio": None,
            "error":            None,
        }

        try:
            if ref.stat().st_size > 0 and dist.stat().st_size > 0:
                results["compression_ratio"] = round(
                    ref.stat().st_size / dist.stat().st_size, 3
                )

            if QUALITY_CONFIG.get("enable_vmaf"):
                subsample = QUALITY_CONFIG.get("vmaf_subsample", 1)
                vmaf_log = Path("/tmp") / f"vmaf_{dist.stem}.json"
                cmd = self._build_vmaf_cmd(ref, dist, vmaf_log, subsample=subsample)

                self._log("[Quality] Menjalankan VMAF analysis (bisa memakan waktu)...")
                proc = subprocess.run(cmd, capture_output=True, text=True)

                if proc.returncode != 0:
                    err_msg = proc.stderr[-800:].strip()
                    self._log(f"[Quality] ✗ VMAF gagal: {err_msg}")
                    results["error"] = f"VMAF gagal: {err_msg[:200]}"
                else:
                    self._parse_vmaf_log(vmaf_log, results)
                    vmaf_log.unlink(missing_ok=True)

        except Exception as e:
            self._log(f"[Quality] ✗ Analisis error: {e}")
            results["error"] = str(e)

        # Grade VMAF
        if results["vmaf"] is not None:
            g, d = vmaf_grade(results["vmaf"])
            results["vmaf_grade"]       = g
            results["vmaf_description"] = d

        self._log(
            f"[Quality] {label}: VMAF={results['vmaf']} | "
            f"PSNR={results['psnr']} dB | SSIM={results['ssim']} | "
            f"Grade={results['vmaf_grade']}"
        )
        return results

    def _build_vmaf_cmd(
        self, ref: Path, dist: Path, log_path: Path, subsample: int = 1
    ) -> list[str]:
        """
        Build perintah FFmpeg untuk VMAF.
        Kompatibel dengan FFmpeg 7.x / libvmaf v3.
        Feature names: psnr (→psnr_y dalam output), float_ssim (→float_ssim)
        """
        base_vf = (
            f"[0:v]setpts=PTS-STARTPTS[ref];"
            f"[1:v]setpts=PTS-STARTPTS[dist];"
            f"[ref][dist]libvmaf="
            f"log_path={log_path}:"
            f"log_fmt=json:"
            f"n_subsample={subsample}"
        )

        # Feature names yang valid di libvmaf v3 (FFmpeg 7.x):
        # "psnr" → menghasilkan psnr_y, psnr_cb, psnr_cr
        # "float_ssim" → menghasilkan float_ssim
        features = []
        if QUALITY_CONFIG.get("enable_psnr"):
            features.append("name=psnr")
        if QUALITY_CONFIG.get("enable_ssim"):
            features.append("name=float_ssim")

        vf = base_vf + (":feature=" + "|".join(features) if features else "")

        return [
            FFMPEG_PATH, "-y",
            "-i", str(ref),
            "-i", str(dist),
            "-filter_complex", vf,
            "-f", "null", "-",
        ]

    def _parse_vmaf_log(self, log_path: Path, results: dict) -> None:
        """Parse file log JSON VMAF (libvmaf v2/v3 format)."""
        if not log_path.exists():
            self._log(f"[Quality] ✗ VMAF log tidak ditemukan: {log_path}")
            return
        try:
            with open(log_path) as f:
                data = json.load(f)

            pooled = data.get("pooled_metrics", {})

            # VMAF
            vmaf_val = pooled.get("vmaf", {}).get("mean")
            if vmaf_val is not None:
                results["vmaf"] = round(vmaf_val, 3)

            # PSNR: libvmaf v3 menggunakan kunci "psnr_y"
            for key in ("psnr_y", "psnr_hvs", "psnr"):
                if key in pooled:
                    results["psnr"] = round(pooled[key]["mean"], 3)
                    break

            # SSIM: libvmaf v3 menggunakan "float_ssim"
            for key in ("float_ssim", "ssim"):
                if key in pooled:
                    results["ssim"] = round(pooled[key]["mean"], 6)
                    break

        except Exception as e:
            self._log(f"[Quality] ✗ Gagal parse VMAF log: {e}")


# ─── Report Generator ─────────────────────────────────────────────────────────

class ReportGenerator:
    """Generate laporan analisis kualitas dalam format JSON, CSV, dan HTML."""

    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Laporan Analisis Kualitas Video - {{ title }}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 2rem; }
    h1 { text-align: center; color: #38bdf8; font-size: 1.8rem; margin-bottom: 0.5rem; }
    .subtitle { text-align: center; color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
    .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
    h2 { color: #7dd3fc; font-size: 1.1rem; margin-bottom: 1rem; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th { background: #0f172a; color: #38bdf8; padding: 10px 12px; text-align: left; font-weight: 600; }
    td { padding: 9px 12px; border-bottom: 1px solid #1e293b; }
    tr:nth-child(even) td { background: rgba(15,23,42,0.4); }
    tr:hover td { background: rgba(30,58,95,0.4); }
    .badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
    .badge-excellent { background: #14532d; color: #4ade80; }
    .badge-good { background: #1e3a5f; color: #38bdf8; }
    .badge-fair { background: #3d2f00; color: #facc15; }
    .badge-poor { background: #450a0a; color: #f87171; }
    .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; }
    .stat { background: #0f172a; border-radius: 8px; padding: 1rem; text-align: center; }
    .stat .val { font-size: 1.8rem; font-weight: 700; color: #38bdf8; }
    .stat .lbl { font-size: 0.75rem; color: #64748b; margin-top: 4px; }
    .ts { text-align: center; color: #475569; font-size: 0.8rem; margin-top: 2rem; }
  </style>
</head>
<body>
<h1>Laporan Analisis Kualitas Video</h1>
<p class="subtitle">{{ title }} | {{ timestamp }}</p>

{% if summary %}
<div class="card">
  <h2>Ringkasan Statistik</h2>
  <div class="stat-grid">
    <div class="stat"><div class="val">{{ summary.total }}</div><div class="lbl">Total Tes</div></div>
    <div class="stat"><div class="val">{{ summary.avg_vmaf }}</div><div class="lbl">Rata-rata VMAF</div></div>
    <div class="stat"><div class="val">{{ summary.avg_psnr }}</div><div class="lbl">Rata-rata PSNR (dB)</div></div>
    <div class="stat"><div class="val">{{ summary.avg_ssim }}</div><div class="lbl">Rata-rata SSIM</div></div>
  </div>
</div>
{% endif %}

<div class="card">
  <h2>Detail Hasil Analisis</h2>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Label</th><th>VMAF</th><th>Grade</th>
        <th>PSNR (dB)</th><th>SSIM</th><th>Rasio Kompresi</th>
        <th>Ref (MB)</th><th>Dist (MB)</th>
      </tr>
    </thead>
    <tbody>
      {% for r in results %}
      <tr>
        <td>{{ loop.index }}</td>
        <td>{{ r.label }}</td>
        <td>{{ r.vmaf if r.vmaf is not none else 'N/A' }}</td>
        <td>
          {% if r.vmaf_grade %}
            <span class="badge badge-{{ r.vmaf_grade.lower() }}">{{ r.vmaf_grade }}</span>
          {% else %}N/A{% endif %}
        </td>
        <td>{{ r.psnr if r.psnr is not none else 'N/A' }}</td>
        <td>{{ r.ssim if r.ssim is not none else 'N/A' }}</td>
        <td>{{ r.compression_ratio if r.compression_ratio is not none else 'N/A' }}</td>
        <td>{{ r.file_size_ref_mb }}</td>
        <td>{{ r.file_size_dist_mb }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<p class="ts">AI Video Upscaling Pipeline &bull; {{ timestamp }}</p>
</body>
</html>"""

    def generate(
        self,
        results: list[dict],
        stem: str,
        output_dir: str | Path = REPORTS_DIR,
    ) -> dict[str, Path]:
        """Generate laporan JSON, CSV, dan HTML."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        paths = {}

        json_path = output_dir / f"{stem}_quality_report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        paths["json"] = json_path

        csv_path = output_dir / f"{stem}_quality_report.csv"
        if results:
            df = pd.DataFrame(results)
            df.to_csv(csv_path, index=False, encoding="utf-8")
        paths["csv"] = csv_path

        html_path = output_dir / f"{stem}_quality_report.html"
        summary   = self._calc_summary(results)
        env       = jinja2.Environment(loader=jinja2.BaseLoader())
        tmpl      = env.from_string(self.HTML_TEMPLATE)
        html_content = tmpl.render(
            title=stem,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            results=results,
            summary=summary,
        )
        html_path.write_text(html_content, encoding="utf-8")
        paths["html"] = html_path

        logger.info(f"Laporan disimpan: JSON={json_path.name}, CSV={csv_path.name}, HTML={html_path.name}")
        return paths

    def _calc_summary(self, results: list[dict]) -> dict | None:
        if not results:
            return None
        vmaf_vals = [r["vmaf"] for r in results if r.get("vmaf") is not None]
        psnr_vals = [r["psnr"] for r in results if r.get("psnr") is not None]
        ssim_vals = [r["ssim"] for r in results if r.get("ssim") is not None]

        def _avg(vals):
            return round(sum(vals) / len(vals), 3) if vals else "N/A"

        return {
            "total":    len(results),
            "avg_vmaf": _avg(vmaf_vals),
            "avg_psnr": _avg(psnr_vals),
            "avg_ssim": _avg(ssim_vals),
        }


# ─── Fungsi Helper Publik ─────────────────────────────────────────────────────

def analyze_quality(
    reference_path: str | Path,
    distorted_path: str | Path,
    label: str = "",
    callback=None,
) -> dict:
    """Analisis kualitas satu pasang video."""
    analyzer = QualityAnalyzer(callback=callback)
    return analyzer.analyze(reference_path, distorted_path, label)


def generate_report(
    results: list[dict],
    stem: str,
    output_dir: str | Path | None = None,
) -> dict[str, Path]:
    """Generate laporan dari list hasil analisis."""
    gen = ReportGenerator()
    return gen.generate(results, stem, output_dir or REPORTS_DIR)


# ─── CLI Standalone ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE, level=logging.INFO)

    if len(sys.argv) < 3:
        print("Usage: python quality_analyzer.py <reference.mp4> <distorted.mp4>")
        sys.exit(1)

    ref_path  = Path(sys.argv[1])
    dist_path = Path(sys.argv[2])

    result = analyze_quality(ref_path, dist_path, label=dist_path.stem, callback=print)
    print(f"\nHasil Analisis:")
    print(json.dumps(result, indent=2))

    reports = generate_report([result], stem=dist_path.stem)
    print(f"\nLaporan:")
    for fmt, path in reports.items():
        print(f"  {fmt}: {path}")

