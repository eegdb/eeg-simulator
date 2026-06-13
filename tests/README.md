# EEG Simulator 单元测试

## 测试结构

```
tests/
├── __init__.py              # 测试包初始化
├── run_tests.py             # 测试运行入口
├── test_models.py           # 模型类测试
├── test_utils.py            # 工具模块测试
├── test_signal_engine.py    # 信号引擎测试
├── test_noise_continuity/   # 噪声连续性测试
└── README.md                # 本文档
```

## 运行测试

### 方法1：使用 run_tests.py（推荐）

```bash
python tests/run_tests.py
```

### 方法2：使用 unittest 模块

```bash
# 运行所有测试
python -m unittest discover tests -v

# 运行单个测试文件
python -m unittest tests.test_models -v
python -m unittest tests.test_utils -v
python -m unittest tests.test_signal_engine -v

# 运行单个测试类
python -m unittest tests.test_models.TestDipole -v
```

### 方法3：使用 pytest

```bash
# 安装依赖（含 pytest）
pip install -r requirements.txt

# 运行所有测试
pytest tests/ -v

# 运行并生成覆盖率报告
pytest tests/ -v --cov=eeg_simulator --cov-report=html
```

## 测试覆盖范围

### test_models.py
- `Dipole`: 偶极子定义模型
  - 初始化测试
  - 方向向量归一化测试
  - 可选属性测试
  
- `SignalGenerator`: 信号生成器模型
  - 各种信号类型初始化测试
  - 参数更新测试

- `CouplingModel`: 耦合模型
  - 线性/非线性/延迟耦合测试

### test_utils.py
- `Translator`: 国际化翻译
- `ConfigManager`: 配置管理（SQLite）

### test_signal_engine.py
- `SignalEngine`: 信号生成引擎
  - 各种波形生成测试

### test_noise_continuity/
- 各类噪声的批次连续性测试
