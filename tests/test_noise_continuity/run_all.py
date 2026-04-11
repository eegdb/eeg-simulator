#!/usr/bin/env python
"""
运行所有噪声连续性测试

运行方式:
    python tests/test_noise_continuity/run_all.py
    
或运行单个测试:
    python tests/test_noise_continuity/test_pink_noise.py
    python tests/test_noise_continuity/test_brown_noise.py
    python tests/test_noise_continuity/test_line_noise.py
    python tests/test_noise_continuity/test_ecg_noise.py
    python tests/test_noise_continuity/test_eog_noise.py
    python tests/test_noise_continuity/test_emg_noise.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 导入所有测试模块
from test_pink_noise import test_pink_noise_continuity
from test_brown_noise import test_brown_noise_continuity
from test_line_noise import test_line_noise_continuity
from test_ecg_noise import test_ecg_noise_continuity
from test_eog_noise import test_eog_noise_continuity
from test_emg_noise import test_emg_noise_continuity


def run_all_tests():
    """运行所有噪声连续性测试"""
    
    output_dir = os.path.join(os.path.dirname(__file__), 'plots')
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "=" * 70)
    print(" EEG Simulator - Noise Continuity Test Suite ".center(70, "="))
    print("=" * 70)
    
    all_results = {}
    
    # 1. 粉红噪声测试
    print("\n" + "-" * 70)
    print("[1/6] 粉红噪声测试")
    print("-" * 70)
    all_results['pink'] = test_pink_noise_continuity(
        sampling_rate=1000,
        chunk_duration=0.5,
        n_chunks=10,
        save_path=os.path.join(output_dir, 'pink_noise_continuity.png')
    )
    
    # 2. 布朗噪声测试
    print("\n" + "-" * 70)
    print("[2/6] 布朗噪声测试")
    print("-" * 70)
    all_results['brown'] = test_brown_noise_continuity(
        sampling_rate=1000,
        chunk_duration=0.5,
        n_chunks=10,
        save_path=os.path.join(output_dir, 'brown_noise_continuity.png')
    )
    
    # 3. 工频噪声测试
    print("\n" + "-" * 70)
    print("[3/6] 工频噪声测试")
    print("-" * 70)
    all_results['line'] = test_line_noise_continuity(
        sampling_rate=1000,
        chunk_duration=0.5,
        n_chunks=10,
        line_freq=50,
        save_path=os.path.join(output_dir, 'line_noise_continuity.png')
    )
    
    # 4. ECG测试
    print("\n" + "-" * 70)
    print("[4/6] 心电伪迹测试")
    print("-" * 70)
    all_results['ecg'] = test_ecg_noise_continuity(
        sampling_rate=1000,
        chunk_duration=0.5,
        n_chunks=10,
        heart_rate=60,
        save_path=os.path.join(output_dir, 'ecg_noise_continuity.png')
    )
    
    # 5. EOG测试
    print("\n" + "-" * 70)
    print("[5/6] 眼电伪迹测试")
    print("-" * 70)
    all_results['eog'] = test_eog_noise_continuity(
        sampling_rate=1000,
        chunk_duration=0.5,
        n_chunks=10,
        blink_rate=0.5,
        save_path=os.path.join(output_dir, 'eog_noise_continuity.png')
    )
    
    # 6. EMG测试
    print("\n" + "-" * 70)
    print("[6/6] 肌电伪迹测试")
    print("-" * 70)
    all_results['emg'] = test_emg_noise_continuity(
        sampling_rate=1000,
        chunk_duration=0.5,
        n_chunks=10,
        amplitude=20.0,
        save_path=os.path.join(output_dir, 'emg_noise_continuity.png')
    )
    
    # 汇总报告
    print("\n" + "=" * 70)
    print(" 测试汇总报告 ".center(70, "="))
    print("=" * 70)
    print(f"{'噪声类型':<20} {'独立生成跳跃':>15} {'连续生成跳跃':>15} {'改进':>10}  {'说明'}")
    print("-" * 70)
    
    summaries = {
        'pink': '随机过程，无需连续性',
        'brown': '随机过程，无需连续性',
        'line': '正弦波，保持相位连续',
        'ecg': '心跳周期保持连续',
        'eog': '眨眼状态保持连续',
        'emg': '多频带相位保持连续'
    }
    
    for name, results in all_results.items():
        ind_jump = np.mean(results['independent_jumps'])
        con_jump = np.mean(results['continuous_jumps'])
        if ind_jump > 0:
            improvement = (1 - con_jump / ind_jump) * 100
            print(f"{name.upper():<20} {ind_jump:>15.4f} {con_jump:>15.4f} {improvement:>9.1f}%  {summaries[name]}")
        else:
            print(f"{name.upper():<20} {ind_jump:>15.4f} {con_jump:>15.4f} {'N/A':>10}  {summaries[name]}")
    
    print("=" * 70)
    print(f"\n所有测试图片已保存至: {output_dir}")
    print("\n单个测试文件:")
    print("  - test_pink_noise.py: 粉红噪声")
    print("  - test_brown_noise.py: 布朗噪声")
    print("  - test_line_noise.py: 工频噪声")
    print("  - test_ecg_noise.py: 心电伪迹")
    print("  - test_eog_noise.py: 眼电伪迹")
    print("  - test_emg_noise.py: 肌电伪迹")
    
    return all_results


if __name__ == '__main__':
    import numpy as np  # 需要在主函数中导入用于汇总报告
    
    print("\n EEG Simulator 噪声连续性测试套件 ")
    print("=" * 70)
    print("\n本测试套件验证各类噪声的连续性:")
    print("  1. 粉红噪声: 1/f 随机噪声")
    print("  2. 布朗噪声: 1/f² 随机噪声")
    print("  3. 工频噪声: 50Hz/60Hz 正弦波")
    print("  4. 心电伪迹: ECG 信号")
    print("  5. 眼电伪迹: EOG 眨眼信号")
    print("  6. 肌电伪迹: EMG 高频噪声")
    
    results = run_all_tests()
    
    print("\n" + "=" * 70)
    print(" 所有测试完成! ".center(70, "="))
    print("=" * 70 + "\n")
