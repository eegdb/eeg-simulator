#!/usr/bin/env python
"""
粉红噪声连续性测试

粉红噪声 (Pink Noise / 1/f 噪声) 具有 1/f 频谱特性。
由于是随机过程，不需要跨批次时域连续性。

运行方式:
    python tests/test_noise_continuity/test_pink_noise.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import numpy as np
import matplotlib.pyplot as plt
from eeg_simulator.core.signal_engine import SignalEngine


def test_pink_noise_continuity(
    sampling_rate=1000,
    chunk_duration=0.5,
    n_chunks=10,
    save_path=None
):
    """
    测试粉红噪声连续性
    
    Args:
        sampling_rate: 采样率 (Hz)
        chunk_duration: 每个块的持续时间 (秒)
        n_chunks: 生成的块数
        save_path: 图片保存路径
        
    Returns:
        dict: 测试结果
    """
    print("\n" + "=" * 60)
    print("粉红噪声连续性测试")
    print("=" * 60)
    
    dt = 1.0 / sampling_rate
    n_samples_per_chunk = int(chunk_duration * sampling_rate)
    
    engine = SignalEngine(sampling_rate=sampling_rate)
    noise_config = {'type': 'pink', 'amplitude': 10.0}
    
    total_samples = n_samples_per_chunk * n_chunks
    
    # 方法1: 一次性生成（参考基准 - 最理想情况）
    print("\n[1/2] 一次性生成 (参考基准)...")
    # 一次性生成完整的粉红噪声
    independent_signal = engine._generate_pink_noise(total_samples, 10.0)
    
    # 方法2: 分块连续生成 - 分块但保持状态连续性
    print("[2/2] 分块连续生成 (保持状态)...")
    continuous_signal = []
    state = {}
    for i in range(n_chunks):
        noise = engine._generate_continuous_pink_noise(n_samples_per_chunk, 10.0, state)
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
    
    # 绘制对比图
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    fig.suptitle('Pink Noise Continuity Test', fontsize=14, fontweight='bold')
    
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
    
    # 图3: 边界细节
    ax = axes[2]
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
    freqs, psd_ind = sp_signal.welch(independent_signal, fs=sampling_rate, nperseg=1024)
    freqs, psd_con = sp_signal.welch(continuous_signal, fs=sampling_rate, nperseg=1024)
    
    # 计算1/f特性
    freq_mask = (freqs > 1) & (freqs < 100)
    slope_ind = np.polyfit(np.log10(freqs[freq_mask]), np.log10(psd_ind[freq_mask]), 1)[0]
    slope_con = np.polyfit(np.log10(freqs[freq_mask]), np.log10(psd_con[freq_mask]), 1)[0]
    
    print(f"  独立生成 - 频谱斜率: {slope_ind:.2f} (理想: -1.0)")
    print(f"  连续生成 - 频谱斜率: {slope_con:.2f} (理想: -1.0)")
    
    return {
        'independent': independent_signal,
        'continuous': continuous_signal,
        'independent_jumps': independent_jumps,
        'continuous_jumps': continuous_jumps,
        'spectrum_slope_ind': slope_ind,
        'spectrum_slope_con': slope_con
    }


def main():
    """主函数"""
    output_dir = os.path.join(os.path.dirname(__file__), 'plots')
    os.makedirs(output_dir, exist_ok=True)
    
    results = test_pink_noise_continuity(
        sampling_rate=1000,
        chunk_duration=0.5,
        n_chunks=10,
        save_path=os.path.join(output_dir, 'pink_noise_continuity.png')
    )
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
