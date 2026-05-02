# AI Video Upscaling Pipeline

**Penerapan Algoritma AI Video Upscaling Berbasis Open-Source untuk Restorasi dan Rekompresi Video Resolusi Standar (SD) menjadi High Definition (HD)**

---

## 📋 Deskripsi Proyek

Pipeline otomatis untuk merestorasi video siaran lawas (SD) menjadi HD menggunakan teknologi AI (**Real-ESRGAN ncnn-vulkan**), kemudian melakukan rekompresi dengan codec **H.265/HEVC** untuk efisiensi penyimpanan, dan menganalisis kualitas hasil dengan metrik **VMAF, PSNR, SSIM** melalui FFmpeg.

Proyek ini dilengkapi dengan **antarmuka GUI berbasis PyQt6** (dark theme) dan **CLI** untuk penggunaan tanpa GUI.

---

## 🎯 Tujuan Penelitian

1. Menghasilkan purwarupa alur kerja (SOP/workflow) penerapan AI open-source untuk merestorasi aset video siaran lawas
2. Mengevaluasi dan mendapatkan data empiris mengenai peningkatan kualitas visual video arsip setelah melalui proses AI upscaling
3. Memformulasikan parameter encoding (rekompresi) yang paling efisien untuk sistem manajemen aset digital (DAM) penyiaran

---

## 🔧 Persyaratan Sistem

### Hardware
- **GPU (Disarankan)**: GPU dengan dukungan Vulkan (NVIDIA/AMD/Intel) untuk performa Real-ESRGAN
- **RAM**: Minimum 8 GB, disarankan 16 GB atau lebih
- **Storage**: SSD dengan ruang kosong 50 GB+ (video processing memerlukan space temporary)

### Software
- **Python**: 3.10 atau lebih baru (termasuk 3.14) — **tidak membutuhkan PyTorch**
- **FFmpeg**: Versi terbaru dengan dukungan `libx265` dan `libvmaf`
- **uv** (package manager): Disarankan untuk manajemen virtual environment

> ⚠️ **Catatan**: Proyek ini menggunakan binary **realesrgan-ncnn-vulkan** (bukan library Python)
> sehingga **tidak membutuhkan PyTorch** dan kompatibel dengan Python 3.14+.
> Binary akan **diunduh otomatis** dari GitHub Releases saat pertama kali digunakan.

---

## 📦 Instalasi

### 1. Masuk ke Direktori Proyek
```bash
cd /home/umri/PycharmProjects/VideoUpscaling
```

### 2. Aktifkan Virtual Environment
```bash
# Jika virtual environment belum ada, buat dengan uv:
uv venv .venv

# Aktivasi (Linux/macOS):
source .venv/bin/activate

# Aktivasi (Windows PowerShell):
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
# Menggunakan uv (direkomendasikan):
uv pip install PyQt6 pandas jinja2 requests

# Atau menggunakan pip:
pip install -r requirements.txt
```

### 4. Install FFmpeg

#### Linux (Fedora/RHEL):
```bash
sudo dnf install ffmpeg
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt install ffmpeg
```

#### Verifikasi Instalasi FFmpeg:
```bash
ffmpeg -version
ffprobe -version
# Pastikan output mengandung: --enable-libvmaf --enable-libx265
```

---

## 📁 Struktur Folder

```
VideoUpscaling/
├── input/                    # Letakkan video SD di sini
├── output/                   # Hasil video upscaled & compressed
├── temp/                     # File frame sementara (auto cleanup)
├── reports/                  # Laporan analisis kualitas
├── models/                   # Folder model (reserved)
├── tools/                    # Binary realesrgan-ncnn-vulkan (auto-download)
├── .venv/                    # Virtual environment Python
│
├── main.py                   # CLI entry point utama
├── run_gui.py                # GUI entry point (PyQt6)
├── gui.py                    # Implementasi antarmuka GUI
├── config.py                 # Konfigurasi pipeline (edit di sini)
├── metadata_extractor.py     # Ekstraksi metadata via ffprobe
├── upscaler.py               # AI upscaling (Real-ESRGAN + Bicubic)
├── compressor.py             # Kompresi HEVC/H.265 via FFmpeg
├── quality_analyzer.py       # Analisis VMAF/PSNR/SSIM + laporan
│
├── requirements.txt          # Dependensi Python
├── pyproject.toml            # Metadata proyek & script entry points
└── README.md
```

---

## 🚀 Cara Penggunaan

### Menggunakan GUI (Disarankan)

```bash
cd /home/umri/PycharmProjects/VideoUpscaling
.venv/bin/python run_gui.py
```

GUI memiliki 4 tab utama:

| Tab | Fungsi |
|-----|--------|
| **📁 Input Video** | Pilih file video SD, lihat metadata (resolusi, FPS, codec, durasi, bitrate) |
| **⚙️ Pengaturan** | Pilih metode upscaling, model ESRGAN, GPU/CPU, nilai CRF, preset HEVC, VMAF |
| **🔄 Progress & Log** | Monitor tahapan pipeline, log real-time, simpan log |
| **📊 Hasil** | Tabel VMAF/PSNR/SSIM dengan grade, daftar file output, buka laporan HTML |

### Menggunakan CLI

#### Process semua video di folder `input/`:
```bash
.venv/bin/python main.py
```

#### Process satu video spesifik:
```bash
.venv/bin/python main.py -i path/to/video.mp4
```

#### Skip analisis VMAF (lebih cepat):
```bash
.venv/bin/python main.py -i video.mp4 --skip-vmaf
```

#### Tanpa perbandingan Bicubic:
```bash
.venv/bin/python main.py --no-bicubic
```

#### Log detail (verbose):
```bash
.venv/bin/python main.py -i video.mp4 -v
```

### Penggunaan Modul Individual

#### Ekstraksi Metadata:
```bash
.venv/bin/python metadata_extractor.py video.mp4
```

#### Upscaling Saja:
```bash
.venv/bin/python upscaler.py video.mp4 realesrgan
.venv/bin/python upscaler.py video.mp4 bicubic
```

#### Kompresi HEVC:
```bash
.venv/bin/python compressor.py video_hd.mp4         # CRF 18, 23, 28
.venv/bin/python compressor.py video_hd.mp4 23      # CRF spesifik
```

#### Analisis VMAF:
```bash
.venv/bin/python quality_analyzer.py reference.mp4 distorted.mp4
```

---

## ⚙️ Konfigurasi

Edit `config.py` untuk mengubah parameter pipeline:

### Target Resolusi Output
```python
TARGET_WIDTH  = 1920   # HD 1080p
TARGET_HEIGHT = 1080
```

### Pengaturan Real-ESRGAN
```python
REALESRGAN_CONFIG = {
    'model_name': 'realesrgan-x4plus',  # Model upscaling
    'scale':      4,                     # Faktor skala (2 atau 4)
    'tile_size':  0,                     # 0=auto, 128/256 untuk VRAM rendah
    'use_gpu':    True,                  # True=Vulkan GPU, False=CPU
    'gpu_id':     1,                     # ID GPU (0=pertama, 1=kedua, dst.)
}
```

> Model yang tersedia:
> - `realesrgan-x4plus` — untuk foto/video nyata (default)
> - `realesrgan-x4plus-anime` — untuk konten animasi
> - `realesrnet-x4plus` — varian ringan
> - `realesr-animevideov3` — animasi, dioptimasi untuk video

### Pengaturan HEVC Compression
```python
HEVC_CONFIG = {
    'codec':       'libx265',
    'preset':      'medium',         # ultrafast/fast/medium/slow/veryslow
    'crf_values':  [18, 23, 28],     # Variasi CRF untuk eksperimen
    'audio_codec': 'aac',
    'audio_bitrate': '128k',
}
```

### Pengaturan Analisis Kualitas
```python
QUALITY_CONFIG = {
    'enable_vmaf':   True,   # Analisis VMAF (butuh libvmaf di FFmpeg)
    'enable_psnr':   True,   # Analisis PSNR
    'enable_ssim':   True,   # Analisis SSIM
    'vmaf_subsample': 1,     # 1=semua frame, 5=setiap 5 frame (lebih cepat)
}
```

---

## 📊 Output & Laporan

### File Output Video:
| File | Keterangan |
|------|-----------|
| `output/{video}_upscaled_realesrgan.mp4` | HD hasil AI upscaling Real-ESRGAN |
| `output/{video}_upscaled_bicubic.mp4` | HD hasil Bicubic (baseline) |
| `output/{video}_hevc_crf18.mp4` | HEVC kompresi kualitas tinggi |
| `output/{video}_hevc_crf23.mp4` | HEVC balanced |
| `output/{video}_hevc_crf28.mp4` | HEVC ukuran kecil |

### Laporan Analisis:
| File | Keterangan |
|------|-----------|
| `reports/{video}_metadata.json` | Metadata video asli |
| `reports/{video}_pipeline_results.json` | Hasil lengkap pipeline |
| `reports/{video}_quality_report.json` | Data metrik kualitas (JSON) |
| `reports/{video}_quality_report.csv` | Data metrik kualitas (CSV/Excel) |
| `reports/{video}_quality_report.html` | Laporan visual (dark theme) |

---

## 📈 Interpretasi Hasil VMAF

| VMAF Score | Grade | Deskripsi |
|------------|-------|-----------|
| ≥ 95 | 🟢 Excellent | Visually lossless, tidak terlihat perbedaan |
| 85 – 95 | 🔵 Good | Perbedaan minor, acceptable untuk broadcast |
| 70 – 85 | 🟡 Fair | Kompresi terlihat, masih acceptable |
| < 70 | 🔴 Poor | Artefak terlihat jelas |

---

## 🔬 Diagram Alir Pipeline

```
┌─────────────────┐
│  Video SD Input │
└────────┬────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Tahap 1: Ekstraksi Metadata            │
│  ffprobe → resolusi, FPS, codec,       │
│  durasi, bitrate, info audio           │
│  Output: reports/{stem}_metadata.json  │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Tahap 2: AI Upscaling                  │
│  Real-ESRGAN ncnn-vulkan (4x scale)    │
│    → ekstrak frame → AI → gabung       │
│  Bicubic via FFmpeg (baseline)         │
│  Output: output/{stem}_upscaled_*.mp4  │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Tahap 3: Rekompresi HEVC               │
│  libx265 CRF 18 / 23 / 28             │
│  Preset: medium (configurable)         │
│  Output: output/{stem}_hevc_crf*.mp4   │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Tahap 4: Analisis Kualitas             │
│  VMAF via libvmaf (FFmpeg)             │
│  PSNR & SSIM                           │
│  Compression ratio                     │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Tahap 5: Generate Laporan              │
│  JSON · CSV · HTML (dark theme)        │
│  Output: reports/{stem}_quality_*.*    │
└────────────────────────────────────────┘
```

---

## 🐛 Troubleshooting

### Error: Binary realesrgan-ncnn-vulkan tidak tersedia
Binary akan **diunduh otomatis** dari GitHub Releases. Jika gagal karena koneksi:
```bash
# Download manual dari:
# https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0
# Pilih: realesrgan-ncnn-vulkan-20220424-ubuntu.zip
# Ekstrak ke: tools/realesrgan-ncnn-vulkan
chmod +x /home/umri/PycharmProjects/VideoUpscaling/tools/realesrgan-ncnn-vulkan
```

### Error: FFmpeg atau ffprobe tidak ditemukan
Set path manual di `config.py`:
```python
FFMPEG_PATH  = "/usr/bin/ffmpeg"
FFPROBE_PATH = "/usr/bin/ffprobe"
```

### Error: libvmaf tidak tersedia di FFmpeg
Verifikasi build FFmpeg:
```bash
ffmpeg -version | grep libvmaf
```
Jika tidak ada, install FFmpeg dari repositori distro (Fedora/Ubuntu sudah include libvmaf).

### Error: CUDA out of memory / Vulkan error
Edit `config.py` untuk mengurangi tile size atau gunakan CPU:
```python
REALESRGAN_CONFIG = {
    'tile_size': 256,    # Kurangi untuk GPU VRAM rendah
    'use_gpu':   False,  # Set False untuk pakai CPU
}
```

### Error saat install PyQt6
```bash
uv pip install PyQt6 pandas jinja2 requests
```

### GUI tidak muncul (Linux headless/SSH)
Set DISPLAY environment:
```bash
export DISPLAY=:0
.venv/bin/python run_gui.py
```

---

## 📚 Referensi

- [Real-ESRGAN GitHub](https://github.com/xinntao/Real-ESRGAN)
- [Real-ESRGAN ncnn-vulkan releases](https://github.com/xinntao/Real-ESRGAN/releases)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [VMAF by Netflix](https://github.com/Netflix/vmaf)
- [H.265/HEVC Overview](https://x265.readthedocs.io/)
- [PyQt6 Documentation](https://doc.qt.io/qtforpython-6/)
- [uv – Python Package Manager](https://docs.astral.sh/uv/)

---

## 📄 Lisensi

Proyek penelitian untuk keperluan akademis.

---

**Dibuat untuk penelitian: Penerapan Algoritma AI Video Upscaling Berbasis Open-Source**
> Environment: Fedora Linux · Python 3.14 · FFmpeg 7.1.2 · PyQt6 6.11.0 · uv 0.11.8
