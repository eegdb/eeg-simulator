#!/usr/bin/env python
"""
眼电伪迹 (EOG) 连续性测试

EOG噪声模拟眨眼产生的瞬态干扰，表现为低频双相脉冲信号。
需要保持眨眼周期和基线漂移的连续性。

运行方式:
    python tests/test_noise_continuity/test_eog_noise.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import numpy as np
import matplotlib.pyplot as plt
from eeg_simulator.core.signal_engine import SignalEngine


def test_eog_noise_continuity(
    sampling_rate=1000,
    chunk_duration=0.5,
    n_chunks=10,
    blink_rate=0.5,
    save_path=None
):
    """
    测试EOG噪声连续性
    
    Args:
        sampling_rate: 采样率 (Hz)
        chunk_duration: 每个块的持续时间 (秒)
        n_chunks: 生成的块数
        blink_rate: 眨眼频率 (Hz)
        save_path: 图片保存路径
        
    Returns:
        dict: 测试结果
    """
    print("\n" + "=" * 60)
    print(f"眼电伪迹连续性测试 (眨眼频率: {blink_rate} Hz)")
    print("=" * 60)
    
    dt = 1.0 / sampling_rate
    n_samples_per_chunk = int(chunk_duration * sampling_rate)
    
    engine = SignalEngine(sampling_rate=sampling_rate)
    noise_config = {'type': 'eog', 'amplitude': 100.0, 'blink_rate': blink_rate}
    
    total_samples = n_samples_per_chunk * n_chunks
    
    # 方法1: 独立生成 - 一次性生成完整信号
    print("\n[1/2] 独立生成 (一次性生成完整信号)...")
    independent_signal = engine.generate_noise(noise_config, total_samples)
    
    # 方法2: 连续生成 - 分块生成，保持眨眼状态连续性
    print("[2/2] 连续生成 (分块保持眨眼状态)...")
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
    
    # 绘制对比图
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    fig.suptitle(f'EOG Noise Continuity Test (Blink Rate: {blink_rate} Hz)', 
                 fontsize=14, fontweight='bold')
    
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
    zoom_samples = int(0.1 * n_samples_per_chunk)
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
    else:
        plt.show()
    
    plt.close()
    
    return {
        'independent': independent_signal,
        'continuous': continuous_signal,
        'independent_jumps': independent_jumps,
        'continuous_jumps': continuous_jumps,
        'blink_rate': blink_rate
    }


def test_multiple_blink_rates(save_dir=None):
    """测试多种眨眼频率"""
    if save_dir is None:
        save_dir = os.path.join(os.path.dirname(__file__), 'plots')
    os.makedirs(save_dir, exist_ok=True)
    
    blink_rates = [0.2, 0.5, 1.0, 2.0]
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('EOG Noise - Different Blink Rates', fontsize=14, fontweight='bold')
    
    for idx, br in enumerate(blink_rates):
        ax = axes[idx // 2, idx % 2]
        
        results = test_eog_noise_continuity(
            sampling_rate=1000,
            chunk_duration=0.5,
            n_chunks=4,
            blink_rate=br,
            save_path=None
        )
        
        # 只绘制连续生成的信号
        t = np.arange(len(results['continuous'])) / 1000.0
        ax.plot(t, results['continuous'], color='#8c564b', linewidth=1.2)
        ax.set_title(f'Blink Rate: {br} Hz ({br*60:.0f} BPM)', fontsize=11, fontweight='bold')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude (μV)')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, t[-1])
    
    plt.tight_layout()
    save_path = os.path.join(save_dir, 'eog_multiple_blink_rates.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\n多眨眼频率对比图已保存: {save_path}")
    plt.close()


def main():
    """主函数"""
    output_dir = os.path.join(os.path.dirname(__file__), 'plots')
    os.makedirs(output_dir, exist_ok=True)
    
    # 单一眨眼频率测试
    results = test_eog_noise_continuity(
        sampling_rate=1000,
        chunk_duration=0.5,
        n_chunks=10,
        blink_rate=0.5,
        save_path=os.path.join(output_dir, 'eog_noise_continuity.png')
    )
    
    # 多眨眼频率对比
    print("\n" + "=" * 60)
    print("生成多眨眼频率对比图...")
    test_multiple_blink_rates(output_dir)
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
