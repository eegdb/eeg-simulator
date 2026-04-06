#!/usr/bin/env python
"""程序入口 - 启动EEG Simulator"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eeg_simulator.__main__ import main

if __name__ == "__main__":
    main()