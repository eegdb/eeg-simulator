"""
噪声连续性测试包

包含各类噪声的连续性测试:
- test_pink_noise.py: 粉红噪声
- test_brown_noise.py: 布朗噪声  
- test_line_noise.py: 工频噪声
- test_ecg_noise.py: 心电伪迹
- test_eog_noise.py: 眼电伪迹
- test_emg_noise.py: 肌电伪迹
- run_all.py: 运行所有测试
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
