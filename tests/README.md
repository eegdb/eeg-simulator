# EEG Simulator 单元测试

## 测试结构

```
tests/
├── __init__.py              # 测试包初始化
├── run_tests.py             # 测试运行入口
├── test_models.py           # 模型类测试
├── test_utils.py            # 工具模块测试
├── test_signal_engine.py    # 信号引擎测试
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
python -m unittest tests.test_models.TestDipoleDefinition -v
```

### 方法3：使用 pytest（需要安装 pytest）

```bash
# 安装 pytest
pip install pytest pytest-cov

# 运行所有测试
pytest tests/ -v

# 运行并生成覆盖率报告
pytest tests/ -v --cov=eegs --cov-report=html
```

## 测试覆盖范围

### test_models.py
- `DipoleDefinition`: 偶极子定义模型
  - 初始化测试
  - 方向向量归一化测试
  - 可选属性测试
  
- `SignalGenerator`: 信号生成器模型
  - 各种信号类型初始化测试
  - 参数更新测试
  
- `CouplingModel`: 耦合模型
  - 线性和非线性耦合测试
  - 参数修改测试

### test_utils.py
- `Translator`: 国际化翻译
  - 语言设置测试
  - 翻译功能测试
  
- `ConfigManager`: 配置管理
  - 默认配置加载
  - 配置读写测试
  - 主题和语言设置测试

### test_signal_engine.py
- `SignalEngine`: 信号引擎
  - 各种信号类型生成测试（正弦、方波、锯齿波、噪声等）
  - 信号参数测试（振幅、频率、相位）

## 添加新测试

1. 在对应的测试文件中添加测试类或方法
2. 测试方法名必须以 `test_` 开头
3. 使用 `unittest.TestCase` 的断言方法

示例：

```python
class TestNewFeature(unittest.TestCase):
    def setUp(self):
        """测试前准备"""
        pass
    
    def tearDown(self):
        """测试后清理"""
        pass
    
    def test_something(self):
        """测试某个功能"""
        result = some_function()
        self.assertEqual(result, expected_value)
```
