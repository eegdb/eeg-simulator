#!/usr/bin/env python
"""
噪声连续性测试 - 验证噪声生成在不同批次间的连续性

运行方式:
    python tests/run_noise_continuity_overview.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib.pyplot as plt
from eeg_simulator.core.signal_engine import SignalEngine


def test_noise_continuity(noise_type, noise_config, sampling_rate=1000, chunk_duration=0.5, n_chunks=10):
    """
    测试噪声连续性 - 比较连续生成 vs 独立生成
    
    Args:
        noise_type: 噪声类型名称
        noise_config: 噪声配置字典
        sampling_rate: 采样率
        chunk_duration: 每个块的持续时间（秒）
        n_chunks: 生成的块数
        
    Returns:
        dict: 包含测试结果和生成的信号
    """
    print(f"\n测试噪声类型: {noise_type}")
    print("-" * 60)
    
    dt = 1.0 / sampling_rate
    n_samples_per_chunk = int(chunk_duration * sampling_rate)
    
    engine = SignalEngine(sampling_rate=sampling_rate)
    
    # 方法1: 独立生成（不连续）- 每次重新生成，没有状态保存
    independent_signal = []
    for i in range(n_chunks):
        noise = engine.generate_noise(noise_config, n_samples_per_chunk)
        independent_signal.append(noise)
    independent_signal = np.concatenate(independent_signal)
    
    # 方法2: 连续生成 - 使用状态保持连续性
    continuous_signal = []
    state = {}
    for i in range(n_chunks):
        noise = engine.generate_continuous_noise(noise_config, n_samples_per_chunk, dt, state)
        continuous_signal.append(noise)
    continuous_signal = np.concatenate(continuous_signal)
    
    # 方法3: 一次性生成完整的参考信号
    total_samples = n_samples_per_chunk * n_chunks
    reference_signal = engine.generate_noise(noise_config, total_samples)
    
    # 分析连续性 - 计算块边界的跳跃
    def calculate_boundary_jumps(signal, n_chunks, n_samples_per_chunk):
        """计算每个块边界的信号跳跃（不连续程度）"""
        jumps = []
        for i in range(1, n_chunks):
            boundary_idx = i * n_samples_per_chunk
            if boundary_idx < len(signal):
                # 计算边界前后5个样本的平均差值
                before = np.mean(signal[boundary_idx-5:boundary_idx])
                after = np.mean(signal[boundary_idx:boundary_idx+5])
                jumps.append(abs(after - before))
        return jumps
    
    independent_jumps = calculate_boundary_jumps(independent_signal, n_chunks, n_samples_per_chunk)
    continuous_jumps = calculate_boundary_jumps(continuous_signal, n_chunks, n_samples_per_chunk)
    
    print(f"  独立生成 - 边界平均跳跃: {np.mean(independent_jumps):.4f} μV")
    print(f"  连续生成 - 边界平均跳跃: {np.mean(continuous_jumps):.4f} μV")
    
    # 计算改进比例
    if np.mean(independent_jumps) > 0:
        improvement = (1 - np.mean(continuous_jumps) / np.mean(independent_jumps)) * 100
        print(f"  连续性改进: {improvement:.1f}%")
    
    return {
        'independent': independent_signal,
        'continuous': continuous_signal,
        'reference': reference_signal,
        'independent_jumps': independent_jumps,
        'continuous_jumps': continuous_jumps,
        'dt': dt,
        'n_chunks': n_chunks,
        'n_samples_per_chunk': n_samples_per_chunk
    }


def plot_continuity_comparison(results, noise_type, save_path=None):
    """
    绘制连续性对比图
    
    Args:
        results: test_noise_continuity 返回的结果字典
        noise_type: 噪声类型名称
        save_path: 图片保存路径
    """
    independent = results['independent']
    continuous = results['continuous']
    n_chunks = results['n_chunks']
    n_samples_per_chunk = results['n_samples_per_chunk']
    dt = results['dt']
    
    total_samples = len(independent)
    t = np.arange(total_samples) * dt
    
    # 创建图形
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    fig.suptitle(f'Noise Continuity Test: {noise_type}', fontsize=14, fontweight='bold')
    
    # 颜色方案
    color_independent = '#d62728'  # 红色 - 独立生成
    color_continuous = '#2ca02c'   # 绿色 - 连续生成
    color_boundary = '#ff7f0e'     # 橙色 - 边界标记
    
    # 图1: 独立生成（不连续）
    ax = axes[0]
    ax.plot(t, independent, color=color_independent, linewidth=0.8, alpha=0.9, label='Independent Generation')
    
    # 标记边界
    for i in range(1, n_chunks):
        boundary_t = i * n_samples_per_chunk * dt
        ax.axvline(x=boundary_t, color=color_boundary, linestyle='--', linewidth=1.5, alpha=0.7)
    
    ax.set_title(f'Independent Generation (Discontinuous) - Avg Jump: {np.mean(results["independent_jumps"]):.3f} μV', 
                 fontsize=11, color=color_independent)
    ax.set_xlabel('Time (s)', fontsize=10)
    ax.set_ylabel('Amplitude (μV)', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle=':')
    ax.set_xlim(0, t[-1])
    
    # 图2: 连续生成
    ax = axes[1]
    ax.plot(t, continuous, color=color_continuous, linewidth=0.8, alpha=0.9, label='Continuous Generation')
    
    # 标记边界
    for i in range(1, n_chunks):
        boundary_t = i * n_samples_per_chunk * dt
        ax.axvline(x=boundary_t, color=color_boundary, linestyle='--', linewidth=1.5, alpha=0.7)
    
    ax.set_title(f'Continuous Generation - Avg Jump: {np.mean(results["continuous_jumps"]):.3f} μV', 
                 fontsize=11, color=color_continuous)
    ax.set_xlabel('Time (s)', fontsize=10)
    ax.set_ylabel('Amplitude (μV)', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle=':')
    ax.set_xlim(0, t[-1])
    
    # 图3: 叠加对比 - 只看边界区域
    ax = axes[2]
    
    # 选择几个边界区域放大显示
    zoom_window = int(0.05 * n_samples_per_chunk)  # 边界前后5%的窗口
    boundary_idx = (n_chunks // 2) * n_samples_per_chunk  # 选择中间的边界
    
    start_idx = max(0, boundary_idx - zoom_window)
    end_idx = min(total_samples, boundary_idx + zoom_window)
    
    t_zoom = t[start_idx:end_idx]
    
    ax.plot(t_zoom, independent[start_idx:end_idx], 
            color=color_independent, linewidth=2, alpha=0.8, label='Independent')
    ax.plot(t_zoom, continuous[start_idx:end_idx], 
            color=color_continuous, linewidth=2, alpha=0.8, label='Continuous')
    
    # 标记边界线
    boundary_t = boundary_idx * dt
    ax.axvline(x=boundary_t, color=color_boundary, linestyle='--', linewidth=2, alpha=0.9, label='Boundary')
    
    ax.set_title(f'Boundary Detail (Zoomed)', fontsize=11, fontweight='bold')
    ax.set_xlabel('Time (s)', fontsize=10)
    ax.set_ylabel('Amplitude (μV)', fontsize=10)
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle=':')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"  图片已保存: {save_path}")
    else:
        plt.show()
    
    plt.close()


def run_all_continuity_tests(save_dir=None):
    """
    运行所有噪声类型的连续性测试
    
    Args:
        save_dir: 图片保存目录
    """
    if save_dir is None:
        save_dir = os.path.join(os.path.dirname(__file__), 'noise_plots', 'continuity')
    os.makedirs(save_dir, exist_ok=True)
    
    print("\n" + "=" * 70)
    print(" EEG Simulator - Noise Continuity Test ".center(70, "="))
    print("=" * 70)
    print("\n本测试比较两种噪声生成方式:")
    print("  1. 独立生成: 每次调用重新生成，无状态保持")
    print("  2. 连续生成: 使用状态保持跨批次连续性")
    print("\n测试方法:")
    print("  - 将信号分成多个小块 (chunks)")
    print("  - 分别用两种方式生成")
    print("  - 比较块边界的信号跳跃程度")
    print("  - 跳跃越小表示连续性越好")
    
    # 定义要测试的噪声类型
    test_cases = [
        {
            'name': 'Pink Noise',
            'type': 'pink',
            'config': {'type': 'pink', 'amplitude': 10.0}
        },
        {
            'name': 'Brown Noise',
            'type': 'brown',
            'config': {'type': 'brown', 'amplitude': 10.0}
        },
        {
            'name': 'Line Noise (50Hz)',
            'type': 'line',
            'config': {'type': 'line', 'amplitude': 10.0, 'line_freq': 50}
        },
        {
            'name': 'ECG (60 BPM)',
            'type': 'ecg',
            'config': {'type': 'ecg', 'amplitude': 50.0, 'heart_rate': 60}
        },
        {
            'name': 'EOG (0.5Hz blink)',
            'type': 'eog',
            'config': {'type': 'eog', 'amplitude': 100.0, 'blink_rate': 0.5}
        },
        {
            'name': 'EMG',
            'type': 'emg',
            'config': {'type': 'emg', 'amplitude': 20.0, 'cutoff_freq': 200}
        },
    ]
    
    all_results = {}
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] ", end="")
        
        # 运行测试
        results = test_noise_continuity(
            noise_type=test_case['name'],
            noise_config=test_case['config'],
            sampling_rate=1000,
            chunk_duration=0.5,  # 每块0.5秒
            n_chunks=10          # 共10块，5秒总时长
        )
        
        all_results[test_case['name']] = results
        
        # 绘制对比图
        save_path = os.path.join(save_dir, f'continuity_{test_case["type"]}.png')
        plot_continuity_comparison(results, test_case['name'], save_path)
    
    # 生成汇总报告
    print("\n" + "=" * 70)
    print(" 连续性测试汇总 ".center(70, "="))
    print("=" * 70)
    print(f"{'噪声类型':<25} {'独立生成跳跃':>15} {'连续生成跳跃':>15} {'改进':>10}")
    print("-" * 70)
    
    for name, results in all_results.items():
        ind_jump = np.mean(results['independent_jumps'])
        con_jump = np.mean(results['continuous_jumps'])
        if ind_jump > 0:
            improvement = (1 - con_jump / ind_jump) * 100
            print(f"{name:<25} {ind_jump:>15.4f} {con_jump:>15.4f} {improvement:>9.1f}%")
        else:
            print(f"{name:<25} {ind_jump:>15.4f} {con_jump:>15.4f} {'N/A':>10}")
    
    print("=" * 70)
    print(f"\n所有测试图片已保存至: {save_dir}")
    
    return all_results


def main():
    """主函数"""
    # 运行所有测试
    results = run_all_continuity_tests()
    
    print("\n" + "=" * 70)
    print(" 测试完成! ".center(70, "="))
    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()
