"""
gui.py - GUI PyQt6 untuk AI Video Upscaling Pipeline
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize,
)
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QPalette, QPixmap,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog,
    QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QSpinBox,
    QSplitter, QStackedWidget, QStatusBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget, QHeaderView,
)

# Pastikan working directory di folder proyek
PROJECT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_DIR))

from config import (
    INPUT_DIR, OUTPUT_DIR, REPORTS_DIR, TARGET_WIDTH, TARGET_HEIGHT,
    REALESRGAN_CONFIG, HEVC_CONFIG, QUALITY_CONFIG,
    SUPPORTED_VIDEO_EXTENSIONS,
)

logger = logging.getLogger(__name__)

# ─── Tema Warna ───────────────────────────────────────────────────────────────
PALETTE = {
    "bg_dark":     "#1E104E",   # Ungu tua – background utama
    "bg_card":     "#452E5A",   # Ungu medium – card/panel
    "bg_input":    "#2a1a5e",   # Ungu sedikit lebih terang – input field
    "accent":      "#FF653F",   # Oranye-merah – aksen utama / CTA
    "accent2":     "#FFC85C",   # Kuning emas – aksen sekunder
    "success":     "#4ade80",   # Hijau – status sukses
    "warning":     "#FFC85C",   # Kuning emas – peringatan
    "error":       "#ff6b6b",   # Merah – error
    "text":        "#f0eaff",   # Putih keunguan – teks utama
    "text_dim":    "#a899c2",   # Abu keunguan – teks redup
    "border":      "#6b4f7a",   # Ungu muda – garis tepi
}

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {PALETTE['bg_dark']};
    color: {PALETTE['text']};
    font-family: 'Segoe UI', 'Ubuntu', system-ui, sans-serif;
    font-size: 13px;
}}
QTabWidget::pane {{
    border: 1px solid {PALETTE['border']};
    background: {PALETTE['bg_card']};
    border-radius: 8px;
}}
QTabBar::tab {{
    background: {PALETTE['bg_dark']};
    color: {PALETTE['text_dim']};
    padding: 10px 22px;
    border: 1px solid {PALETTE['border']};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background: {PALETTE['bg_card']};
    color: {PALETTE['accent']};
    font-weight: bold;
    border-bottom: 2px solid {PALETTE['accent']};
}}
QPushButton {{
    background-color: {PALETTE['accent']};
    color: #0f172a;
    border: none;
    border-radius: 7px;
    padding: 9px 20px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: #7dd3fc;
}}
QPushButton:pressed {{
    background-color: #0ea5e9;
}}
QPushButton:disabled {{
    background-color: {PALETTE['border']};
    color: {PALETTE['text_dim']};
}}
QPushButton#btn_danger {{
    background-color: {PALETTE['error']};
    color: white;
}}
QPushButton#btn_secondary {{
    background-color: {PALETTE['bg_card']};
    color: {PALETTE['text']};
    border: 1px solid {PALETTE['border']};
}}
QPushButton#btn_secondary:hover {{
    background-color: #334155;
}}
QPushButton#btn_success {{
    background-color: {PALETTE['success']};
    color: #0f172a;
}}
QLineEdit, QSpinBox, QComboBox {{
    background-color: {PALETTE['bg_input']};
    color: {PALETTE['text']};
    border: 1px solid {PALETTE['border']};
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {PALETTE['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {PALETTE['bg_card']};
    color: {PALETTE['text']};
    selection-background-color: {PALETTE['accent']};
    selection-color: #0f172a;
}}
QGroupBox {{
    border: 1px solid {PALETTE['border']};
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px;
    font-weight: bold;
    color: {PALETTE['accent']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    background: {PALETTE['bg_dark']};
}}
QCheckBox {{
    color: {PALETTE['text']};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {PALETTE['border']};
    border-radius: 4px;
    background: {PALETTE['bg_input']};
}}
QCheckBox::indicator:checked {{
    background-color: {PALETTE['accent']};
    border-color: {PALETTE['accent']};
}}
QProgressBar {{
    border: 1px solid {PALETTE['border']};
    border-radius: 6px;
    background: {PALETTE['bg_input']};
    height: 18px;
    text-align: center;
    color: {PALETTE['text']};
    font-size: 11px;
}}
QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {PALETTE['accent']}, stop:1 {PALETTE['accent2']}
    );
    border-radius: 5px;
}}
QTextEdit {{
    background-color: #020617;
    color: #94a3b8;
    border: 1px solid {PALETTE['border']};
    border-radius: 6px;
    font-family: 'Consolas', 'JetBrains Mono', 'Courier New', monospace;
    font-size: 12px;
    padding: 6px;
}}
QTableWidget {{
    background-color: {PALETTE['bg_card']};
    gridline-color: {PALETTE['border']};
    border: 1px solid {PALETTE['border']};
    border-radius: 6px;
    color: {PALETTE['text']};
}}
QTableWidget::item {{
    padding: 6px 10px;
}}
QTableWidget::item:selected {{
    background-color: #1e3a5f;
    color: {PALETTE['text']};
}}
QHeaderView::section {{
    background-color: #0f172a;
    color: {PALETTE['accent']};
    padding: 8px;
    border: none;
    border-right: 1px solid {PALETTE['border']};
    font-weight: bold;
}}
QScrollBar:vertical {{
    background: {PALETTE['bg_dark']};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {PALETTE['border']};
    border-radius: 4px;
    min-height: 20px;
}}
QStatusBar {{
    background-color: {PALETTE['bg_card']};
    color: {PALETTE['text_dim']};
    border-top: 1px solid {PALETTE['border']};
}}
QSlider::groove:horizontal {{
    height: 6px;
    background: {PALETTE['border']};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {PALETTE['accent']};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background: {PALETTE['accent']};
    border-radius: 3px;
}}
"""

# ─── Worker Thread ────────────────────────────────────────────────────────────

class PipelineWorker(QThread):
    """Thread terpisah untuk menjalankan pipeline tanpa membekukan GUI."""

    log_signal          = pyqtSignal(str)        # Pesan log
    progress_signal     = pyqtSignal(int, str)   # (persen, label tahap)
    stage_signal        = pyqtSignal(str)        # Nama tahap aktif
    finished_signal     = pyqtSignal(dict)       # Hasil pipeline
    error_signal        = pyqtSignal(str)        # Pesan error fatal

    def __init__(
        self,
        video_path: str,
        settings: dict,
        parent=None,
    ):
        super().__init__(parent)
        self.video_path = Path(video_path)
        self.settings   = settings
        self._stop      = False

    def stop(self):
        self._stop = True
        self.terminate()

    def _emit_log(self, msg: str):
        self.log_signal.emit(msg)

    def run(self):
        """Jalankan pipeline sepenuhnya di thread terpisah."""
        try:
            self._run_pipeline()
        except Exception as e:
            self.error_signal.emit(str(e))

    def _run_pipeline(self):
        import json
        import time

        # Import modul di sini agar path sudah benar
        sys.path.insert(0, str(PROJECT_DIR))
        from metadata_extractor import extract_metadata, save_metadata
        from upscaler import upscale_video, ensure_realesrgan_binary
        from compressor import Compressor
        from quality_analyzer import QualityAnalyzer, ReportGenerator

        stem     = self.video_path.stem
        settings = self.settings
        results  = {
            "input_video": str(self.video_path),
            "stem": stem,
            "metadata": None,
            "upscaling": {},
            "compression": {},
            "quality": [],
            "report_paths": {},
            "errors": [],
        }

        def log(msg):
            self._emit_log(msg)

        # ── Tahap 1: Metadata ─────────────────────────────────────────────────
        self.stage_signal.emit("metadata")
        self.progress_signal.emit(5, "Mengekstrak metadata...")
        log("Memeriksa tahap metadata...")
        self.progress_signal.emit(5, "Mengekstrak metadata...")
        log("==> Tahap 1: Ekstraksi Metadata")
        try:
            metadata = extract_metadata(self.video_path)
            results["metadata"] = metadata
            save_metadata(metadata, REPORTS_DIR / f"{stem}_metadata.json")
            v = metadata["video"]
            log(f"  [OK] Resolusi: {v['width']}x{v['height']} @ {v['fps']}fps")
            log(f"  [OK] Codec   : {v['codec']} | Durasi: {metadata['duration_str']}")
            log(f"  [OK] Ukuran  : {metadata['file_size_mb']} MB")
        except Exception as e:
            log(f"  [ERR] Metadata gagal: {e}")
            results["errors"].append(str(e))

        if self._stop:
            return

        # ── Tahap 2: Upscaling ────────────────────────────────────────────────
        self.stage_signal.emit("upscaling")
        self.progress_signal.emit(15, "Memulai AI Upscaling...")
        log("\n==> Tahap 2: AI Upscaling")

        upscaled_esrgan  = None
        upscaled_bicubic = None

        if settings.get("use_realesrgan", True):
            # Download binary jika belum ada
            log("  --> Memeriksa binary Real-ESRGAN...")
            binary = ensure_realesrgan_binary(callback=log)
            if not binary:
                log("  [!] Binary Real-ESRGAN tidak tersedia / tidak executable.")
                log("      Download manual dari: https://github.com/xinntao/Real-ESRGAN/releases")
                log("      Letakkan di: tools/realesrgan-ncnn-vulkan")
                results["errors"].append("ESRGAN: Binary tidak tersedia")
            else:
                log(f"  --> Binary ditemukan: {binary}")
                log("  --> Real-ESRGAN upscaling (proses ini memerlukan waktu)...")
                self.progress_signal.emit(20, "Real-ESRGAN upscaling...")
                try:
                    t0 = time.time()
                    upscaled_esrgan = upscale_video(
                        self.video_path,
                        method="realesrgan",
                        callback=log,
                    )
                    elapsed = round(time.time() - t0, 1)
                    log(f"  [OK] ESRGAN selesai: {upscaled_esrgan.name} ({elapsed}s)")
                    results["upscaling"]["realesrgan"] = str(upscaled_esrgan)
                except Exception as e:
                    log(f"  [ERR] Real-ESRGAN gagal: {e}")
                    results["errors"].append(f"ESRGAN: {e}")

        if self._stop:
            return

        if settings.get("use_bicubic", True):
            log("  --> Bicubic upscaling (baseline comparison)...")
            self.progress_signal.emit(45, "Bicubic upscaling...")
            try:
                t0 = time.time()
                upscaled_bicubic = upscale_video(
                    self.video_path,
                    method="bicubic",
                    callback=log,
                )
                elapsed = round(time.time() - t0, 1)
                log(f"  [OK] Bicubic selesai: {upscaled_bicubic.name} ({elapsed}s)")
                results["upscaling"]["bicubic"] = str(upscaled_bicubic)
            except Exception as e:
                log(f"  [ERR] Bicubic gagal: {e}")
                results["errors"].append(f"Bicubic: {e}")

        if self._stop:
            return

        # ── Tahap 3: Kompresi HEVC ────────────────────────────────────────────
        self.stage_signal.emit("compression")
        self.progress_signal.emit(60, "Kompresi HEVC...")
        log("\n==> Tahap 3: Rekompresi HEVC")

        comp   = Compressor(callback=log)
        source = upscaled_esrgan or upscaled_bicubic or self.video_path

        crf_values = settings.get("crf_values", HEVC_CONFIG["crf_values"])
        for i, crf in enumerate(crf_values):
            if self._stop:
                return
            self.progress_signal.emit(
                60 + int(10 * (i + 1) / len(crf_values)),
                f"Kompresi CRF {crf}..."
            )
            try:
                out = comp.compress(source, crf)
                results["compression"][f"crf{crf}"] = str(out)
            except Exception as e:
                log(f"  ✗ CRF {crf} gagal: {e}")
                results["errors"].append(f"CRF{crf}: {e}")

        if self._stop:
            return

        # ── Tahap 4: Analisis Kualitas ────────────────────────────────────────
        if settings.get("enable_vmaf", True):
            self.stage_signal.emit("quality")
            self.progress_signal.emit(75, "Analisis VMAF / PSNR / SSIM...")
            log("\n==> Tahap 4: Analisis Kualitas VMAF")

            analyzer      = QualityAnalyzer(callback=log)
            quality_list  = []
            ref_video     = upscaled_esrgan or upscaled_bicubic

            if ref_video:
                comp_items = list(results["compression"].items())
                for idx, (crf_key, comp_path) in enumerate(comp_items):
                    if self._stop:
                        return
                    self.progress_signal.emit(
                        75 + int(10 * (idx + 1) / max(len(comp_items), 1)),
                        f"VMAF untuk {crf_key}..."
                    )
                    try:
                        r = analyzer.analyze(
                            ref_video, Path(comp_path),
                            label=f"{stem}_{crf_key}",
                        )
                        quality_list.append(r)
                    except Exception as e:
                        log(f"  ✗ VMAF {crf_key}: {e}")
                        results["errors"].append(f"VMAF {crf_key}: {e}")

                if upscaled_esrgan and upscaled_bicubic:
                    try:
                        r = analyzer.analyze(
                            upscaled_esrgan, upscaled_bicubic,
                            label=f"{stem}_bicubic_vs_esrgan",
                        )
                        quality_list.append(r)
                    except Exception as e:
                        log(f"  ✗ ESRGAN vs Bicubic: {e}")
            else:
                log("  ⚠ Tidak ada referensi untuk VMAF, dilewati.")

            results["quality"] = quality_list
        else:
            log("\n[SKIP] Tahap 4: VMAF dilewati (sesuai pengaturan)")

        # ── Tahap 5: Laporan ──────────────────────────────────────────────────
        self.stage_signal.emit("report")
        self.progress_signal.emit(90, "Generate laporan...")
        log("\n==> Tahap 5: Generate Laporan")
        try:
            if results["quality"]:
                gen = ReportGenerator()
                rp  = gen.generate(results["quality"], stem=stem)
                results["report_paths"] = {k: str(v) for k, v in rp.items()}
                for fmt, path in rp.items():
                    log(f"  ✓ {fmt.upper()}: {path}")

            pipeline_json = REPORTS_DIR / f"{stem}_pipeline_results.json"
            with open(pipeline_json, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            log(f"  ✓ Pipeline JSON: {pipeline_json}")
        except Exception as e:
            log(f"  ✗ Laporan gagal: {e}")
            results["errors"].append(f"Report: {e}")

        self.progress_signal.emit(100, "Selesai!")
        self.stage_signal.emit("done")
        log("\n[DONE] Pipeline selesai!")
        if results["errors"]:
            log(f"  [!] {len(results['errors'])} error: {results['errors']}")
        self.finished_signal.emit(results)


# ─── Widget Pembantu ──────────────────────────────────────────────────────────

class SectionLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            f"color: {PALETTE['accent']}; font-size: 12px; font-weight: bold; "
            f"margin-top: 6px; margin-bottom: 2px;"
        )


class MetadataCard(QFrame):
    """Kartu menampilkan metadata video."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MetadataCard")
        self.setStyleSheet(
            "#MetadataCard { "
            f"background-color: {PALETTE['bg_card']}; "
            f"border: 1px solid {PALETTE['border']}; "
            "border-radius: 10px; "
            "}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(6)
        self._layout = outer
        self._rows: dict[str, QLabel] = {}
        self._init_rows()

    def _row(self, key: str, label: str):
        row = QHBoxLayout()
        lbl = QLabel(label + ":")
        lbl.setFixedWidth(120)
        lbl.setStyleSheet(
            f"color: {PALETTE['text_dim']}; "
            f"background: transparent; border: none;"
        )
        val = QLabel("–")
        val.setStyleSheet(
            f"color: {PALETTE['text']}; font-weight: bold; "
            f"background: transparent; border: none;"
        )
        val.setWordWrap(True)
        row.addWidget(lbl)
        row.addWidget(val, 1)
        self._layout.addLayout(row)
        self._rows[key] = val

    def _init_rows(self):
        self._row("file",     "File")
        self._row("size",     "Ukuran")
        self._row("res",      "Resolusi")
        self._row("fps",      "FPS")
        self._row("codec",    "Codec")
        self._row("duration", "Durasi")
        self._row("bitrate",  "Bitrate")
        self._row("audio",    "Audio")

    def update_metadata(self, meta: dict):
        v = meta.get("video", {})
        a = meta.get("audio") or {}
        self._rows["file"].setText(meta.get("file_name", "–"))
        self._rows["size"].setText(f"{meta.get('file_size_mb', 0)} MB")
        self._rows["res"].setText(v.get("resolution", "–"))
        self._rows["fps"].setText(str(v.get("fps", "–")))
        self._rows["codec"].setText(v.get("codec_long", v.get("codec", "–")))
        self._rows["duration"].setText(meta.get("duration_str", "–"))
        self._rows["bitrate"].setText(f"{meta.get('bitrate_kbps', 0)} kbps")
        self._rows["audio"].setText(
            f"{a.get('codec', 'N/A')} | {a.get('sample_rate', '?')} Hz | "
            f"{a.get('channels', '?')}ch"
            if a else "Tidak ada audio"
        )

    def clear(self):
        for lbl in self._rows.values():
            lbl.setText("–")


# ─── Tab Input ────────────────────────────────────────────────────────────────

class InputTab(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Judul
        title = QLabel("Pilih Video Input SD")
        title.setStyleSheet(
            f"color: {PALETTE['accent']}; font-size: 18px; font-weight: bold;"
        )
        layout.addWidget(title)

        sub = QLabel("Pilih file video resolusi standar (SD) yang akan di-upscale ke HD.")
        sub.setStyleSheet(f"color: {PALETTE['text_dim']};")
        layout.addWidget(sub)

        # Drop area / file picker
        drop_frame = QFrame()
        drop_frame.setStyleSheet(
            f"QFrame {{ background: {PALETTE['bg_card']}; "
            f"border: 2px dashed {PALETTE['border']}; "
            f"border-radius: 12px; min-height: 100px; }}"
        )
        drop_layout = QVBoxLayout(drop_frame)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        drop_icon = QLabel("[ VIDEO ]")
        drop_icon.setFont(QFont("", 18))
        drop_icon.setStyleSheet(
            f"color: {PALETTE['accent']}; font-weight: bold; "
            f"border: 2px solid {PALETTE['border']}; border-radius: 8px; padding: 10px 20px;"
        )
        drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(drop_icon)

        drop_text = QLabel("Klik tombol di bawah untuk memilih file video")
        drop_text.setStyleSheet(f"color: {PALETTE['text_dim']}; font-size: 13px;")
        drop_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(drop_text)

        layout.addWidget(drop_frame)

        # Input path
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Path file video atau klik Browse...")
        self.path_edit.setReadOnly(False)
        path_row.addWidget(self.path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(120)
        browse_btn.clicked.connect(self._browse_file)
        path_row.addWidget(browse_btn)

        clear_btn = QPushButton("X")
        clear_btn.setObjectName("btn_secondary")
        clear_btn.setFixedWidth(40)
        clear_btn.clicked.connect(self._clear_file)
        path_row.addWidget(clear_btn)

        layout.addLayout(path_row)

        # Format yang didukung
        fmt_label = QLabel(
            "Format didukung: " +
            ", ".join(sorted(SUPPORTED_VIDEO_EXTENSIONS))
        )
        fmt_label.setStyleSheet(f"color: {PALETTE['text_dim']}; font-size: 11px;")
        layout.addWidget(fmt_label)

        # Metadata card
        layout.addWidget(SectionLabel("Informasi Video"))
        self.meta_card = MetadataCard()
        layout.addWidget(self.meta_card)

        layout.addStretch()

        # Tombol Analisis Metadata saja
        self.meta_btn = QPushButton("[ Ekstrak Metadata ]")
        self.meta_btn.setObjectName("btn_secondary")
        self.meta_btn.clicked.connect(self._extract_metadata)
        self.meta_btn.setFixedHeight(38)
        layout.addWidget(self.meta_btn)

    def _browse_file(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_VIDEO_EXTENSIONS)
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Video SD",
            str(INPUT_DIR),
            f"Video Files ({exts});;All Files (*)",
        )
        if path:
            self.path_edit.setText(path)
            self.file_selected.emit(path)
            self._extract_metadata()

    def _clear_file(self):
        self.path_edit.clear()
        self.meta_card.clear()

    def _extract_metadata(self):
        path = self.path_edit.text().strip()
        if not path or not Path(path).exists():
            return
        try:
            from metadata_extractor import extract_metadata
            meta = extract_metadata(path)
            self.meta_card.update_metadata(meta)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Gagal membaca metadata:\n{e}")

    def get_video_path(self) -> str:
        return self.path_edit.text().strip()


# ─── Tab Pengaturan ───────────────────────────────────────────────────────────

class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        layout    = QVBoxLayout(container)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        # ── Metode Upscaling ──────────────────────────────────────────────────
        box_up = QGroupBox("🚀 Metode Upscaling")
        box_up_layout = QVBoxLayout(box_up)

        self.cb_realesrgan = QCheckBox("Real-ESRGAN (AI Upscaling – kualitas terbaik)")
        self.cb_realesrgan.setChecked(True)
        box_up_layout.addWidget(self.cb_realesrgan)

        self.cb_bicubic = QCheckBox("Bicubic (Baseline perbandingan – cepat)")
        self.cb_bicubic.setChecked(True)
        box_up_layout.addWidget(self.cb_bicubic)

        # Model Real-ESRGAN
        box_up_layout.addWidget(SectionLabel("Model Real-ESRGAN"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "RealESRGAN_x4plus",
            "RealESRGANv2-animevideo-xsx2",
            "realesrnet-x4plus",
            "RealESRGAN_x4plus_anime_6B",
        ])
        box_up_layout.addWidget(self.model_combo)

        # GPU settings
        gpu_row = QHBoxLayout()
        self.cb_use_gpu = QCheckBox("Gunakan GPU (Vulkan)")
        self.cb_use_gpu.setChecked(REALESRGAN_CONFIG.get("use_gpu", True))
        gpu_row.addWidget(self.cb_use_gpu)
        gpu_row.addStretch()
        gpu_id_lbl = QLabel("GPU ID:")
        gpu_id_lbl.setStyleSheet(f"color: {PALETTE['text_dim']};")
        gpu_row.addWidget(gpu_id_lbl)
        self.gpu_spin = QSpinBox()
        self.gpu_spin.setRange(0, 7)
        self.gpu_spin.setValue(REALESRGAN_CONFIG.get("gpu_id", 1))
        self.gpu_spin.setFixedWidth(60)
        gpu_row.addWidget(self.gpu_spin)
        box_up_layout.addLayout(gpu_row)

        # Tile size
        tile_row = QHBoxLayout()
        tile_lbl = QLabel("Tile Size (0=auto, 128/256 untuk VRAM rendah):")
        tile_lbl.setStyleSheet(f"color: {PALETTE['text_dim']};")
        tile_row.addWidget(tile_lbl)
        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(0, 512)
        self.tile_spin.setValue(0)
        self.tile_spin.setSingleStep(64)
        self.tile_spin.setFixedWidth(80)
        tile_row.addWidget(self.tile_spin)
        box_up_layout.addLayout(tile_row)

        layout.addWidget(box_up)

        # ── Resolusi Output ───────────────────────────────────────────────────
        box_res = QGroupBox("🖥️ Resolusi Output")
        box_res_layout = QHBoxLayout(box_res)
        w_lbl = QLabel("Lebar:")
        w_lbl.setStyleSheet(f"color: {PALETTE['text_dim']};")
        self.width_spin = QSpinBox()
        self.width_spin.setRange(480, 7680)
        self.width_spin.setValue(TARGET_WIDTH)
        self.width_spin.setSingleStep(2)

        h_lbl = QLabel("Tinggi:")
        h_lbl.setStyleSheet(f"color: {PALETTE['text_dim']};")
        self.height_spin = QSpinBox()
        self.height_spin.setRange(270, 4320)
        self.height_spin.setValue(TARGET_HEIGHT)
        self.height_spin.setSingleStep(2)

        preset_res = QComboBox()
        preset_res.addItems(["1920×1080 (FHD)", "1280×720 (HD)", "3840×2160 (4K)"])
        preset_res.currentIndexChanged.connect(self._apply_preset_res)

        box_res_layout.addWidget(w_lbl)
        box_res_layout.addWidget(self.width_spin)
        box_res_layout.addWidget(h_lbl)
        box_res_layout.addWidget(self.height_spin)
        box_res_layout.addWidget(QLabel("  Preset:"))
        box_res_layout.addWidget(preset_res)
        box_res_layout.addStretch()
        layout.addWidget(box_res)

        # ── Kompresi HEVC ─────────────────────────────────────────────────────
        box_hevc = QGroupBox("💾 Kompresi HEVC/H.265")
        box_hevc_layout = QVBoxLayout(box_hevc)

        # CRF checkboxes
        crf_row = QHBoxLayout()
        crf_row.addWidget(SectionLabel("Nilai CRF:"))
        self.crf_checks = {}
        for crf in [18, 23, 28]:
            cb = QCheckBox(str(crf))
            cb.setChecked(crf in HEVC_CONFIG["crf_values"])
            self.crf_checks[crf] = cb
            crf_row.addWidget(cb)
        crf_row.addStretch()
        box_hevc_layout.addLayout(crf_row)

        # Preset encode
        preset_row = QHBoxLayout()
        preset_lbl = QLabel("Preset Encode:")
        preset_lbl.setStyleSheet(f"color: {PALETTE['text_dim']};")
        self.encode_preset = QComboBox()
        self.encode_preset.addItems(
            ["ultrafast", "superfast", "veryfast", "faster", "fast",
             "medium", "slow", "slower", "veryslow"]
        )
        self.encode_preset.setCurrentText(HEVC_CONFIG.get("preset", "medium"))
        preset_row.addWidget(preset_lbl)
        preset_row.addWidget(self.encode_preset)
        preset_row.addStretch()
        box_hevc_layout.addLayout(preset_row)

        layout.addWidget(box_hevc)

        # ── Analisis Kualitas ─────────────────────────────────────────────────
        box_qa = QGroupBox("📊 Analisis Kualitas")
        box_qa_layout = QVBoxLayout(box_qa)

        self.cb_vmaf = QCheckBox("Aktifkan VMAF (butuh libvmaf dalam FFmpeg)")
        self.cb_vmaf.setChecked(QUALITY_CONFIG.get("enable_vmaf", True))
        box_qa_layout.addWidget(self.cb_vmaf)

        self.cb_psnr = QCheckBox("Aktifkan PSNR")
        self.cb_psnr.setChecked(QUALITY_CONFIG.get("enable_psnr", True))
        box_qa_layout.addWidget(self.cb_psnr)

        self.cb_ssim = QCheckBox("Aktifkan SSIM")
        self.cb_ssim.setChecked(True)
        box_qa_layout.addWidget(self.cb_ssim)

        sub_row = QHBoxLayout()
        sub_lbl = QLabel("VMAF Subsample (1=semua frame, lebih besar=lebih cepat):")
        sub_lbl.setStyleSheet(f"color: {PALETTE['text_dim']};")
        self.subsample_spin = QSpinBox()
        self.subsample_spin.setRange(1, 25)
        self.subsample_spin.setValue(QUALITY_CONFIG.get("vmaf_subsample", 1))
        sub_row.addWidget(sub_lbl)
        sub_row.addWidget(self.subsample_spin)
        sub_row.addStretch()
        box_qa_layout.addLayout(sub_row)

        layout.addWidget(box_qa)

        layout.addStretch()

    def _apply_preset_res(self, idx):
        presets = [(1920, 1080), (1280, 720), (3840, 2160)]
        if idx < len(presets):
            self.width_spin.setValue(presets[idx][0])
            self.height_spin.setValue(presets[idx][1])

    def get_settings(self) -> dict:
        """Kembalikan dict pengaturan saat ini."""
        crf_values = [crf for crf, cb in self.crf_checks.items() if cb.isChecked()]
        return {
            "use_realesrgan": self.cb_realesrgan.isChecked(),
            "use_bicubic":    self.cb_bicubic.isChecked(),
            "model_name":     self.model_combo.currentText(),
            "use_gpu":        self.cb_use_gpu.isChecked(),
            "gpu_id":         self.gpu_spin.value(),
            "tile_size":      self.tile_spin.value(),
            "target_width":   self.width_spin.value(),
            "target_height":  self.height_spin.value(),
            "crf_values":     crf_values or [23],
            "encode_preset":  self.encode_preset.currentText(),
            "enable_vmaf":    self.cb_vmaf.isChecked(),
            "enable_psnr":    self.cb_psnr.isChecked(),
            "enable_ssim":    self.cb_ssim.isChecked(),
            "vmaf_subsample": self.subsample_spin.value(),
        }


# ─── Tab Progress ─────────────────────────────────────────────────────────────

class ProgressTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Stage indicators
        stages_box = QGroupBox("Tahapan Pipeline")
        stages_layout = QHBoxLayout(stages_box)
        stages_layout.setSpacing(4)

        self._stage_labels: dict[str, QLabel] = {}
        stages = [
            ("metadata",    "1. Metadata"),
            ("upscaling",   "2. Upscaling"),
            ("compression", "3. Kompresi"),
            ("quality",     "4. VMAF"),
            ("report",      "5. Laporan"),
        ]
        for key, text in stages:
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setMinimumWidth(90)
            lbl.setStyleSheet(
                f"background: {PALETTE['bg_input']}; "
                f"border: 1px solid {PALETTE['border']}; "
                f"border-radius: 6px; padding: 8px 4px; "
                f"color: {PALETTE['text_dim']}; font-size: 11px;"
            )
            self._stage_labels[key] = lbl
            stages_layout.addWidget(lbl)

        layout.addWidget(stages_box)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(22)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("Siap untuk memulai...")
        self.progress_label.setStyleSheet(f"color: {PALETTE['text_dim']}; font-size: 12px;")
        layout.addWidget(self.progress_label)

        # Log output
        layout.addWidget(SectionLabel("Log Real-Time"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(320)
        layout.addWidget(self.log_text, 1)

        # Tombol kontrol
        btn_row = QHBoxLayout()
        self.clear_log_btn = QPushButton("Bersihkan Log")
        self.clear_log_btn.setObjectName("btn_secondary")
        self.clear_log_btn.clicked.connect(self.log_text.clear)
        btn_row.addWidget(self.clear_log_btn)

        self.save_log_btn = QPushButton("Simpan Log")
        self.save_log_btn.setObjectName("btn_secondary")
        self.save_log_btn.clicked.connect(self._save_log)
        btn_row.addWidget(self.save_log_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def append_log(self, msg: str):
        """Tambah pesan ke area log dengan warna (HTML-safe)."""
        import html as _html

        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

        # Warna berdasarkan konten
        color = PALETTE["text_dim"]
        msg_lower = msg.lower()
        if any(x in msg for x in ["✓", "✅"]) or any(x in msg_lower for x in ["selesai", "berhasil"]):
            color = PALETTE["success"]
        elif any(x in msg for x in ["✗", "❌"]) or any(x in msg_lower for x in ["gagal", "error", "permission denied"]):
            color = PALETTE["error"]
        elif any(x in msg for x in ["⚠"]) or "warning" in msg_lower:
            color = PALETTE["warning"]
        elif any(x in msg for x in ["→", "Tahap", "Mengekstrak", "Mengunduh",
                                      "Menjalankan", "Menggabungkan"]):
            color = PALETTE["accent"]

        # Escape HTML entities agar path/karakter khusus tidak merusak rendering
        safe_msg = _html.escape(msg)
        self.log_text.insertHtml(
            f'<span style="color:{color}; font-family:monospace;">{safe_msg}</span><br>'
        )
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def update_progress(self, value: int, label: str):
        self.progress_bar.setValue(value)
        self.progress_label.setText(label)

    def set_active_stage(self, stage_key: str):
        """Tandai tahap aktif."""
        done_stages = {
            "metadata":    [],
            "upscaling":   ["metadata"],
            "compression": ["metadata", "upscaling"],
            "quality":     ["metadata", "upscaling", "compression"],
            "report":      ["metadata", "upscaling", "compression", "quality"],
            "done":        ["metadata", "upscaling", "compression", "quality", "report"],
        }
        completed = done_stages.get(stage_key, [])

        text_map = {
            "metadata":    "1. Metadata",
            "upscaling":   "2. Upscaling",
            "compression": "3. Kompresi",
            "quality":     "4. VMAF",
            "report":      "5. Laporan",
        }
        for key, lbl in self._stage_labels.items():
            text = text_map.get(key, key)
            if key in completed:
                lbl.setText(f"[OK] {text}")
                lbl.setStyleSheet(
                    f"background: #14532d; border: 1px solid {PALETTE['success']}; "
                    f"border-radius: 6px; padding: 8px 4px; "
                    f"color: {PALETTE['success']}; font-size: 11px; font-weight: bold;"
                )
            elif key == stage_key:
                lbl.setText(f"[>>] {text}")
                lbl.setStyleSheet(
                    f"background: #1e3a5f; border: 2px solid {PALETTE['accent']}; "
                    f"border-radius: 6px; padding: 8px 4px; "
                    f"color: {PALETTE['accent']}; font-size: 11px; font-weight: bold;"
                )
            else:
                lbl.setText(text)
                lbl.setStyleSheet(
                    f"background: {PALETTE['bg_input']}; "
                    f"border: 1px solid {PALETTE['border']}; "
                    f"border-radius: 6px; padding: 8px 4px; "
                    f"color: {PALETTE['text_dim']}; font-size: 11px;"
                )

    def reset(self):
        self.progress_bar.setValue(0)
        self.progress_label.setText("Siap untuk memulai...")
        text_map = {
            "metadata":    "1. Metadata",
            "upscaling":   "2. Upscaling",
            "compression": "3. Kompresi",
            "quality":     "4. VMAF",
            "report":      "5. Laporan",
        }
        for key, lbl in self._stage_labels.items():
            lbl.setText(text_map.get(key, key))
            lbl.setStyleSheet(
                f"background: {PALETTE['bg_input']}; "
                f"border: 1px solid {PALETTE['border']}; "
                f"border-radius: 6px; padding: 8px 4px; "
                f"color: {PALETTE['text_dim']}; font-size: 11px;"
            )

    def _save_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Log", str(REPORTS_DIR / "pipeline.log"),
            "Log Files (*.log *.txt);;All Files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_text.toPlainText())


# ─── Tab Hasil ────────────────────────────────────────────────────────────────

class ResultsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._results: dict = {}

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Hasil Analisis Kualitas")
        title.setStyleSheet(
            f"color: {PALETTE['accent']}; font-size: 18px; font-weight: bold;"
        )
        layout.addWidget(title)

        # Tabel hasil kualitas
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Label", "VMAF", "Grade", "PSNR (dB)", "SSIM",
            "Rasio Kompresi", "Ref (MB)", "Dist (MB)",
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        layout.addWidget(self.table, 1)

        # Output files
        layout.addWidget(SectionLabel("File Output"))
        self.files_text = QTextEdit()
        self.files_text.setReadOnly(True)
        self.files_text.setMaximumHeight(140)
        self.files_text.setStyleSheet(
            f"background: {PALETTE['bg_card']}; "
            f"border: 1px solid {PALETTE['border']}; "
            f"border-radius: 6px; font-size: 12px; color: {PALETTE['text']};"
        )
        layout.addWidget(self.files_text)

        # Action buttons
        btn_row = QHBoxLayout()
        self.open_output_btn = QPushButton("Buka Folder Output")
        self.open_output_btn.clicked.connect(self._open_output_folder)
        btn_row.addWidget(self.open_output_btn)

        self.open_report_btn = QPushButton("Buka Laporan HTML")
        self.open_report_btn.setObjectName("btn_secondary")
        self.open_report_btn.clicked.connect(self._open_html_report)
        btn_row.addWidget(self.open_report_btn)

        self.open_reports_btn = QPushButton("Buka Folder Reports")
        self.open_reports_btn.setObjectName("btn_secondary")
        self.open_reports_btn.clicked.connect(self._open_reports_folder)
        btn_row.addWidget(self.open_reports_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ─── Grade badge color ────────────────────────────────────────────────────

    @staticmethod
    def _grade_color(grade: str) -> tuple[str, str]:
        """(bg_color, text_color) berdasarkan grade."""
        return {
            "Excellent": ("#14532d", "#4ade80"),
            "Good":      ("#1e3a5f", "#38bdf8"),
            "Fair":      ("#3d2f00", "#facc15"),
            "Poor":      ("#450a0a", "#f87171"),
        }.get(grade, (PALETTE["bg_card"], PALETTE["text"]))

    def update_results(self, pipeline_results: dict):
        self._results = pipeline_results
        quality_list  = pipeline_results.get("quality", [])

        # Isi tabel
        self.table.setRowCount(0)
        for row_idx, r in enumerate(quality_list):
            self.table.insertRow(row_idx)

            def _item(val, center=True):
                item = QTableWidgetItem(str(val) if val is not None else "N/A")
                if center:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                return item

            grade       = r.get("vmaf_grade") or "N/A"
            bg, fg      = self._grade_color(grade)

            grade_item   = QTableWidgetItem(grade)
            grade_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            grade_item.setBackground(QColor(bg))
            grade_item.setForeground(QColor(fg))

            self.table.setItem(row_idx, 0, _item(r.get("label", ""), center=False))
            self.table.setItem(row_idx, 1, _item(r.get("vmaf")))
            self.table.setItem(row_idx, 2, grade_item)
            self.table.setItem(row_idx, 3, _item(r.get("psnr")))
            self.table.setItem(row_idx, 4, _item(r.get("ssim")))
            self.table.setItem(row_idx, 5, _item(r.get("compression_ratio")))
            self.table.setItem(row_idx, 6, _item(r.get("file_size_ref_mb")))
            self.table.setItem(row_idx, 7, _item(r.get("file_size_dist_mb")))

        # File output list
        lines = []
        for method, path in pipeline_results.get("upscaling", {}).items():
            lines.append(f"[Upscaled {method.upper()}]  {path}")
        for crf_key, path in pipeline_results.get("compression", {}).items():
            lines.append(f"[HEVC {crf_key}]             {path}")
        for fmt, path in pipeline_results.get("report_paths", {}).items():
            lines.append(f"[Report {fmt.upper()}]        {path}")

        self.files_text.setPlainText("\n".join(lines) if lines else "Tidak ada output")

    def _open_output_folder(self):
        subprocess.Popen(["xdg-open", str(OUTPUT_DIR)])

    def _open_reports_folder(self):
        subprocess.Popen(["xdg-open", str(REPORTS_DIR)])

    def _open_html_report(self):
        html = self._results.get("report_paths", {}).get("html")
        if html and Path(html).exists():
            subprocess.Popen(["xdg-open", html])
        else:
            # Cari laporan HTML terbaru
            htmls = sorted(REPORTS_DIR.glob("*_quality_report.html"), key=os.path.getmtime, reverse=True)
            if htmls:
                subprocess.Popen(["xdg-open", str(htmls[0])])
            else:
                QMessageBox.information(self, "Info", "Belum ada laporan HTML yang dihasilkan.")


# ─── Window Utama ─────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._worker: PipelineWorker | None = None
        self._is_running = False
        self._setup_window()
        self._build_ui()

    def _setup_window(self):
        self.setWindowTitle("🎬 AI Video Upscaling Pipeline")
        self.setMinimumSize(1000, 720)
        self.resize(1200, 800)
        self.setStyleSheet(STYLESHEET)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet(
            f"background: {PALETTE['bg_card']}; "
            f"border-bottom: 1px solid {PALETTE['border']};"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 20, 0)

        logo = QLabel("[ AI ]")
        logo.setFont(QFont("", 16))
        logo.setStyleSheet(
            f"color: {PALETTE['accent']}; font-weight: bold; "
            f"border: 2px solid {PALETTE['accent']}; border-radius: 6px; padding: 4px 8px;"
        )
        h_layout.addWidget(logo)

        title_group = QVBoxLayout()
        title_group.setSpacing(0)
        app_title = QLabel("AI Video Upscaling Pipeline")
        app_title.setStyleSheet(
            f"color: {PALETTE['accent']}; font-size: 18px; font-weight: bold;"
        )
        title_group.addWidget(app_title)
        app_sub = QLabel("Restorasi Video SD → HD | Real-ESRGAN + HEVC + VMAF")
        app_sub.setStyleSheet(f"color: {PALETTE['text_dim']}; font-size: 11px;")
        title_group.addWidget(app_sub)

        h_layout.addLayout(title_group)
        h_layout.addStretch()

        # Tombol Mulai / Stop di header
        self.run_btn = QPushButton("▶  Mulai Pipeline")
        self.run_btn.setFixedSize(160, 40)
        self.run_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #cbd5e1;"
            "    color: #0f172a;"
            "    border: none;"
            "    border-radius: 7px;"
            "    font-weight: bold;"
            "    font-size: 13px;"
            "}"
            "QPushButton:hover { background-color: #e2e8f0; }"
            "QPushButton:pressed { background-color: #cbd5e1; }"
            "QPushButton:disabled { background-color: #334155; color: #64748b; }"
        )
        self.run_btn.clicked.connect(self._start_pipeline)
        h_layout.addWidget(self.run_btn)

        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setFixedSize(100, 40)
        self.stop_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #ffffff;"
            "    color: #b91c1c;"
            "    border: 2px solid #f87171;"
            "    border-radius: 7px;"
            "    font-weight: bold;"
            "    font-size: 13px;"
            "}"
            "QPushButton:hover { background-color: #fee2e2; }"
            "QPushButton:pressed { background-color: #fecaca; }"
            "QPushButton:disabled { background-color: #334155; color: #64748b; border: none; }"
        )
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_pipeline)
        h_layout.addWidget(self.stop_btn)

        root.addWidget(header)

        # ── Tabs ──────────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.tab_input    = InputTab()
        self.tab_settings = SettingsTab()
        self.tab_progress = ProgressTab()
        self.tab_results  = ResultsTab()

        self.tabs.addTab(self.tab_input,    "[ Input Video ]")
        self.tabs.addTab(self.tab_settings, "[ Pengaturan ]")
        self.tabs.addTab(self.tab_progress, "[ Progress & Log ]")
        self.tabs.addTab(self.tab_results,  "[ Hasil ]")

        root.addWidget(self.tabs, 1)

        # ── Status Bar ────────────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Siap – Letakkan video SD di tab Input Video")

    # ─── Pipeline Control ─────────────────────────────────────────────────────

    def _start_pipeline(self):
        video_path = self.tab_input.get_video_path()
        if not video_path:
            QMessageBox.warning(self, "Perhatian",
                                "Pilih file video terlebih dahulu di tab 'Input Video'.")
            self.tabs.setCurrentIndex(0)
            return
        if not Path(video_path).exists():
            QMessageBox.critical(self, "Error",
                                 f"File tidak ditemukan:\n{video_path}")
            return

        settings = self.tab_settings.get_settings()
        if not settings["use_realesrgan"] and not settings["use_bicubic"]:
            QMessageBox.warning(self, "Perhatian",
                                "Pilih minimal satu metode upscaling.")
            self.tabs.setCurrentIndex(1)
            return

        # Update config berdasarkan settings
        from config import REALESRGAN_CONFIG as RC
        RC["model_name"] = settings["model_name"]
        RC["tile_size"]  = settings["tile_size"]
        RC["use_gpu"]    = settings["use_gpu"]
        RC["gpu_id"]     = settings["gpu_id"]

        # Pindah ke tab progress
        self.tabs.setCurrentIndex(2)
        self.tab_progress.reset()
        self.tab_progress.append_log(
            f"🚀 Memulai pipeline pada: {Path(video_path).name}"
        )
        self.tab_progress.append_log(
            f"   Pengaturan: ESRGAN={settings['use_realesrgan']} | "
            f"Bicubic={settings['use_bicubic']} | "
            f"CRF={settings['crf_values']} | VMAF={settings['enable_vmaf']}"
        )

        self._worker = PipelineWorker(video_path, settings, parent=self)
        self._worker.log_signal.connect(self.tab_progress.append_log)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.stage_signal.connect(self.tab_progress.set_active_stage)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.error_signal.connect(self._on_error)

        self._is_running = True
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_bar.showMessage("⏳ Pipeline sedang berjalan...")

        self._worker.start()

    def _stop_pipeline(self):
        if self._worker and self._worker.isRunning():
            reply = QMessageBox.question(
                self, "Konfirmasi",
                "Hentikan pipeline yang sedang berjalan?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._worker.stop()
                self.tab_progress.append_log("⏹ Pipeline dihentikan oleh pengguna.")
                self._reset_controls()

    def _on_progress(self, value: int, label: str):
        self.tab_progress.update_progress(value, label)
        self.status_bar.showMessage(f"⏳ {label} ({value}%)")

    def _on_finished(self, results: dict):
        self._reset_controls()
        self.tab_results.update_results(results)
        self.status_bar.showMessage(
            f"✅ Pipeline selesai! "
            f"{len(results.get('quality', []))} analisis kualitas."
        )

        errors = results.get("errors", [])
        if errors:
            self.tab_progress.append_log(
                f"\n⚠ {len(errors)} error terjadi:\n" +
                "\n".join(f"  • {e}" for e in errors)
            )

        # Pindah ke tab hasil
        QTimer.singleShot(800, lambda: self.tabs.setCurrentIndex(3))

        QMessageBox.information(
            self, "Pipeline Selesai",
            f"✅ Pemrosesan video selesai!\n\n"
            f"Video   : {Path(results['input_video']).name}\n"
            f"Output  : {len(results.get('upscaling', {}))} upscaled, "
            f"{len(results.get('compression', {}))} compressed\n"
            f"Kualitas: {len(results.get('quality', []))} analisis\n"
            f"Laporan : {', '.join(results.get('report_paths', {}).keys()) or 'tidak ada'}\n\n"
            f"Lihat detail di tab '📊 Hasil'."
        )

    def _on_error(self, message: str):
        self._reset_controls()
        self.tab_progress.append_log(f"\n❌ ERROR FATAL: {message}")
        self.status_bar.showMessage(f"❌ Error: {message[:80]}")
        QMessageBox.critical(self, "Error Pipeline", f"Terjadi error fatal:\n\n{message}")

    def _reset_controls(self):
        self._is_running = False
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def closeEvent(self, event):
        if self._is_running and self._worker:
            reply = QMessageBox.question(
                self, "Konfirmasi Keluar",
                "Pipeline masih berjalan. Yakin ingin keluar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self._worker.stop()
        event.accept()


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    os.chdir(PROJECT_DIR)
    app = QApplication(sys.argv)
    app.setApplicationName("AI Video Upscaling Pipeline")
    app.setOrganizationName("Research")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

