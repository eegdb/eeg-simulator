#!/usr/bin/env python
"""
心电伪迹 (ECG) 连续性测试

ECG噪声模拟心电信号，包含P波、QRS波群、T波。
需要保持心跳周期连续性以避免波形断裂。

运行方式:
    python tests/test_noise_continuity/test_ecg_noise.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import numpy as np
import matplotlib.pyplot as plt
from eeg_simulator.core.signal_engine import SignalEngine


def test_ecg_noise_continuity(
    sampling_rate=1000,
    chunk_duration=0.5,
    n_chunks=10,
    heart_rate=60,
    save_path=None
):
    """
    测试ECG噪声连续性
    
    Args:
        sampling_rate: 采样率 (Hz)
        chunk_duration: 每个块的持续时间 (秒)
        n_chunks: 生成的块数
        heart_rate: 心率 (BPM)
        save_path: 图片保存路径
        
    Returns:
        dict: 测试结果
    """
    print("\n" + "=" * 60)
    print(f"心电伪迹连续性测试 (心率: {heart_rate} BPM)")
    print("=" * 60)
    
    dt = 1.0 / sampling_rate
    n_samples_per_chunk = int(chunk_duration * sampling_rate)
    
    engine = SignalEngine(sampling_rate=sampling_rate)
    noise_config = {'type': 'ecg', 'amplitude': 50.0, 'heart_rate': heart_rate}
    
    total_samples = n_samples_per_chunk * n_chunks
    
    # 方法1: 独立生成 - 一次性生成完整信号
    print("\n[1/2] 独立生成 (一次性生成完整信号)...")
    independent_signal = engine.generate_noise(noise_config, total_samples)
    
    # 方法2: 连续生成 - 分块生成，保持心跳周期连续性
    print("[2/2] 连续生成 (分块保持心跳周期)...")
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
    
    # 计算心跳周期
    beat_interval = 60.0 / heart_rate
    
    # 绘制对比图
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    fig.suptitle(f'ECG Noise Continuity Test ({heart_rate} BPM)', fontsize=14, fontweight='bold')
    
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
    
    # 图3: 边界细节 - 单心跳周期
    ax = axes[2]
    period_samples = int(sampling_rate * beat_interval)
    boundary_idx = (n_chunks // 2) * n_samples_per_chunk
    start_idx = max(0, boundary_idx - period_samples // 4)
    end_idx = min(total_samples, boundary_idx + period_samples * 3 // 4)
    
    t_zoom = t[start_idx:end_idx]
    ax.plot(t_zoom, independent_signal[start_idx:end_idx], 
            color='#d62728', linewidth=2, label='Independent', alpha=0.8)
    ax.plot(t_zoom, continuous_signal[start_idx:end_idx], 
            color='#2ca02c', linewidth=2, label='Continuous', alpha=0.8)
    ax.axvline(x=boundary_idx * dt, color='#ff7f0e', linestyle='--', linewidth=2, label='Boundary')
    
    ax.set_title('Single Heartbeat at Boundary (Zoomed)', fontsize=11, fontweight='bold')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude (μV)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"\n图片已保存: {save_path}")
    
    plt.close()
    
    # 频谱分析
    print("\n频谱特性:")
    from scipy import signal as sp_signal
    freqs, psd = sp_signal.welch(continuous_signal, fs=sampling_rate, nperseg=1024)
    
    # 查找心率对应的频率峰值
    hr_freq = heart_rate / 60.0
    freq_idx = np.argmin(np.abs(freqs - hr_freq))
    print(f"  心率频率: {hr_freq:.2f} Hz")
    print(f"  频谱峰值位置: {freqs[freq_idx]:.2f} Hz")
    
    return {
        'independent': independent_signal,
        'continuous': continuous_signal,
        'independent_jumps': independent_jumps,
        'continuous_jumps': continuous_jumps,
        'heart_rate': heart_rate
    }


def test_multiple_heart_rates(save_dir=None):
    """测试多种心率"""
    if save_dir is None:
        save_dir = os.path.join(os.path.dirname(__file__), 'plots')
    os.makedirs(save_dir, exist_ok=True)
    
    heart_rates = [50, 60, 80, 100]
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('ECG Noise - Different Heart Rates', fontsize=14, fontweight='bold')
    
    for idx, hr in enumerate(heart_rates):
        ax = axes[idx // 2, idx % 2]
        
        results = test_ecg_noise_continuity(
            sampling_rate=1000,
            chunk_duration=0.3,
            n_chunks=3,
            heart_rate=hr,
            save_path=None
        )
        
        # 只绘制连续生成的信号
        t = np.arange(len(results['continuous'])) / 1000.0
        ax.plot(t, results['continuous'], color='#9467bd', linewidth=1.2)
        ax.set_title(f'{hr} BPM', fontsize=11, fontweight='bold')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude (μV)')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, t[-1])
    
    plt.tight_layout()
    save_path = os.path.join(save_dir, 'ecg_multiple_heart_rates.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\n多心率对比图已保存: {save_path}")
    plt.close()


def main():
    """主函数"""
    output_dir = os.path.join(os.path.dirname(__file__), 'plots')
    os.makedirs(output_dir, exist_ok=True)
    
    # 单一心率测试
    results = test_ecg_noise_continuity(
        sampling_rate=1000,
        chunk_duration=0.5,
        n_chunks=10,
        heart_rate=60,
        save_path=os.path.join(output_dir, 'ecg_noise_continuity.png')
    )
    
    # 多心率对比
    print("\n" + "=" * 60)
    print("生成多心率对比图...")
    test_multiple_heart_rates(output_dir)
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
