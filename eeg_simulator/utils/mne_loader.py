"""MNE数据加载工具

坐标系和单位说明：
- MNE使用RAS坐标系（神经影像学标准）
  * R (X轴+): 向右
  * A (Y轴+): 向前（朝向面部）
  * S (Z轴+): 向上（朝向头顶）
  * 原点(0,0,0): 大脑解剖学中心，大致在前连合(AC)附近
- 所有物理坐标单位：米(m)

源空间数据结构：
- s['rr']: 顶点坐标数组 (N x 3)，单位米
- s['nn']: 顶点法向量数组 (N x 3)
- s['vertno']: 实际使用的顶点索引列表
- s['inuse']: 顶点是否被使用的标记数组
"""

import os
import mne
import numpy as np


def load_forward_model(file_path):
    """加载正向模型
    
    正向模型描述源空间（大脑皮层）与传感器（电极）之间的映射关系。
    
    Args:
        file_path: 正向模型文件路径 (.fif格式)
        
    Returns:
        mne.Forward: 正向模型对象，包含：
        - src: 源空间信息
        - info: 传感器信息
        - sol: 增益矩阵（leadfield），描述每个源对 each 传感器的贡献
    """
    return mne.read_forward_solution(file_path)


def load_source_space(file_path):
    """加载源空间
    
    源空间定义了大脑皮层上可能产生EEG/MEG信号的离散位置点。
    
    Args:
        file_path: 源空间文件路径 (*-src.fif格式)
        
    Returns:
        list: 源空间列表，通常包含两个元素：
        - src[0]: 左半球源空间
        - src[1]: 右半球源空间
        
        每个源空间对象包含：
        - rr: 所有顶点坐标 (N x 3)，单位米，RAS坐标系
        - nn: 所有顶点法向量 (N x 3)
        - vertno: 实际用于计算的顶点索引列表
        - type: 'surf'(表面) 或 'vol'(体积)
    """
    return mne.read_source_spaces(file_path)


def estimate_source_positions(src, subject, subjects_dir):
    """估算源点在标准空间中的位置
    
    从源空间中提取实际使用的顶点（s['vertno']）的位置和法向量信息。
    
    Args:
        src: 源空间列表（从load_source_space加载）
        subject: 主题名称（如'sample'）
        subjects_dir: 主题目录路径（包含fsaverage等）
        
    Returns:
        dict: 源点位置信息，格式：
        {
            'lh': {vertno: {'pos': [x,y,z], 'normal': [nx,ny,nz]}, ...},
            'rh': {vertno: {'pos': [x,y,z], 'normal': [nx,ny,nz]}, ...}
        }
        其中：
        - pos: [x, y, z] 物理坐标，单位米，RAS坐标系
               x: 左右（右为正），y: 前后（前为正），z: 上下（上为正）
               原点(0,0,0)在大脑中心
        - normal: 表面法向量（朝外）
        - vertno: 顶点在原始表面网格中的编号
    """
    positions = {'lh': {}, 'rh': {}}
    
    for src_idx, s in enumerate(src):
        if s['type'] != 'surf':
            continue  # 跳过体积源空间
            
        hemi = 'lh' if src_idx == 0 else 'rh'
        
        # 遍历该半球实际使用的顶点（s['vertno']是子集）
        for vert_idx in s['vertno']:
            # s['rr'][vert_idx]: 获取该顶点的RAS物理坐标，单位米
            # 坐标范围示例：X约±0.07m(±7cm)，Y约±0.10m，Z约-0.06~+0.09m
            pos = s['rr'][vert_idx]
            
            # s['nn'][vert_idx]: 该顶点的表面法向量
            positions[hemi][vert_idx] = {
                'pos': pos,      # [x, y, z] 单位：米，RAS坐标系
                'normal': s['nn'][vert_idx] if 'nn' in s else [0, 0, 1]  # 法向量
            }
    
    return positions


def get_label_vertices(subject, label_name, hemi, subjects_dir):
    """获取标签包含的顶点
    
    Args:
        subject: 主题名称
        label_name: 标签名称
        hemi: 半球 ('lh' 或 'rh')
        subjects_dir: 主题目录
        
    Returns:
        list: 顶点索引列表
    """
    label_path = os.path.join(
        subjects_dir, subject, 'label',
        f"{hemi}.{label_name}.label"
    )
    
    if os.path.exists(label_path):
        label = mne.read_label(label_path, subject=subject)
        return label.vertices.tolist()
    
    return []


def load_atlas_labels(subject, subjects_dir, atlas='aparc'):
    """加载图谱标签
    
    Args:
        subject: 主题名称
        subjects_dir: 主题目录
        atlas: 图谱名称 ('aparc', 'a2009s')
        
    Returns:
        dict: {hemi: {label_name: [vertices]}}
    """
    labels = {'lh': {}, 'rh': {}}
    label_dir = os.path.join(subjects_dir, subject, 'label')
    
    if not os.path.exists(label_dir):
        return labels
    
    for fname in os.listdir(label_dir):
        if not fname.endswith('.label'):
            continue
            
        # 解析文件名
        parts = fname.replace('.label', '').split('.')
        if len(parts) < 2:
            continue
            
        hemi_part = parts[0]
        if '-' in hemi_part:
            hemi, atlas_name = hemi_part.split('-', 1)
            if atlas_name != atlas:
                continue
        else:
            hemi = hemi_part
            
        label_name = '.'.join(parts[1:])
        
        try:
            label_path = os.path.join(label_dir, fname)
            label = mne.read_label(label_path, subject=subject)
            
            if hemi not in labels:
                labels[hemi] = {}
            
            labels[hemi][label_name] = label.vertices.tolist()
        except Exception as e:
            print(f"读取标签失败 {fname}: {e}")
    
    return labels
