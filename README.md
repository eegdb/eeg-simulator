# EEG Simulator | 脑电信号仿真器

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![MNE](https://img.shields.io/badge/MNE-1.0+-orange.svg)](https://mne.tools/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

基于 **PyQt6** 和 **MNE-Python** 的脑电信号仿真平台，支持从真实大脑模型加载源空间，可视化选择信号源，配置偶极子、信号生成器和耦合模型，实现实时脑电信号仿真。

[English Documentation](README_EN.md)

---

## ✨ 功能特点

| 功能 | 描述 |
|------|------|
| 🧠 **真实脑模型** | 加载 MNE 标准大脑模型（如 sample 数据集），支持 MRI 切片可视化 |
| 🎯 **可视化源点选择** | 在 MRI 切片上手动选择，或按解剖标签（Atlas）批量选择信号源 |
| 📊 **灵活的信号配置** | 支持正弦波、方波、锯齿波、脉冲、噪声等多种信号类型 |
| 🔗 **耦合模型** | 定义偶极子之间的连接关系（线性/非线性/延迟耦合）|
| 🔊 **噪声管理** | 支持白噪声、粉红噪声、1/f 噪声、生理噪声（EOG/EMG/ECG）等 |
| 📁 **项目管理** | 创建、保存、加载完整的仿真项目配置 |
| 🎨 **现代化 UI** | 支持深色/浅色主题切换，中英文界面 |
| ⚙️ **BEM 模型** | 设置脑组织、颅骨、头皮的导电率并生成 BEM 模型 |

---

## 📁 项目结构

```
EEG_Simulation/
├── eegs/                          # 主程序包
│   ├── core/                      # 仿真核心
│   │   ├── simulator_nav.py       # 主仿真器（NavigationView 布局）
│   │   ├── signal_engine.py       # 信号生成引擎
│   │   ├── mne_simulator.py       # MNE 集成仿真器
│   │   └── simulator.py           # 基础仿真器
│   ├── models/                    # 数据模型
│   │   ├── patch.py               # Patch 模型（偶极子组管理）
│   │   ├── coupling.py            # 耦合模型
│   │   ├── mne_coupling.py        # MNE 耦合引擎
│   │   └── signal.py              # 信号生成器
│   ├── ui/                        # 用户界面
│   │   ├── styles.py              # QSS 样式
│   │   ├── themes.py              # 主题管理（深色/浅色）
│   │   ├── widgets/               # 基础控件
│   │   ├── panels/                # 配置面板
│   │   └── dialogs/               # 对话框
│   ├── utils/                     # 工具模块
│   │   ├── config_manager.py      # 配置管理（SQLite）
│   │   ├── project_manager.py     # 项目管理
│   │   ├── mne_loader.py          # MNE 数据加载
│   │   ├── i18n.py                # 国际化
│   │   └── logger.py              # 日志管理
│   ├── __init__.py
│   └── __main__.py                # 模块入口
├── tests/                         # 测试模块
├── main.py                        # 启动脚本
├── requirements.txt               # 依赖列表
└── README.md                      # 本文件
```

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Windows / Linux / macOS
- 4GB+ 内存（推荐 8GB）

### 安装

```bash
# 1. 克隆仓库
git clone <repository-url>
cd EEG_Simulation

# 2. 创建虚拟环境（推荐）
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 下载 MNE Sample 数据集（首次运行自动下载）
python -c "import mne; mne.datasets.sample.data_path()"
```

### 启动程序

```bash
# 方式1：使用启动脚本
python main.py

# 方式2：使用模块方式
python -m eegs
```

---

## 📖 使用指南

### 基本工作流程

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  加载源空间  │ -> │  选择信号源  │ -> │  配置信号   │ -> │  运行仿真   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

#### 1. 加载源空间
- 点击 **"加载 MNE Sample 源空间"** 加载示例数据
- 或点击 **"从文件加载源空间"** 加载自定义 `-src.fif` 文件

#### 2. 选择信号源
- 点击 **"选择源空间点..."** 打开 MRI 切片可视化选择器
- 在 MRI 切片上点击选择单个点（绿色=左脑，红色=右脑，黄色星形=已选中）
- 或在 **"解剖学标签"** 中勾选区域，批量添加选中区域的全部源点

#### 3. 配置信号
- **Patch 管理**：创建和管理 Patch（相邻偶极子组）
- **信号生成器**：为正弦波、ERP、Gamma 等信号配置参数
- **耦合模型**：定义 Patch 之间的线性/非线性/延迟连接
- **噪声设置**：添加白噪声、生理噪声等

#### 4. 设置 BEM 模型（可选）
- 设置脑组织、颅骨、头皮的导电率
- 点击 **"生成 BEM 模型"**

#### 5. 开始仿真
- 设置采样率（默认 1000 Hz）
- 选择要显示的 EEG 通道
- 点击 **"开始仿真"** 查看实时波形

---

## 🔧 核心概念

### Patch 模型

**Patch** 是 EEG 信号仿真的核心抽象，表示大脑中的一个功能区域：

- 包含一个**中心偶极子**（anchor）和相邻偶极子
- 所有偶极子共享相同的**波形设置**
- 支持多种波形类型：正弦波、ERP、Gaussian、Gamma 振荡等

```python
from eegs.models import Patch

# 创建 Patch
patch = Patch(
    id="patch_1",
    label_name="superiortemporal-lh",
    hemi="lh",
    waveform_type="sin",
    waveform_params={"frequency": 10, "amplitude": 10}
)
```

### 耦合模型

定义 Patch 之间的信号连接关系：

| 耦合类型 | 公式 | 说明 |
|---------|------|------|
| 线性耦合 | `target += strength * source` | 直接信号传递 |
| 非线性耦合 | `target += strength * tanh(source)` | 饱和非线性 |
| 延迟耦合 | `target += strength * source(t-delay)` | 时延连接 |

### 信号类型

| 类型 | 说明 | 参数 |
|------|------|------|
| Sine | 正弦波 | frequency, amplitude, phase |
| ERP | 事件相关电位 | frequency, latency, width |
| Gaussian | 高斯调制 | frequency, sigma, center |
| Gamma | Gamma 振荡 | frequency, alpha, beta |

---

## 🔊 噪声管理

系统支持多种噪声类型，可叠加多个噪声实例，模拟真实 EEG 环境中的各种干扰。

### 噪声类型

| 类型 | 说明 | 可配置参数 |
|------|------|-----------|
| **White** | 白噪声（平坦频谱）| 幅度、截止频率 |
| **Pink** | 粉红噪声（1/f 频谱）| 幅度 |
| **1/f** | 分数噪声 | 幅度、指数 |
| **Brown** | 布朗噪声（1/f² 频谱）| 幅度 |
| **Line** | 工频干扰 | 幅度、频率（50/60 Hz）|
| **EOG** | 眼电伪迹 | 幅度、截止频率、眨眼频率 |
| **EMG** | 肌电伪迹 | 幅度、截止频率 |
| **ECG** | 心电伪迹 | 幅度、心率（BPM）|

### 使用方式

1. 点击 **"噪声设置"** 按钮打开噪声管理器
2. 在右侧面板选择噪声类型，配置参数
3. 点击 **"添加"** 将噪声实例加入列表
4. 可添加多个同类型噪声实例（如不同幅度的白噪声）
5. 在左侧面板查看和管理已添加的噪声
6. 点击 **"确定"** 应用配置

### 噪声参数说明

| 参数 | 说明 | 适用范围 |
|------|------|---------|
| **幅度** | 噪声强度（μV）| 所有噪声类型 |
| **截止频率** | 低通滤波截止频率（Hz）| White、EOG、EMG |
| **指数** | 1/f 噪声的频谱指数 | 1/f 噪声 |
| **工频频率** | 50 Hz 或 60 Hz | Line 噪声 |
| **心率** | 心跳频率（BPM）| ECG 噪声 |
| **眨眼频率** | 眨眼次数/秒 | EOG 噪声 |

---

## 🎮 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+N` | 新建项目 |
| `Ctrl+O` | 打开项目 |
| `Ctrl+S` | 保存项目 |
| `Ctrl+Shift+S` | 另存为 |

---

## ⚙️ 设置

程序设置自动保存在 `~/.eegs/config.db`（SQLite 数据库）：

- 语言（中文/英文）
- 主题（深色/浅色）
- 默认采样率
- 默认项目目录
- 滤波阶数

---

## 🧪 测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python tests/run_tests.py

# 对比 MNE 仿真结果
python tests/test_compare_mne.py
```

---

## 📚 依赖

- **GUI**: [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) ≥ 6.0.0
- **信号处理**: [NumPy](https://numpy.org/) ≥ 1.20.0, [MNE-Python](https://mne.tools/) ≥ 1.0.0
- **可视化**: [pyqtgraph](http://www.pyqtgraph.org/) ≥ 0.13.0, [Matplotlib](https://matplotlib.org/) ≥ 3.5.0
- **脑影像**: [NiBabel](https://nipy.org/nibabel/) 5.4.0
- **数据导出**: [pyEDFlib](https://pyedflib.readthedocs.io/) 0.1.42

---

## 📄 许可证

[MIT License](LICENSE)

---

## 🙏 致谢

- [MNE-Python](https://mne.tools/) - 强大的脑电数据分析工具
- [PyQt](https://www.riverbankcomputing.com/software/pyqt/) - Qt 的 Python 绑定
- [pyqtgraph](http://www.pyqtgraph.org/) - 高性能科学绘图
- [FreeSurfer](https://surfer.nmr.mgh.harvard.edu/) - 脑影像分析软件

---

<p align="center">
  <sub>Built with ❤️ for neuroscience research</sub>
</p>
