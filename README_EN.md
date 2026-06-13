# EEG Simulator | 脑电信号仿真器

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![MNE](https://img.shields.io/badge/MNE-1.0+-orange.svg)](https://mne.tools/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An EEG signal simulation platform based on **PyQt6** and **MNE-Python**, supporting loading source spaces from real brain models, visual selection of signal sources, configuration of dipoles, signal generators, and coupling models, with real-time EEG signal simulation.

[中文文档](README.md)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **Real Brain Models** | Load MNE standard brain models (e.g., sample dataset) with MRI slice visualization |
| 🎯 **Visual Source Selection** | Manually select on MRI slices or batch select by anatomical labels (Atlas) |
| 📊 **Flexible Signal Config** | Support for sine, square, sawtooth, pulse, noise, and other signal types |
| 🔗 **Coupling Models** | Define connection relationships between dipoles (linear/non-linear/delayed coupling) |
| 🔊 **Noise Management** | Support for white noise, pink noise, 1/f noise, physiological noise (EOG/EMG/ECG), etc. |
| 📁 **Project Management** | Create, save, and load complete simulation project configurations |
| 🎨 **Modern UI** | Support for dark/light theme switching, Chinese/English interface |
| ⚙️ **BEM Model** | Set conductivity for brain, skull, and scalp, and generate BEM models |

---

## 📁 Project Structure

```
EEG_Simulation/
├── eeg_simulator/                 # Main package
│   ├── core/                      # Simulation core
│   │   ├── simulator_nav.py       # Main simulator (NavigationView layout)
│   │   ├── signal_engine.py       # Signal generation engine
│   │   └── mne_simulator.py       # MNE integration simulator
│   ├── models/                    # Data models
│   │   ├── patch.py               # Patch model (dipole group management)
│   │   ├── coupling.py            # Coupling models
│   │   ├── mne_coupling.py        # MNE coupling engine
│   │   └── signal.py              # Signal generators
│   ├── ui/                        # User interface
│   │   ├── styles.py              # QSS styles
│   │   ├── themes.py              # Theme management (dark/light)
│   │   ├── widgets/               # Basic widgets
│   │   ├── panels/                # Configuration panels
│   │   └── dialogs/               # Dialogs
│   ├── utils/                     # Utility modules
│   │   ├── config_manager.py      # Configuration management (SQLite)
│   │   ├── project_manager.py     # Project management
│   │   ├── mne_loader.py          # MNE data loading
│   │   ├── i18n.py                # Internationalization
│   │   └── logger.py              # Logging management
│   ├── __init__.py
│   └── __main__.py                # Module entry
├── tests/                         # Test modules
├── main.py                        # Launch script
├── requirements.txt               # Dependencies
└── README_EN.md                   # This file
```

---

## 🚀 Quick Start

### Requirements

- Python 3.8+
- Windows / Linux / macOS
- 4GB+ RAM (8GB recommended)

### Installation

```bash
# 1. Clone repository
git clone <repository-url>
cd EEG_Simulation

# 2. Create virtual environment (recommended)
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download MNE Sample dataset (auto-download on first run)
python -c "import mne; mne.datasets.sample.data_path()"
```

### Launch

```bash
# Method 1: Using launch script
python main.py

# Method 2: Using module
python -m eeg_simulator
```

---

## 📖 Usage Guide

### Basic Workflow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Load Source │ -> │ Select      │ -> │ Configure   │ -> │ Run         │
│ Space       │    │ Sources     │    │ Signals     │    │ Simulation  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

#### 1. Load Source Space
- Click **"Load MNE Sample Source Space"** to load sample data
- Or click **"Load from File"** to load custom `-src.fif` files

<p align="center">
  <img src="docs/pic/source_cfg.jpg" alt="Source Config page" width="900">
</p>

#### 2. Select Signal Sources
- Click **"Select Source Points..."** to open the MRI slice visual selector
- Click on MRI slices to select individual points (green=left, red=right, yellow star=selected)
- Or check regions in **"Anatomy Labels"** to batch add all source points in selected regions

<p align="center">
  <img src="docs/pic/patch.jpg" alt="Patch Manager" width="900">
</p>

#### 3. Configure Signals
- **Patch Manager**: Create and manage Patches (adjacent dipole groups)
- **Signal Generators**: Configure parameters for sine, ERP, Gamma, etc.
- **Coupling Models**: Define linear/non-linear/delayed connections between Patches
- **Noise Settings**: Add white noise, physiological noise, etc.

<p align="center">
  <img src="docs/pic/noise.jpg" alt="Noise Manager" width="900">
</p>

#### 4. Set BEM Model (Optional)
- Set conductivity for brain, skull, and scalp
- Click **"Generate BEM Model"**

#### 5. Start Simulation
- Set sampling rate (default 1000 Hz)
- Select EEG channels to display

<p align="center">
  <img src="docs/pic/channel.jpg" alt="Electrode & Channels page" width="900">
</p>

- Configure output format and simulation control

<p align="center">
  <img src="docs/pic/output.jpg" alt="Output Settings page" width="900">
</p>

- Click **"Start Simulation"** to view real-time waveforms

<p align="center">
  <img src="docs/pic/realtime.jpg" alt="Real-time Signal page" width="900">
</p>

---

## 🔧 Core Concepts

### Patch Model

**Patch** is the core abstraction for EEG signal simulation, representing a functional region in the brain:

- Contains one **anchor dipole** and adjacent dipoles
- All dipoles share the same **waveform settings**
- Supports multiple waveform types: sine, ERP, Gaussian, Gamma oscillation, etc.

```python
from eeg_simulator.models import Patch

# Create Patch
patch = Patch(
    id="patch_1",
    label_name="superiortemporal-lh",
    hemi="lh",
    waveform_type="sin",
    waveform_params={"frequency": 10, "amplitude": 10}
)
```

### Coupling Models

Define signal connection relationships between Patches:

| Coupling Type | Formula | Description |
|--------------|---------|-------------|
| Linear | `target += strength * source` | Direct signal transfer |
| Non-linear | `target += strength * tanh(source)` | Saturating non-linearity |
| Delayed | `target += strength * source(t-delay)` | Time-delayed connection |

### Signal Types

| Type | Description | Parameters |
|------|-------------|------------|
| Sine | Sine wave | frequency, amplitude, phase |
| ERP | Event-related potential | frequency, latency, width |
| Gaussian | Gaussian modulation | frequency, sigma, center |
| Gamma | Gamma oscillation | frequency, alpha, beta |

---

## 🔊 Noise Management

The system supports multiple noise types and allows stacking multiple noise instances to simulate various interferences in real EEG environments.

### Noise Types

| Type | Description | Configurable Parameters |
|------|-------------|------------------------|
| **White** | White noise (flat spectrum) | Amplitude, Cutoff frequency |
| **Pink** | Pink noise (1/f spectrum) | Amplitude |
| **1/f** | Fractional noise | Amplitude, Exponent |
| **Brown** | Brown noise (1/f² spectrum) | Amplitude |
| **Line** | Power line interference | Amplitude, Frequency (50/60 Hz) |
| **EOG** | Electrooculogram artifacts | Amplitude, Cutoff frequency, Blink rate |
| **EMG** | Electromyogram artifacts | Amplitude, Cutoff frequency |
| **ECG** | Electrocardiogram artifacts | Amplitude, Heart rate (BPM) |

#### Physiological Noise Details

**ECG (Electrocardiogram Artifacts)**
- Simulates ECG waveforms including P wave, QRS complex, and T wave
- Uses a simplified physiological model to generate periodic heartbeat signals based on heart rate
- Typical amplitude: 20-50 μV
- Suitable for simulating cardiac interference in EEG

**EOG (Electrooculogram Artifacts)**
- Simulates low-frequency transient interference from eye blinks and movements
- Blink waveform: biphasic pulse with rapid rise and slow decay
- Configurable blink rate (default 0.5 Hz, approximately one blink every 2 seconds)
- Includes slow eye movement baseline drift (0.1-0.5 Hz)
- Typical amplitude: 50-200 μV (blink artifacts are typically strong)

**EMG (Electromyogram Artifacts)**
- Simulates high-frequency, non-periodic noise from muscle activity
- Multi-band synthesis: 10-30 Hz (large motor units), 30-100 Hz (primary energy), 100-200 Hz (fast motor units)
- Simulates burst activity (muscle contraction periods)
- Typical amplitude: 10-30 μV

### Noise Spectral Characteristics

| Noise Type | Power Spectral Density | Spectral Feature | Generation Method |
|-----------|----------------------|-----------------|------------------|
| **White** | $P(f) = C$ | Flat spectrum | Pure random sequence |
| **Pink** | $P(f) = C/f$ | 1/f decay | Integration of white noise |
| **Brown** | $P(f) = C/f^2$ | 1/f² decay | Double integration of white noise |
| **1/f** | $P(f) = C/f^\alpha$ | Adjustable α decay | Fractional integration filter |

#### White Noise

**Spectral Feature**: **Flat** - Equal energy at all frequencies

| Property | Description |
|----------|-------------|
| **Physical Meaning** | Like white light containing all colors, equal energy at all frequencies |
| **Sounds Like** | Hissing sound, like TV static |
| **EEG Relevance** | Simulates electronic thermal noise, quantization noise |

**FFT Plot**: Approximately horizontal line

#### Pink Noise

**Spectral Feature**: **1/f decay** - Equal energy per octave

| Property | Description |
|----------|-------------|
| **Physical Meaning** | High energy at low frequencies, low at high, decaying as 1/f |
| **Sounds Like** | "Softer", like wind or flowing water |
| **EEG Relevance** | Close to real EEG background (EEG exhibits 1/f characteristics) |

**Energy Distribution**:
- 1-2 Hz: Energy = 1
- 2-4 Hz: Energy = 0.5 (same total as 1-2Hz band)
- 4-8 Hz: Energy = 0.25

**FFT Plot**: Monotonically decreasing left to right (slope ~ -10 dB/octave)

#### Brown Noise

**Spectral Feature**: **1/f² decay** - Low frequencies absolutely dominant

| Property | Description |
|----------|-------------|
| **Physical Meaning** | Faster decay than pink noise, random walk characteristics |
| **Sounds Like** | Deep rumbling sound |
| **EEG Relevance** | Simulates electrode polarization drift, slow baseline wander |

**Comparison with White Noise**:
- White: Adjacent samples independent
- Brown: Strong correlation (random walk)

**FFT Plot**: Steep decrease (slope ~ -20 dB/octave)

#### 1/f Noise (Fractional)

**Spectral Feature**: **1/f^α decay** (adjustable α, 0 ≤ α ≤ 2)

| α Value | Noise Type | Spectral Slope |
|---------|-----------|----------------|
| 0 | White | 0 dB/octave |
| 0.5 | Intermediate | -5 dB/octave |
| 1.0 | Pink | -10 dB/octave |
| 1.5 | Intermediate | -15 dB/octave |
| 2.0 | Brown | -20 dB/octave |

**Usage**: Fine-tune background noise spectral characteristics as needed

#### Spectral Comparison Diagram

```
Amplitude (dB)
  |
0 |    White  ─────────────────────────
  |    Pink   ─────╲
  |    1/f (α=1.5) ──────╲
  |    Brown  ───────────╲
-20|                       ╲
  |                         ╲
-40|                           ╲_____
  |
  +------------------------------------
     1Hz   10Hz   100Hz   1000Hz   Frequency
```

### Usage

1. Click **"Noise Settings"** button to open the noise manager
2. Select noise type in the right panel and configure parameters
3. Click **"Add"** to add the noise instance to the list
4. Multiple instances of the same type can be added (e.g., white noise with different amplitudes)
5. View and manage added noises in the left panel
6. Click **"OK"** to apply the configuration

### Noise Parameters

| Parameter | Description | Applicable to |
|-----------|-------------|---------------|
| **Amplitude** | Noise intensity (μV) | All noise types |
| **Cutoff Frequency** | Low-pass filter cutoff (Hz) | White, EOG, EMG |
| **Exponent** | Spectral exponent for 1/f noise | 1/f noise |
| **Line Frequency** | 50 Hz or 60 Hz | Line noise |
| **Heart Rate** | Heartbeat frequency (BPM) | ECG noise |
| **Blink Rate** | Blinks per second | EOG noise |

---

## 🎮 Keyboard Shortcuts

| Shortcut | Function |
|----------|----------|
| `Ctrl+N` | New Project |
| `Ctrl+O` | Open Project |
| `Ctrl+S` | Save Project |
| `Ctrl+Shift+S` | Save As |

---

## ⚙️ Settings

Program settings are automatically saved to `~/.eegs/config.db` (SQLite database):

- Language (Chinese/English)
- Theme (Dark/Light)
- Default sampling rate
- Default project directory
- Filter Order

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific tests
python tests/run_tests.py

# Compare with MNE simulation results
python tests/test_compare_mne.py

# Generate noise waveform visualization
python tests/test_noise_visualization.py
```

### Noise Visualization Test

Run `test_noise_visualization.py` to generate waveform and spectrum comparison plots for all noise types:

- **Noise Overview** (`tests/noise_plots/noise_overview.png`): Time-domain waveforms + spectrum comparison for 8 noise types
- **Physiological Noise Details** (`tests/noise_plots/noise_detailed_detailed.png`): Parameter variation comparison for ECG/EOG/EMG

---

## 📚 Dependencies

- **GUI**: [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) ≥ 6.0.0
- **Signal Processing**: [NumPy](https://numpy.org/) ≥ 1.20.0, [MNE-Python](https://mne.tools/) ≥ 1.0.0
- **Visualization**: [pyqtgraph](http://www.pyqtgraph.org/) ≥ 0.13.0, [Matplotlib](https://matplotlib.org/) ≥ 3.5.0
- **Brain Imaging**: [NiBabel](https://nipy.org/nibabel/) 5.4.0
- **Data Export**: [pyEDFlib](https://pyedflib.readthedocs.io/) 0.1.42

---

## 📄 License

[MIT License](LICENSE)

---

## 🙏 Acknowledgments

- [MNE-Python](https://mne.tools/) - Powerful EEG data analysis tools
- [PyQt](https://www.riverbankcomputing.com/software/pyqt/) - Qt bindings for Python
- [pyqtgraph](http://www.pyqtgraph.org/) - High-performance scientific plotting
- [FreeSurfer](https://surfer.nmr.mgh.harvard.edu/) - Brain imaging analysis software

---

<p align="center">
  <sub>Built with ❤️ for neuroscience research</sub>
</p>
