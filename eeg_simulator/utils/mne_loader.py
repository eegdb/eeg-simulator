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

from .logger import get_logger

logger = get_logger(__name__)

# 经典 10-20 常用导联（UI「10-20 系统」子集；含 Oz 以支持枕叶 α 等场景）
CLASSIC_1020_CHANNELS = [
    'Fp1', 'Fp2', 'F7', 'F3', 'Fz', 'F4', 'F8',
    'T3', 'C3', 'Cz', 'C4', 'T4',
    'T5', 'P3', 'Pz', 'P4', 'T6', 'O1', 'Oz', 'O2',
]


def pick_montage_channels(montage, ch_names):
    """从 montage 中取出指定通道子集（保留 nasion/lpa/rpa，避免 MNE plot 警告）"""
    pos = montage.get_positions()
    ch_pos = {n: pos['ch_pos'][n] for n in ch_names if n in pos['ch_pos']}
    missing = [n for n in ch_names if n not in ch_pos]
    if missing:
        logger.warning(f"montage 缺少通道位置: {missing[:5]}{'...' if len(missing) > 5 else ''}")
    dig_kwargs = {
        'ch_pos': ch_pos,
        'coord_frame': pos.get('coord_frame', 'head'),
    }
    for fid in ('nasion', 'lpa', 'rpa'):
        if pos.get(fid) is not None:
            dig_kwargs[fid] = pos[fid]
    return mne.channels.make_dig_montage(**dig_kwargs)


def resolve_standard_montage(montage_name: str):
    """解析 UI montage 名称为 DigMontage（standard_1020 映射为经典 19 导）"""
    if montage_name == 'standard_1020':
        full = mne.channels.make_standard_montage('standard_1020')
        return pick_montage_channels(full, CLASSIC_1020_CHANNELS)
    return mne.channels.make_standard_montage(montage_name)


# FreeSurfer Desikan-Killiany (aparc) 皮层分区名称
APARC_REGIONS = frozenset({
    'bankssts', 'caudalanteriorcingulate', 'caudalmiddlefrontal', 'cuneus',
    'entorhinal', 'fusiform', 'inferiorparietal', 'inferiortemporal',
    'isthmuscingulate', 'lateraloccipital', 'lateralorbitofrontal', 'lingual',
    'medialorbitofrontal', 'middletemporal', 'parahippocampal', 'paracentral',
    'parsopercularis', 'parsorbitalis', 'parstriangularis', 'pericalcarine',
    'postcentral', 'posteriorcingulate', 'precentral', 'precuneus',
    'rostralanteriorcingulate', 'rostralmiddlefrontal', 'superiorfrontal',
    'superiorparietal', 'superiortemporal', 'supramarginal', 'frontalpole',
    'temporalpole', 'transversetemporal', 'insula', 'unknown',
})


def _src_vertex_maps(loaded_src):
    """从源空间构建顶点集合与索引映射"""
    src_vertices = {'lh': set(), 'rh': set()}
    src_vertno_to_idx = {'lh': {}, 'rh': {}}

    if not loaded_src:
        return src_vertices, src_vertno_to_idx

    for src_idx, s in enumerate(loaded_src):
        if s['type'] != 'surf':
            continue
        hemi = 'lh' if src_idx == 0 else 'rh'
        offset = 0 if src_idx == 0 else len(loaded_src[0]['vertno'])
        for i, vertno in enumerate(s['vertno']):
            src_vertices[hemi].add(vertno)
            src_vertno_to_idx[hemi][vertno] = offset + i

    return src_vertices, src_vertno_to_idx


def _add_label_vertices(src_labels, label_source_map, hemi, label_name, vertices,
                        src_vertices, src_vertno_to_idx):
    """将 label 顶点写入映射表"""
    if hemi not in src_labels:
        src_labels[hemi] = {}
        label_source_map[hemi] = {}

    if label_name not in src_labels[hemi]:
        src_labels[hemi][label_name] = []
        label_source_map[hemi][label_name] = []

    src_labels[hemi][label_name].extend(vertices.tolist())

    available_vertices = set(vertices.tolist()) & src_vertices.get(hemi, set())
    for vertno in sorted(available_vertices):
        idx = src_vertno_to_idx[hemi].get(vertno)
        if idx is not None:
            label_source_map[hemi][label_name].append({
                'vertno': vertno,
                'index': idx,
            })


def _aparc_region_name(label, hemi):
    """从 MNE label 名称提取 aparc 分区名（去掉 -lh/-rh 后缀）"""
    suffix = f'-{hemi}'
    if label.name.endswith(suffix):
        return label.name[:-len(suffix)]
    return label.name


def _load_aparc_from_annot(subjects_dir, subject, src_vertices, src_vertno_to_idx,
                           src_labels, label_source_map):
    """从 lh/rh.aparc.annot 加载 Desikan-Killiany 分区"""
    loaded = False
    for hemi in ('lh', 'rh'):
        annot_file = os.path.join(subjects_dir, subject, 'label', f'{hemi}.aparc.annot')
        if not os.path.exists(annot_file):
            continue

        labels = mne.read_labels_from_annot(
            subject,
            parc='aparc',
            hemi=hemi,
            subjects_dir=subjects_dir,
            verbose=False,
        )
        loaded = True
        for label in labels:
            region = _aparc_region_name(label, hemi)
            _add_label_vertices(
                src_labels, label_source_map, hemi, region, label.vertices,
                src_vertices, src_vertno_to_idx,
            )
    return loaded


def _load_aparc_from_label_files(subjects_dir, subject, src_vertices, src_vertno_to_idx,
                                 src_labels, label_source_map):
    """从 .label 文件加载 aparc 分区（仅白名单内的标准分区名）"""
    labels_dir = os.path.join(subjects_dir, subject, 'label')
    if not os.path.exists(labels_dir):
        return False

    loaded = False
    for fname in os.listdir(labels_dir):
        if not fname.endswith('.label'):
            continue

        parts = fname.replace('.label', '').split('.')
        if len(parts) < 2:
            continue

        hemi_part = parts[0]
        hemi = hemi_part.split('-')[0] if '-' in hemi_part else hemi_part
        label_name = '.'.join(parts[1:])

        if label_name not in APARC_REGIONS:
            continue

        try:
            label_path = os.path.join(labels_dir, fname)
            label = mne.read_label(label_path, subject=subject)
            loaded = True
            _add_label_vertices(
                src_labels, label_source_map, hemi, label_name, label.vertices,
                src_vertices, src_vertno_to_idx,
            )
        except Exception:
            continue
    return loaded


def _load_a2009s_from_annot(subjects_dir, subject, src_vertices, src_vertno_to_idx,
                            src_labels, label_source_map):
    """从 lh/rh.aparc.a2009s.annot 加载 Destrieux 分区"""
    loaded = False
    for hemi in ('lh', 'rh'):
        annot_file = os.path.join(subjects_dir, subject, 'label', f'{hemi}.aparc.a2009s.annot')
        if not os.path.exists(annot_file):
            continue

        labels = mne.read_labels_from_annot(
            subject,
            parc='aparc.a2009s',
            hemi=hemi,
            subjects_dir=subjects_dir,
            verbose=False,
        )
        loaded = True
        for label in labels:
            label_name = f"a2009s.{label.name}"
            _add_label_vertices(
                src_labels, label_source_map, hemi, label_name, label.vertices,
                src_vertices, src_vertno_to_idx,
            )
    return loaded


def build_label_source_map(loaded_src, subjects_dir, subject):
    """构建 aparc 与 a2009s 图谱的 label 映射

    Desikan-Killiany 从 FreeSurfer 的 .aparc.annot 读取标准分区；
    不会把 BA 等自定义 .label 文件混入 aparc 列表。
    """
    src_labels = {'lh': {}, 'rh': {}}
    label_source_map = {'lh': {}, 'rh': {}}
    src_vertices, src_vertno_to_idx = _src_vertex_maps(loaded_src)

    aparc_loaded = _load_aparc_from_annot(
        subjects_dir, subject, src_vertices, src_vertno_to_idx,
        src_labels, label_source_map,
    )
    if not aparc_loaded:
        _load_aparc_from_label_files(
            subjects_dir, subject, src_vertices, src_vertno_to_idx,
            src_labels, label_source_map,
        )

    _load_a2009s_from_annot(
        subjects_dir, subject, src_vertices, src_vertno_to_idx,
        src_labels, label_source_map,
    )

    return src_labels, label_source_map


def build_eeg_channel_mapping(fwd, montage=None, extra_channels=None, warn_dist_m=0.12):
    """将 UI montage 通道名映射到前向模型 EEG 传感器名（3D 最近邻）。

    通用方法，适用于 MNE 内置 montage（10-20、10-10、Biosemi、EGI、Easycap 等），
    只要 montage 提供各通道在 head 坐标系下的 3D 位置即可。

    Args:
        fwd: MNE Forward 对象
        montage: mne.channels.DigMontage；None 时使用 standard_1020
        extra_channels: 额外需映射的 UI 通道名（如已选但不在 montage 子集中）
        warn_dist_m: 超过该距离（米）的映射记 debug 日志

    Returns:
        dict: {ui_channel_name: forward_sensor_name}
    """
    info = fwd['info']
    picks = mne.pick_types(info, meg=False, eeg=True, exclude=[])
    if len(picks) == 0:
        picks = np.arange(len(info['ch_names']))

    sensor_locs = []
    for i in picks:
        loc = np.array(info['chs'][i]['loc'][:3], dtype=float)
        if loc.shape == (3,) and not np.allclose(loc, 0):
            sensor_locs.append((info['ch_names'][i], loc))

    if not sensor_locs:
        logger.warning("前向模型中无有效 EEG 传感器坐标，无法建立通道映射")
        return {}

    if montage is None:
        montage = resolve_standard_montage('standard_1020')

    montage_positions = montage.get_positions()['ch_pos']
    fwd_ch_names = {name for name, _ in sensor_locs}
    mapping = {}

    def _map_by_nearest(ch_name, positions):
        if ch_name in fwd_ch_names:
            return ch_name, 0.0
        if ch_name not in positions:
            return None, None
        std_pos = np.asarray(positions[ch_name], dtype=float)
        best_ch, best_dist = None, float('inf')
        for sensor_ch, loc in sensor_locs:
            dist = float(np.linalg.norm(loc - std_pos))
            if dist < best_dist:
                best_dist, best_ch = dist, sensor_ch
        return best_ch, best_dist

    for ch_name in montage.ch_names:
        if ch_name in mapping:
            continue
        if ch_name in fwd_ch_names:
            mapping[ch_name] = ch_name
            continue
        best_ch, best_dist = _map_by_nearest(ch_name, montage_positions)
        if best_ch is not None:
            mapping[ch_name] = best_ch
            if best_dist > warn_dist_m:
                logger.debug(
                    f"  {ch_name} -> {best_ch} (距离 {best_dist * 100:.1f} cm)"
                )

    # 已选通道可能不在当前 montage 子集中，用完整 standard_1020 位置补映射
    if extra_channels:
        fallback_positions = montage_positions
        try:
            full_1020 = mne.channels.make_standard_montage('standard_1020')
            fallback_positions = {
                **full_1020.get_positions()['ch_pos'],
                **montage_positions,
            }
        except Exception:
            pass
        for ch_name in extra_channels:
            if ch_name in mapping:
                continue
            best_ch, best_dist = _map_by_nearest(ch_name, fallback_positions)
            if best_ch is not None:
                mapping[ch_name] = best_ch
                if best_dist > warn_dist_m:
                    logger.debug(
                        f"  {ch_name} -> {best_ch} (距离 {best_dist * 100:.1f} cm, extra)"
                    )

    for sensor_ch, _ in sensor_locs:
        if sensor_ch in montage_positions and sensor_ch not in mapping:
            mapping[sensor_ch] = sensor_ch

    return mapping


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
            logger.warning(f"读取标签失败 {fname}: {e}")
    
    return labels
