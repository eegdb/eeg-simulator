#!/usr/bin/env python
"""
肌电伪迹 (EMG) 连续性测试

EMG噪声模拟肌肉活动产生的高频噪声，包含多频带随机信号和爆发性活动。
需要保持多频带相位和爆发状态的连续性。

运行方式:
    python tests/test_noise_continuity/test_emg_noise.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import numpy as np
import matplotlib.pyplot as plt
from eeg_simulator.core.signal_engine import SignalEngine


def test_emg_noise_continuity(
    sampling_rate=1000,
    chunk_duration=0.5,
    n_chunks=10,
    amplitude=20.0,
    save_path=None
):
    """
    测试EMG噪声连续性
    
    Args:
        sampling_rate: 采样率 (Hz)
        chunk_duration: 每个块的持续时间 (秒)
        n_chunks: 生成的块数
        amplitude: 幅度 (μV)
        save_path: 图片保存路径
        
    Returns:
        dict: 测试结果
    """
    print("\n" + "=" * 60)
    print("肌电伪迹连续性测试")
    print("=" * 60)
    
    dt = 1.0 / sampling_rate
    n_samples_per_chunk = int(chunk_duration * sampling_rate)
    
    engine = SignalEngine(sampling_rate=sampling_rate)
    noise_config = {
        'type': 'emg', 
        'amplitude': amplitude, 
        'cutoff_freq': 200
    }
    
    total_samples = n_samples_per_chunk * n_chunks
    
    # 方法1: 独立生成 - 一次性生成完整信号
    print("\n[1/2] 独立生成 (一次性生成完整信号)...")
    independent_signal = engine.generate_noise(noise_config, total_samples)
    
    # 方法2: 连续生成 - 分块生成，保持相位和爆发状态连续性
    print("[2/2] 连续生成 (分块保持相位和爆发状态)...")
    continuous_signal = []
    state = {}
    for i in range(n_chunks):
        noise = engine.generate_continuous_noise(noise_config, n_samples_per_chunk, dt, state)
        continuous_signal.append(noise)
    continuous_signal = np.concatenate(continuous_signal)
    
    # 计算边界跳跃
    def calculate_boundary_jumps(signal, n_chunks, n_samples_per_chunk):
        jumps = []
        for i in range(1, n_chunks):
            boundary_idx = i * n_samples_per_chunk
            if boundary_idx < len(signal):
                before = np.mean(signal[boundary_idx-5:boundary_idx])
                after = np.mean(signal[boundary_idx:boundary_idx+5])
                jumps.append(abs(after - before))
        return jumps
    
    independent_jumps = calculate_boundary_jumps(independent_signal, n_chunks, n_samples_per_chunk)
    continuous_jumps = calculate_boundary_jumps(continuous_signal, n_chunks, n_samples_per_chunk)
    
    print(f"\n测试结果:")
    print(f"  独立生成 - 边界平均跳跃: {np.mean(independent_jumps):.4f} μV")
    print(f"  连续生成 - 边界平均跳跃: {np.mean(continuous_jumps):.4f} μV")
    
    if np.mean(independent_jumps) > 0:
        improvement = (1 - np.mean(continuous_jumps) / np.mean(independent_jumps)) * 100
        print(f"  连续性改进: {improvement:.1f}%")
    
    # 统计特性
    print(f"\n统计特性:")
    print(f"  独立生成 - 均值: {np.mean(independent_signal):.2f} μV, 标准差: {np.std(independent_signal):.2f} μV")
    print(f"  连续生成 - 均值: {np.mean(continuous_signal):.2f} μV, 标准差: {np.std(continuous_signal):.2f} μV")
    
    # 绘制对比图
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    fig.suptitle('EMG Noise Continuity Test', fontsize=14, fontweight='bold')
    
    total_samples = len(independent_signal)
    t = np.arange(total_samples) * dt
    
    # 图1: 独立生成
    ax = axes[0]
    ax.plot(t, independent_signal, color='#d62728', linewidth=0.8, alpha=0.9)
    for i in range(1, n_chunks):
        ax.axvline(x=i * chunk_duration, color='#ff7f0e', linestyle='--', linewidth=1.5, alpha=0.7)
    ax.set_title(f'Independent Generation - Avg Jump: {np.mean(independent_jumps):.3f} μV', 
                 fontsize=11, color='#d62728')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude (μV)')
    ax.grid(True, alpha=0.3)
    
    # 图2: 连续生成
    ax = axes[1]
    ax.plot(t, continuous_signal, color='#2ca02c', linewidth=0.8, alpha=0.9)
    for i in range(1, n_chunks):
        ax.axvline(x=i * chunk_duration, color='#ff7f0e', linestyle='--', linewidth=1.5, alpha=0.7)
    ax.set_title(f'Continuous Generation - Avg Jump: {np.mean(continuous_jumps):.3f} μV', 
                 fontsize=11, color='#2ca02c')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude (μV)')
    ax.grid(True, alpha=0.3)
    
    # 图3: 边界细节 + 频谱对比
    ax = axes[2]
    
    # 绘制边界细节（左侧Y轴）
    zoom_samples = int(0.05 * n_samples_per_chunk)
    boundary_idx = (n_chunks // 2) * n_samples_per_chunk
    start_idx = max(0, boundary_idx - zoom_samples)
    end_idx = min(total_samples, boundary_idx + zoom_samples)
    
    t_zoom = t[start_idx:end_idx]
    ax.plot(t_zoom, independent_signal[start_idx:end_idx], 
            color='#d62728', linewidth=2, label='Independent', alpha=0.8)
    ax.plot(t_zoom, continuous_signal[start_idx:end_idx], 
            color='#2ca02c', linewidth=2, label='Continuous', alpha=0.8)
    ax.axvline(x=boundary_idx * dt, color='#ff7f0e', linestyle='--', linewidth=2, label='Boundary')
    
    ax.set_title('Boundary Detail (Zoomed)', fontsize=11, fontweight='bold')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude (μV)')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"\n图片已保存: {save_path}")
    else:
        plt.show()
    
    plt.close()
    
    # 频谱对比图
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    
    from scipy import signal as sp_signal
    freqs, psd_ind = sp_signal.welch(independent_signal, fs=sampling_rate, nperseg=1024)
    freqs, psd_con = sp_signal.welch(continuous_signal, fs=sampling_rate, nperseg=1024)
    
    ax.semilogy(freqs[1:], psd_ind[1:], label='Independent', color='#d62728', alpha=0.8)
    ax.semilogy(freqs[1:], psd_con[1:], label='Continuous', color='#2ca02c', alpha=0.8)
    
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('PSD (μV²/Hz)')
    ax.set_title('EMG Power Spectral Density Comparison', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 250)
    
    plt.tight_layout()
    
    if save_path:
        psd_path = save_path.replace('.png', '_psd.png')
        plt.savefig(psd_path, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"频谱图已保存: {psd_path}")
    else:
        plt.show()
    
    plt.close()
    
    return {
        'independent': independent_signal,
        'continuous': continuous_signal,
        'independent_jumps': independent_jumps,
        'continuous_jumps': continuous_jumps
    }


def main():
    """主函数"""
    output_dir = os.path.join(os.path.dirname(__file__), 'plots')
    os.makedirs(output_dir, exist_ok=True)
    
    # 测试EMG连续性
    results = test_emg_noise_continuity(
        sampling_rate=1000,
        chunk_duration=0.5,
        n_chunks=10,
        amplitude=20.0,
        save_path=os.path.join(output_dir, 'emg_noise_continuity.png')
    )
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
