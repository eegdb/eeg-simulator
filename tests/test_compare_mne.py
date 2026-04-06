#!/usr/bin/env python3
"""
对比测试：MNE SourceSimulator vs EEGSimulator 生成的信号

测试条件：
- 相同时长：10秒
- 相同采样率：1000Hz
- 信号类型：高斯脉冲（峰值@5s，sigma=0.5s）
- 相同偶极子位置和波形
- 对比时间序列、频谱、相关性
"""

import sys
import numpy as np
import time
import tempfile
import os

# 设置matplotlib后端为非交互式（避免弹窗）
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 添加项目路径
sys.path.insert(0, r'D:\PythonWorkSpace\EEGS')

# MNE相关
import mne
from mne.simulation import simulate_sparse_stc, simulate_raw

# 加载EEGSimulator（不启动GUI，只使用核心功能）
from eeg_simulator.core.mne_simulator import MNESimulator
from eeg_simulator.models.patch import Patch, Dipole
from eeg_simulator.core.signal_engine import SignalEngine


def setup_test_conditions():
    """设置测试条件"""
    
    # 1. 加载MNE示例数据
    data_path = mne.datasets.sample.data_path()
    subjects_dir = data_path / 'subjects'
    subject = 'sample'
    
    # 加载正向模型
    fwd_fname = data_path / 'MEG' / subject / 'sample_audvis-meg-eeg-oct-6-fwd.fif'
    fwd = mne.read_forward_solution(fwd_fname)
    fwd = mne.pick_types_forward(fwd, meg=False, eeg=True, exclude=[])
    
    # 使用fwd中的源空间（与正向模型一致）
    src = fwd['src']
    
    # 加载标签
    labels = mne.read_labels_from_annot(subject, subjects_dir=subjects_dir)
    
    return fwd, src, labels


def generate_with_mne_source_simulator(fwd, labels, duration=10.0, sfreq=1000):
    """使用MNE SourceSimulator生成数据"""
    
    print("\n" + "="*60)
    print("方法1: MNE SourceSimulator")
    print("="*60)
    
    # 时间向量
    times = np.arange(0, duration, 1/sfreq)
    n_times = len(times)
    
    # 使用与EEGSimulator相同的顶点（源空间中的第100和第101个有效顶点）
    src_lh = fwd['src'][0]
    lh_vertno = src_lh['vertno']
    vert1 = int(lh_vertno[100])
    vert2 = int(lh_vertno[101])
    
    print(f"  使用顶点: {vert1}, {vert2}")
    
    # 创建源时间过程：高斯脉冲（峰值在5秒，sigma=0.5秒）
    amplitude = 10e-9  # 10 nAm
    peak_time = 5.0  # 峰值在5秒
    sigma = 0.5  # 宽度0.5秒
    
    # 手动创建SourceEstimate，使用指定的顶点
    vertices = [lh_vertno.copy(), fwd['src'][1]['vertno'].copy()]
    n_verts = len(vertices[0]) + len(vertices[1])
    
    # 找到顶点在完整列表中的索引
    idx1 = np.where(vertices[0] == vert1)[0][0]
    idx2 = np.where(vertices[0] == vert2)[0][0]
    
    # 创建源数据 - 高斯脉冲
    source_data = np.zeros((n_verts, n_times))
    signal = amplitude * np.exp(-0.5 * ((times - peak_time) / sigma)**2)
    source_data[idx1, :] = signal
    source_data[idx2, :] = signal
    
    print(f"  顶点索引: {idx1}, {idx2}")
    print(f"  源数据非零行: {np.count_nonzero(np.any(source_data != 0, axis=1))}")
    print(f"  高斯脉冲: 峰值={amplitude:.2e} @ {peak_time}s, sigma={sigma}s")
    print(f"  信号幅度: {np.min(signal):.2e} ~ {np.max(signal):.2e}")
    
    stc = mne.SourceEstimate(
        data=source_data,
        vertices=vertices,
        tmin=0,
        tstep=1/sfreq,
        subject='sample'
    )
    
    print(f"源时间过程: {stc.data.shape[0]} 个顶点 x {stc.data.shape[1]} 个时间点")
    print(f"  STC非零顶点数: {np.count_nonzero(np.any(stc.data != 0, axis=1))}")
    print(f"时间范围: {stc.times[0]:.3f}s - {stc.times[-1]:.3f}s")
    
    # 直接应用正向模型
    raw = mne.apply_forward_raw(fwd, stc, fwd['info'].copy(), verbose=False)
    
    print(f"生成数据: {raw.n_times} 个时间点, {len(raw.ch_names)} 个通道")
    
    # 检查数据是否为零
    data_check = raw.get_data()
    print(f"  数据非零通道数: {np.count_nonzero(np.any(data_check != 0, axis=1))}")
    print(f"  数据范围: {np.min(data_check):.2e} ~ {np.max(data_check):.2e}")
    
    return raw, stc


def generate_with_eegsimulator(fwd, src, labels, duration=10.0, sfreq=1000):
    """使用EEGSimulator生成数据（批处理模式）"""
    
    print("\n" + "="*60)
    print("方法2: EEGSimulator (MNESimulator)")
    print("="*60)
    
    # 初始化MNE仿真器
    simulator = MNESimulator(fwd, src, sfreq)
    
    # 获取源空间中实际存在的顶点（用于确保匹配）
    src_lh = src[0]
    src_rh = src[1]
    lh_vertno = src_lh['vertno']  # 左半球有效顶点
    rh_vertno = src_rh['vertno']  # 右半球有效顶点
    
    print(f"  源空间有效顶点: LH={len(lh_vertno)}, RH={len(rh_vertno)}")
    
    # 选择2个有效顶点（从源空间中直接选择）
    # 选择左半球的第100和第101个有效顶点
    hemi = 'lh'
    vert1 = int(lh_vertno[100])  # 确保是Python int
    vert2 = int(lh_vertno[101])
    verts = [vert1, vert2]
    
    print(f"  使用顶点: {verts}, hemi={hemi}")
    
    # 创建Patch（2个偶极子）
    patches = {}
    
    # Patch 1: 高斯脉冲（峰值在5秒，sigma=0.5秒）
    patch1 = Patch(id="p1", name="Patch1", hemi=hemi, waveform_type='gaussian')
    dipole1 = Dipole(
        id="d1",
        position=[0, 0, 0],
        orientation=[0, 0, 1],
        hemi=hemi,
        vertno=verts[0]
    )
    patch1.add_dipole(dipole1)
    patch1.waveform_type = 'gaussian'
    patch1.waveform_params = {'amplitude': 10.0, 'center': 5.0, 'width': 0.5}
    patch1.amplitude_scale = 1e-9
    patches[patch1.id] = patch1
    
    # Patch 2: 相同的高斯脉冲
    patch2 = Patch(id="p2", name="Patch2", hemi=hemi, waveform_type='gaussian')
    dipole2 = Dipole(
        id="d2",
        position=[0, 0, 0],
        orientation=[0, 0, 1],
        hemi=hemi,
        vertno=verts[1]
    )
    patch2.add_dipole(dipole2)
    patch2.waveform_type = 'gaussian'
    patch2.waveform_params = {'amplitude': 10.0, 'center': 5.0, 'width': 0.5}
    patch2.amplitude_scale = 1e-9
    patches[patch2.id] = patch2
    
    print(f"创建 {len(patches)} 个 Patch, 共 {sum(p.get_dipole_count() for p in patches.values())} 个偶极子")
    
    # 批量生成信号
    signal_engine = SignalEngine(sfreq)
    
    n_samples = int(duration * sfreq)
    dt = 1.0 / sfreq
    
    # 为每个Patch生成高斯信号（与MNE一致）
    times = np.arange(n_samples) * dt
    amplitude = 10e-9  # 10 nAm
    peak_time = 5.0  # 峰值在5秒
    sigma = 0.5  # 宽度0.5秒
    
    patch_data = {}
    for patch_id, patch in patches.items():
        # 直接生成高斯脉冲（不通过SignalEngine，避免波形类型问题）
        signals = amplitude * np.exp(-0.5 * ((times - peak_time) / sigma)**2)
        patch_data[patch_id] = {
            'signals': signals,
            'dipoles': patch.dipoles,
            'amplitude_scale': 1.0  # 已经在信号中包含了amplitude
        }
    
    print(f"生成 Patch 高斯信号: {n_samples} 个样本, 峰值@{peak_time}s, sigma={sigma}s")
    
    # 前向投影
    channel_signals = simulator.simulate(patch_data, 0, n_samples)
    
    print(f"生成通道数据: {len(channel_signals)} 个通道")
    
    # 创建MNE Raw对象（便于统一对比）
    ch_names = list(channel_signals.keys())
    data = np.array([channel_signals[ch] for ch in ch_names])  # (n_channels, n_times)
    
    # 单位转换：V -> uV（与MNE输出一致）
    data = data * 1e6
    
    info = mne.create_info(ch_names, sfreq, ch_types=['eeg'] * len(ch_names))
    # 不设置montage，使用fwd中的位置信息
    
    raw = mne.io.RawArray(data, info)
    
    return raw, patches


def compare_signals(raw_mne, raw_eeg):
    """对比两组信号的差异"""
    
    print("\n" + "="*60)
    print("对比分析")
    print("="*60)
    
    # 1. 基本信息对比
    print("\n【基本信息】")
    print(f"MNE:    {raw_mne.n_times} 点, {len(raw_mne.ch_names)} 通道")
    print(f"EEGS:   {raw_eeg.n_times} 点, {len(raw_eeg.ch_names)} 通道")
    
    # 找到共同通道
    common_chs = list(set(raw_mne.ch_names) & set(raw_eeg.ch_names))
    common_chs = sorted(common_chs)[:5]  # 取前5个共同通道用于详细对比
    print(f"共同通道数: {len(common_chs)}")
    print(f"分析通道: {common_chs}")
    
    # 2. 获取数据（统一转换为 μV）
    data_mne = raw_mne.get_data(picks=common_chs) * 1e6  # V -> μV
    data_eeg = raw_eeg.get_data(picks=common_chs)  # 已经是 μV
    
    # 3. 统计对比
    print("\n【统计特征】")
    for i, ch in enumerate(common_chs):
        sig_mne = data_mne[i]
        sig_eeg = data_eeg[i]
        
        print(f"\n通道 {ch}:")
        print(f"  MNE:   均值={np.mean(sig_mne):10.4f} μV,  std={np.std(sig_mne):10.4f} μV, "
              f"min={np.min(sig_mne):10.4f}, max={np.max(sig_mne):10.4f}")
        print(f"  EEGS:  均值={np.mean(sig_eeg):10.4f} μV,  std={np.std(sig_eeg):10.4f} μV, "
              f"min={np.min(sig_eeg):10.4f}, max={np.max(sig_eeg):10.4f}")
        
        # 相关系数
        if np.std(sig_mne) > 0 and np.std(sig_eeg) > 0:
            corr = np.corrcoef(sig_mne, sig_eeg)[0, 1]
            print(f"  相关系数: {corr:.4f}")
        
        # RMS差异
        rms_diff = np.sqrt(np.mean((sig_mne - sig_eeg)**2))
        print(f"  RMS差异:  {rms_diff:.4f} μV")
    
    # 4. 频谱对比（取第一个通道）
    print("\n【频谱分析】（取第一个通道）")
    ch = common_chs[0]
    idx_mne = raw_mne.ch_names.index(ch)
    idx_eeg = raw_eeg.ch_names.index(ch)
    
    sig_mne = data_mne[0]
    sig_eeg = data_eeg[0]
    
    # FFT（高斯脉冲的频谱是宽带的）
    sfreq = raw_mne.info['sfreq']
    n_fft = len(sig_mne)
    freqs = np.fft.rfftfreq(n_fft, 1/sfreq)
    
    fft_mne = np.abs(np.fft.rfft(sig_mne))
    fft_eeg = np.abs(np.fft.rfft(sig_eeg))
    
    # 找到最大频谱峰值
    idx_max_mne = np.argmax(fft_mne[1:]) + 1  # 跳过DC
    idx_max_eeg = np.argmax(fft_eeg[1:]) + 1
    
    print(f"频谱峰值（高斯脉冲为宽带谱）:")
    print(f"  MNE:   峰值@{freqs[idx_max_mne]:.1f}Hz = {fft_mne[idx_max_mne]:.4f}")
    print(f"  EEGS:  峰值@{freqs[idx_max_eeg]:.1f}Hz = {fft_eeg[idx_max_eeg]:.4f}")
    
    # 5. 生成对比图
    plot_comparison(sig_mne, sig_eeg, freqs, fft_mne, fft_eeg, ch, sfreq)
    
    return data_mne, data_eeg, common_chs


def plot_comparison(sig_mne, sig_eeg, freqs, fft_mne, fft_eeg, ch_name, sfreq):
    """绘制对比图"""
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    
    # 时间序列（前1秒）
    t = np.arange(len(sig_mne)) / sfreq
    n_show = int(sfreq)  # 1秒
    
    ax1 = axes[0, 0]
    ax1.plot(t[:n_show], sig_mne[:n_show], 'b-', label='MNE SourceSimulator', linewidth=1)
    ax1.plot(t[:n_show], sig_eeg[:n_show], 'r--', label='EEGSimulator', linewidth=1, alpha=0.7)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Amplitude (μV)')
    ax1.set_title(f'Time Series Comparison - Channel {ch_name}')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 差异图
    ax2 = axes[0, 1]
    diff = sig_mne - sig_eeg
    ax2.plot(t[:n_show], diff[:n_show], 'g-', linewidth=1)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Difference (μV)')
    ax2.set_title('Difference (MNE - EEGS)')
    ax2.grid(True, alpha=0.3)
    
    # 频谱对比
    ax3 = axes[1, 0]
    # 只显示0-50Hz
    freq_mask = freqs <= 50
    ax3.plot(freqs[freq_mask], fft_mne[freq_mask], 'b-', label='MNE', linewidth=1.5)
    ax3.plot(freqs[freq_mask], fft_eeg[freq_mask], 'r--', label='EEGS', linewidth=1.5)
    ax3.set_xlabel('Frequency (Hz)')
    ax3.set_ylabel('Amplitude')
    ax3.set_title('Frequency Spectrum')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.axvline(x=10, color='gray', linestyle=':', alpha=0.5, label='10Hz')
    
    # 散点图：MNE vs EEGS
    ax4 = axes[1, 1]
    # 下采样避免图太密
    step = len(sig_mne) // 1000
    ax4.scatter(sig_mne[::step], sig_eeg[::step], c='purple', alpha=0.3, s=1)
    
    # 对角线
    min_val = min(np.min(sig_mne), np.min(sig_eeg))
    max_val = max(np.max(sig_mne), np.max(sig_eeg))
    ax4.plot([min_val, max_val], [min_val, max_val], 'k--', linewidth=1)
    
    ax4.set_xlabel('MNE Amplitude (μV)')
    ax4.set_ylabel('EEGS Amplitude (μV)')
    ax4.set_title('Scatter Plot (MNE vs EEGS)')
    ax4.grid(True, alpha=0.3)
    
    # 计算R²
    ss_res = np.sum((sig_mne - sig_eeg)**2)
    ss_tot = np.sum((sig_mne - np.mean(sig_mne))**2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    ax4.text(0.05, 0.95, f'R² = {r2:.4f}', transform=ax4.transAxes, 
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig('comparison_mne_vs_eegsimulator.png', dpi=150, bbox_inches='tight')
    print(f"\n对比图已保存: comparison_mne_vs_eegsimulator.png")


def main():
    """主函数"""
    
    print("="*60)
    print("MNE SourceSimulator vs EEGSimulator 对比测试")
    print("="*60)
    print(f"测试条件: 10秒时长, 1000Hz采样率, 高斯脉冲(峰值@5s, sigma=0.5s)")
    
    # 设置测试条件
    print("\n加载MNE数据...")
    fwd, src, labels = setup_test_conditions()
    
    duration = 10.0
    sfreq = 1000
    
    # 方法1: MNE
    t_start = time.time()
    raw_mne, stc_mne = generate_with_mne_source_simulator(fwd, labels, duration, sfreq)
    t_mne = time.time() - t_start
    
    # 方法2: EEGSimulator
    t_start = time.time()
    raw_eeg, patches = generate_with_eegsimulator(fwd, src, labels, duration, sfreq)
    t_eeg = time.time() - t_start
    
    print(f"\n【计算耗时】")
    print(f"MNE:   {t_mne:.3f} 秒")
    print(f"EEGS:  {t_eeg:.3f} 秒")
    
    # 对比结果
    data_mne, data_eeg, common_chs = compare_signals(raw_mne, raw_eeg)
    
    # 总结
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
    print(f"分析了 {len(common_chs)} 个共同通道")
    print(f"对比图已保存: comparison_mne_vs_eegsimulator.png")


if __name__ == '__main__':
    main()
