# EEG Simulator

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![MNE](https://img.shields.io/badge/MNE-1.0+-orange.svg)](https://mne.tools/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

EEG Simulator is a desktop EEG simulation tool built with **PyQt6** and **MNE-Python**. It lets you prepare an anatomical model, define cortical signal sources, configure electrodes and output, then run a real-time EEG simulation with waveform, FFT, and topomap views.

[中文文档](README_zh.md) | [Detailed UI docs](docs/README.md)

---

## Features

| Area | What It Does |
| --- | --- |
| Model preparation | Load MNE source spaces, configure electrode montage, generate/load forward models, and optionally build BEM models |
| Signal sources | Create patches from dipoles or atlas labels; configure sine, cosine, ERP, Gaussian, Gamma, oscillation, or custom waveforms |
| Coupling | Configure linear, nonlinear, delayed, or MNE geometry-weighted coupling between patches |
| Noise | Add stackable white, pink, 1/f, brown, line, EOG, EMG, and ECG noise instances |
| Electrodes and channels | Select montage and choose the channels used for simulation, output, and display |
| Real-time display | Show filtered waveforms, FFT spectrum, and a forward-model-based topomap heatmap |
| Output | Stream through LSL or export EDF/FIF files with optional duration limits |
| Project management | Save and reload patches, coupling, noise, filters, montage, model paths, and output settings |
| UI | Light/dark themes and Chinese/English interface |

---

## Current Workflow

The application is organized around a workflow-first layout:

```text
Model Preparation -> Signal Sources -> Electrodes & Channels -> Noise -> Output -> Real-time Signal
```

### 1. Model Preparation

Use this page to prepare the physical model used by the simulation.

- Load or create the source space.
- Configure electrode montage.
- Generate/load the forward model.
- Generate a BEM model if your workflow needs one.
- BEM generation status is shown below the BEM button.

Recommended order:

```text
Load source space -> Generate/load BEM if needed -> Select montage -> Generate forward model
```

If the source space and forward model are not perfectly aligned, the simulator can snap source dipoles to nearby valid forward vertices and logs the snapping distance.

<p align="center">
  <img src="docs/pic/model.png" alt="Model Preparation page" width="900">
</p>

### 2. Signal Sources

Use patches to describe cortical source activity.

- A patch is a group of dipoles that share waveform settings.
- Patches can be created manually from selected dipoles or from anatomical labels.
- Supported waveforms include sine, cosine, ERP, Gaussian, Gamma, transient oscillation, and custom samples.
- Patch amplitude is configured in nAm. The default MNE current scale is `1e-9 A/nAm`.

<p align="center">
  <img src="docs/pic/source.png" alt="Signal Sources page" width="900">
</p>

### 3. Coupling

Patch-to-patch coupling supports:

| Type | Formula |
| --- | --- |
| Linear | `target += strength * source` |
| Nonlinear | `target += strength * tanh(source)` |
| Delayed | `target += strength * source(t-delay)` |
| MNE weighted | Uses geometry-derived patch weights where available |

### 4. Electrodes & Channels

Select the montage and channels used by the run. The montage determines sensor positions for the forward model and heatmap.

<p align="center">
  <img src="docs/pic/electrode.png" alt="Electrodes and Channels page" width="900">
</p>

### 5. Noise

Noise configuration is separated from signal-source configuration.

| Type | Description |
| --- | --- |
| White | Flat-spectrum random noise |
| Pink | 1/f noise |
| 1/f | Fractional noise with configurable exponent |
| Brown | 1/f^2 random-walk-like noise |
| Line | 50/60 Hz power-line interference |
| EOG | Blink and eye-movement artifacts |
| EMG | Muscle artifacts |
| ECG | Cardiac artifacts |

Current implementation note: noise is generated independently per channel. This is useful for stress-testing denoising pipelines, but spatially correlated artifact models are still planned. See [docs/noise_spatial_model_todo.md](docs/noise_spatial_model_todo.md).

<p align="center">
  <img src="docs/pic/noise.png" alt="Noise configuration page" width="900">
</p>

### 6. Output

Configure sampling rate, output format, output directory, file name, and duration.

| Format | Description |
| --- | --- |
| LSL | Live stream through Lab Streaming Layer |
| EDF | EDF file export through pyEDFlib |
| FIF | MNE-native raw file export |

<p align="center">
  <img src="docs/pic/output.png" alt="Output page" width="900">
</p>

### 7. Real-time Signal

The real-time page shows:

- Multi-channel filtered waveforms.
- High-pass, low-pass, and 50/60 Hz notch filters.
- Optional FFT spectrum.
- Optional topomap heatmap.

The topomap heatmap uses forward-model sensor positions when a forward model is available. It is computed from the forward-projected EEG channels, so it remains consistent with the physical model rather than only the currently selected display channels.

<p align="center">
  <img src="docs/pic/realtime.png" alt="Real-time Signal page" width="900">
</p>

---

## Real-time Engine Design

The current real-time engine separates data generation from UI rendering:

1. A background `QThread` generates approximately **1 second** of EEG data at a time.
2. Generated chunks are stored in an internal queue.
3. The UI timer consumes a fixed number of samples per frame:

```text
samples_per_frame = sampling_rate / simulation_fps
```

For example, at `1000 Hz` and `20 FPS`, each UI frame consumes about `50` samples.

This design avoids calling the forward model on every UI refresh. It also keeps rendering responsive even when generation is heavier than a single frame.

### Performance Notes

- Forward projection uses an optimized sparse path when possible: only active dipole columns of the forward matrix are projected.
- If the forward structure is not compatible with the sparse path, the simulator falls back to the safe MNE-compatible path.
- Waveform display is decimated for rendering only; generated and exported data keep the original sampling rate.
- FFT is capped to a lightweight analysis window for real-time display.
- Topomap power is prepared in the worker from forward-projected data, while the UI only renders the latest result.
- Slow-path logs include worker, projection, noise, buffer, plot, and heatmap timing.

Example log:

```text
实时性能: samples=50 queued=1.20s worker=...ms(source=... project=... heatmap_power=... noise=...) ui=...ms(buffer=... plot=... heatmap=...)
```

---

## Forward Model and Heatmap Behavior

When a forward model is available:

- Patch dipoles are projected through the forward solution.
- The simulator maps UI channel names to forward-model channel names.
- If a selected dipole vertex is missing from the forward source space, the simulator can snap it to a nearby valid forward vertex and logs the distance.
- The real-time heatmap uses the forward model's EEG sensor positions.

When no forward model is available:

- The app warns that no forward model is ready.
- A deterministic simplified projection is used as a fallback.
- The fallback is useful for UI testing and rough demos, but not for quantitative interpretation.

---

## Project Structure

```text
eeg_simulator/
  core/
    mne_simulator.py          # Forward projection and MNE integration
    output_sink.py            # LSL / EDF / FIF output
    signal_engine.py          # Waveform and noise generation
    simulator/
      app.py                  # Main window state
      simulation.py           # Real-time queue, worker, start/stop loop
      signal.py               # Projection, filtering, FFT, heatmap power
      buffers.py              # Buffer sizing and sampling-rate sync
      mne.py                  # Model-generation helpers
      patch_ops.py            # Patch/coupling/noise operations
  models/                     # Patch, dipole, coupling, signal models
  ui/                         # Themes, widgets, panels, dialogs
  utils/                      # Config, project, i18n, logging, MNE loading
docs/                         # UI documentation
tests/                        # Unit tests
main.py                       # Launch script
```

---

## Quick Start

### Requirements

- Python 3.8+
- Windows, Linux, or macOS
- 4 GB RAM minimum, 8 GB recommended

### Install

```bash
git clone <repository-url>
cd eeg-simulator

python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python -c "import mne; mne.datasets.sample.data_path()"
```

### Launch

```bash
python main.py

# or
python -m eeg_simulator
```

---

## Testing

```bash
python -m pytest -q
```

Optional scripts:

```bash
python tests/test_compare_mne.py
python tests/test_noise_visualization.py
```

---

## Settings

User settings are stored under `~/.eegs/config.db`:

- Language
- Theme
- Default sampling rate
- Default project directory
- Filter order
- Heatmap refresh interval

---

## License

[MIT License](LICENSE)

---

## Acknowledgments

- [MNE-Python](https://mne.tools/)
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- [pyqtgraph](http://www.pyqtgraph.org/)
- [FreeSurfer](https://surfer.nmr.mgh.harvard.edu/)
