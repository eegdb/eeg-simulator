#!/usr/bin/env python
"""
噪声可视化测试 - 生成并绘制所有类型的噪声波形

运行方式:
    python tests/test_noise_visualization.py
    
或:
    python -m pytest tests/test_noise_visualization.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib.pyplot as plt
from eeg_simulator.core.signal_engine import SignalEngine


def plot_all_noises(duration=5.0, sampling_rate=1000, save_path=None):
    """
    生成并绘制所有类型的噪声波形
    
    Args:
        duration: 信号时长（秒）
        sampling_rate: 采样率（Hz）
        save_path: 图片保存路径，为None则显示图形
    """
    n_samples = int(duration * sampling_rate)
    engine = SignalEngine(sampling_rate=sampling_rate)
    
    # 时间轴
    t = np.arange(n_samples) / sampling_rate
    
    # 定义所有噪声配置
    noise_configs = [
        {
            'name': 'White Noise',
            'type': 'white',
            'config': {'type': 'white', 'amplitude': 10.0, 'cutoff_freq': 100},
            'color': '#1f77b4'
        },
        {
            'name': 'Pink Noise (1/f)',
            'type': 'pink',
            'config': {'type': 'pink', 'amplitude': 10.0},
            'color': '#ff7f0e'
        },
        {
            'name': 'Brown Noise (1/f²)',
            'type': 'brown',
            'config': {'type': 'brown', 'amplitude': 10.0},
            'color': '#2ca02c'
        },
        {
            'name': 'Line Noise (50Hz)',
            'type': 'line',
            'config': {'type': 'line', 'amplitude': 10.0, 'line_freq': 50},
            'color': '#d62728'
        },
        {
            'name': 'ECG (60 BPM)',
            'type': 'ecg',
            'config': {'type': 'ecg', 'amplitude': 50.0, 'heart_rate': 60},
            'color': '#9467bd'
        },
        {
            'name': 'EOG (0.5Hz blink)',
            'type': 'eog',
            'config': {'type': 'eog', 'amplitude': 100.0, 'blink_rate': 0.5},
            'color': '#8c564b'
        },
        {
            'name': 'EMG',
            'type': 'emg',
            'config': {'type': 'emg', 'amplitude': 20.0, 'cutoff_freq': 200},
            'color': '#e377c2'
        },
        {
            'name': '1/f Noise (α=1.5)',
            'type': '1f',
            'config': {'type': '1f', 'amplitude': 10.0, 'exponent': 1.5},
            'color': '#7f7f7f'
        }
    ]
    
    # 生成所有噪声
    print("=" * 60)
    print("生成噪声波形...")
    print("=" * 60)
    
    noise_data = {}
    for item in noise_configs:
        noise = engine.generate_noise(item['config'], n_samples)
        noise_data[item['name']] = noise
        print(f"\n{item['name']}:")
        print(f"  类型: {item['type']}")
        print(f"  幅度: {item['config']['amplitude']} μV")
        print(f"  均值: {np.mean(noise):.3f} μV")
        print(f"  标准差: {np.std(noise):.3f} μV")
        print(f"  范围: [{np.min(noise):.2f}, {np.max(noise):.2f}] μV")
    
    # 创建图形
    fig = plt.figure(figsize=(16, 12))
    fig.suptitle('EEG Simulator - Noise Types Visualization', fontsize=16, fontweight='bold')
    
    # 布局：4行2列（时域波形）+ 1行2列（频谱对比）
    gs = fig.add_gridspec(5, 2, height_ratios=[1, 1, 1, 1, 1], hspace=0.4, wspace=0.3)
    
    axes_wave = []
    for i in range(4):
        for j in range(2):
            idx = i * 2 + j
            if idx < len(noise_configs):
                ax = fig.add_subplot(gs[i, j])
                axes_wave.append(ax)
    
    # 绘制时域波形
    for idx, (item, (name, noise)) in enumerate(zip(noise_configs, noise_data.items())):
        ax = axes_wave[idx]
        
        # 绘制波形
        ax.plot(t, noise, color=item['color'], linewidth=0.8, alpha=0.8)
        
        # 添加零线
        ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        
        # 设置标题和标签
        ax.set_title(f'{name}\n(σ={np.std(noise):.2f} μV)', fontsize=10, fontweight='bold')
        ax.set_xlabel('Time (s)', fontsize=9)
        ax.set_ylabel('Amplitude (μV)', fontsize=9)
        ax.grid(True, alpha=0.3, linestyle=':')
        
        # 自动调整Y轴范围
        y_margin = np.std(noise) * 3
        ax.set_ylim(-y_margin, y_margin)
        ax.set_xlim(0, duration)
    
    # 频谱对比图（最后两行合并）
    ax_psd = fig.add_subplot(gs[4, :])
    
    print("\n" + "=" * 60)
    print("计算功率谱密度...")
    print("=" * 60)
    
    for item in noise_configs:
        name = item['name']
        noise = noise_data[name]
        
        # 计算PSD
        from scipy import signal as sp_signal
        freqs, psd = sp_signal.welch(noise, fs=sampling_rate, nperseg=1024, noverlap=512)
        
        # 绘制PSD（对数坐标）
        ax_psd.semilogy(freqs[1:], psd[1:], label=name, color=item['color'], linewidth=1.5, alpha=0.8)
    
    ax_psd.set_xlabel('Frequency (Hz)', fontsize=10)
    ax_psd.set_ylabel('PSD (μV²/Hz)', fontsize=10)
    ax_psd.set_title('Power Spectral Density Comparison', fontsize=11, fontweight='bold')
    ax_psd.legend(loc='upper right', fontsize=8, ncol=2)
    ax_psd.grid(True, alpha=0.3, linestyle=':')
    ax_psd.set_xlim(0, min(200, sampling_rate / 2))
    
    plt.tight_layout()
    
    # 保存或显示
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"\n图片已保存至: {save_path}")
    else:
        plt.show()
    
    plt.close()
    
    return noise_data


def plot_noise_comparison(detailed=False, save_path=None):
    """
    生成噪声对比图 - 重点展示生理噪声特征
    
    Args:
        detailed: 是否生成详细对比图（ECG/EOG/EMG 单独大图）
        save_path: 图片保存路径
    """
    sampling_rate = 1000
    duration = 3.0  # 较短时长以便观察细节
    n_samples = int(duration * sampling_rate)
    t = np.arange(n_samples) / sampling_rate
    engine = SignalEngine(sampling_rate=sampling_rate)
    
    if detailed:
        # 详细对比图：ECG、EOG、EMG 各参数变化
        fig, axes = plt.subplots(3, 2, figsize=(14, 10))
        fig.suptitle('Physiological Noise Details', fontsize=14, fontweight='bold')
        
        # ECG - 不同心率
        ax = axes[0, 0]
        for hr, color in [(50, '#1f77b4'), (60, '#ff7f0e'), (80, '#2ca02c'), (100, '#d62728')]:
            ecg = engine.generate_noise({'type': 'ecg', 'amplitude': 50, 'heart_rate': hr}, n_samples)
            ax.plot(t, ecg, label=f'HR={hr} BPM', color=color, linewidth=1, alpha=0.8)
        ax.set_title('ECG - Different Heart Rates', fontweight='bold')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude (μV)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 2)  # 只看前2秒
        
        # ECG - 单周期放大
        ax = axes[0, 1]
        ecg = engine.generate_noise({'type': 'ecg', 'amplitude': 50, 'heart_rate': 60}, sampling_rate)
        t_single = np.arange(sampling_rate) / sampling_rate
        ax.plot(t_single, ecg, color='#9467bd', linewidth=2)
        ax.set_title('ECG - Single Beat (60 BPM)', fontweight='bold')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude (μV)')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 1)
        
        # EOG - 不同眨眼频率
        ax = axes[1, 0]
        for br, color in [(0.2, '#1f77b4'), (0.5, '#ff7f0e'), (1.0, '#2ca02c')]:
            eog = engine.generate_noise({'type': 'eog', 'amplitude': 100, 'blink_rate': br}, n_samples)
            ax.plot(t, eog, label=f'Blink={br} Hz', color=color, linewidth=1, alpha=0.8)
        ax.set_title('EOG - Different Blink Rates', fontweight='bold')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude (μV)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # EOG - 单眨眼放大
        ax = axes[1, 1]
        eog = engine.generate_noise({'type': 'eog', 'amplitude': 100, 'blink_rate': 1}, int(2 * sampling_rate))
        t_blink = np.arange(len(eog)) / sampling_rate
        ax.plot(t_blink, eog, color='#8c564b', linewidth=2)
        ax.set_title('EOG - Blink Detail', fontweight='bold')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude (μV)')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 1.5)
        
        # EMG - 不同幅度和截止频率
        ax = axes[2, 0]
        for (amp, cf), color in [((20, 100), '#1f77b4'), ((30, 150), '#ff7f0e'), ((40, 200), '#2ca02c')]:
            emg = engine.generate_noise({'type': 'emg', 'amplitude': amp, 'cutoff_freq': cf}, n_samples)
            ax.plot(t, emg, label=f'Amp={amp}μV, CF={cf}Hz', color=color, linewidth=0.8, alpha=0.8)
        ax.set_title('EMG - Different Parameters', fontweight='bold')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude (μV)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # EMG - 频谱对比
        ax = axes[2, 1]
        from scipy import signal as sp_signal
        for (amp, cf), color in [((20, 100), '#1f77b4'), ((30, 150), '#ff7f0e'), ((40, 200), '#2ca02c')]:
            emg = engine.generate_noise({'type': 'emg', 'amplitude': amp, 'cutoff_freq': cf}, n_samples)
            freqs, psd = sp_signal.welch(emg, fs=sampling_rate, nperseg=512)
            ax.semilogy(freqs[1:], psd[1:], label=f'CF={cf}Hz', color=color, linewidth=1.5)
        ax.set_title('EMG - PSD Comparison', fontweight='bold')
        ax.set_xlabel('Frequency (Hz)')
        ax.set_ylabel('PSD (μV²/Hz)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 250)
        
        plt.tight_layout()
        
        if save_path:
            path_detailed = save_path.replace('.png', '_detailed.png')
            plt.savefig(path_detailed, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"详细对比图已保存至: {path_detailed}")
        else:
            plt.show()
        
        plt.close()


def main():
    """主函数 - 运行所有可视化测试"""
    print("\n" + "=" * 70)
    print(" EEG Simulator - Noise Visualization Test ".center(70, "="))
    print("=" * 70 + "\n")
    
    # 创建输出目录
    output_dir = os.path.join(os.path.dirname(__file__), 'noise_plots')
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 生成所有噪声总览图
    print("\n[1/2] 生成噪声总览图...")
    save_path = os.path.join(output_dir, 'noise_overview.png')
    noise_data = plot_all_noises(duration=5.0, sampling_rate=1000, save_path=save_path)
    
    # 2. 生成详细对比图
    print("\n[2/2] 生成生理噪声详细对比图...")
    save_path_detailed = os.path.join(output_dir, 'noise_detailed.png')
    plot_noise_comparison(detailed=True, save_path=save_path_detailed)
    
    print("\n" + "=" * 70)
    print(" 测试完成！ ".center(70, "="))
    print(f" 输出目录: {output_dir} ".center(70))
    print("=" * 70 + "\n")
    
    return noise_data


if __name__ == '__main__':
    main()
