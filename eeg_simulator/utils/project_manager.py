"""项目管理器 - 处理项目的保存和加载"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np

from .logger import get_logger

logger = get_logger(__name__)


class ProjectManager:
    """项目管理器"""
    
    META_FILE = "meta.json"
    
    @classmethod
    def create_project(cls, project_path, project_name="Untitled"):
        """创建新项目文件夹
        
        Args:
            project_path: 项目文件夹路径
            project_name: 项目名称
            
        Returns:
            bool: 是否成功
        """
        try:
            # 创建项目文件夹
            os.makedirs(project_path, exist_ok=True)
            
            # 创建初始项目数据
            project_data = {
                "meta": {
                    "name": project_name,
                    "created": datetime.now().isoformat(),
                    "modified": datetime.now().isoformat(),
                    "version": "1.0"
                },
                "config": {
                    "sampling_rate": 1000,
                    "simulation_duration": 10.0
                },
                "patches": {},
                "dipoles": [],
                "signals": [],
                "couplings": [],
                "noise": [],
                "bem": {},
                "selected_channels": [],
                "electrode_montage": None,
                "source_space": {}
            }
            
            # 保存到单个 JSON 文件
            with open(os.path.join(project_path, cls.META_FILE), 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            logger.error(f"创建项目失败: {e}")
            return False
    
    @classmethod
    def save_project(cls, project_path, project_data):
        """保存项目数据到单个 meta.json 文件
        
        Args:
            project_path: 项目文件夹路径
            project_data: 项目数据字典
        """
        try:
            if not os.path.exists(project_path):
                os.makedirs(project_path, exist_ok=True)
            
            # 读取现有的 meta.json（如果有）
            meta_path = os.path.join(project_path, cls.META_FILE)
            existing_data = None
            
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Failed to read {meta_path}: {e}")
            
            if existing_data is None:
                existing_data = {
                    "meta": {"name": "Untitled", "created": datetime.now().isoformat()},
                    "config": {},
                    "patches": {},
                    "dipoles": [],
                    "signals": [],
                    "couplings": [],
                    "noise": [],
                    "bem": {},
                    "selected_channels": [],
                    "source_space": {}
                }
            
            # 更新元数据
            existing_data["meta"]["modified"] = datetime.now().isoformat()
            
            # 更新各类数据
            if "patches" in project_data:
                existing_data["patches"] = cls._convert_to_json_serializable(project_data["patches"])
            
            if "dipoles" in project_data:
                existing_data["dipoles"] = cls._serialize_dipoles(project_data["dipoles"])
            
            if "signals" in project_data:
                existing_data["signals"] = cls._serialize_signals(project_data["signals"])
            
            if "couplings" in project_data:
                existing_data["couplings"] = cls._serialize_couplings(project_data["couplings"])
            
            if "noise" in project_data:
                existing_data["noise"] = project_data["noise"]
            
            if "bem" in project_data:
                existing_data["bem"] = project_data["bem"]
            
            if "config" in project_data:
                existing_data["config"] = {**existing_data.get("config", {}), **project_data["config"]}
            
            if "selected_channels" in project_data:
                existing_data["selected_channels"] = project_data["selected_channels"]

            if "electrode_montage" in project_data:
                existing_data["electrode_montage"] = project_data["electrode_montage"]
            
            if "source_space" in project_data:
                existing_data["source_space"] = cls._convert_to_json_serializable(project_data["source_space"])
            
            # 保存到单个 JSON 文件
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            logger.error(f"保存项目失败: {e}", exc_info=True)
            return False
    
    @classmethod
    def load_project(cls, project_path):
        """加载项目数据从 meta.json 文件
        
        Args:
            project_path: 项目文件夹路径
            
        Returns:
            dict: 项目数据
        """
        try:
            meta_path = os.path.join(project_path, cls.META_FILE)
            
            if not os.path.exists(meta_path):
                logger.error(f"项目文件不存在: {meta_path}")
                return None
            
            with open(meta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 确保所有必要的键都存在
            default_data = {
                "meta": {},
                "config": {},
                "patches": {},
                "dipoles": [],
                "signals": [],
                "couplings": [],
                "noise": [],
                "bem": {},
                "selected_channels": [],
                "electrode_montage": None,
                "source_space": {}
            }
            
            for key, default_value in default_data.items():
                if key not in data:
                    data[key] = default_value
            
            return data
        except Exception as e:
            logger.error(f"加载项目失败: {e}", exc_info=True)
            return None
    
    @classmethod
    def is_valid_project(cls, project_path):
        """检查是否是有效的项目文件夹"""
        if not os.path.isdir(project_path):
            return False
        return os.path.exists(os.path.join(project_path, cls.META_FILE))
    
    @classmethod
    def get_project_name(cls, project_path):
        """获取项目名称"""
        try:
            meta_path = os.path.join(project_path, cls.META_FILE)
            if os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("meta", {}).get("name", "Untitled")
        except:
            pass
        return "Untitled"
    
    @staticmethod
    def _convert_to_json_serializable(obj):
        """将 numpy 类型转换为 JSON 可序列化的 Python 原生类型"""
        if obj is None:
            return None
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: ProjectManager._convert_to_json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [ProjectManager._convert_to_json_serializable(v) for v in obj]
        return obj
    
    @staticmethod
    def _serialize_dipoles(dipoles):
        """序列化偶极子数据"""
        serialized = []
        for dipole_id, d in dipoles.items():
            serialized.append({
                "id": dipole_id,
                "position": d.position.tolist() if hasattr(d.position, 'tolist') else list(d.position),
                "orientation": d.orientation.tolist() if hasattr(d.orientation, 'tolist') else list(d.orientation),
                "amplitude": ProjectManager._convert_to_json_serializable(d.amplitude),
                "frequency": ProjectManager._convert_to_json_serializable(d.frequency),
                "waveform_type": getattr(d, 'waveform_type', 'sin'),
                "waveform_params": ProjectManager._convert_to_json_serializable(getattr(d, 'waveform_params', {})),
                "hemi": getattr(d, 'hemi', None),
                "vertno": ProjectManager._convert_to_json_serializable(getattr(d, 'vertno', None)),
                "src_idx": ProjectManager._convert_to_json_serializable(getattr(d, 'src_idx', None))
            })
        return serialized
    
    @staticmethod
    def _serialize_signals(signals):
        """序列化信号数据"""
        serialized = []
        for signal_id, s in signals.items():
            serialized.append({
                "id": signal_id,
                "type": s.type,
                "parameters": ProjectManager._convert_to_json_serializable(s.parameters)
            })
        return serialized
    
    @staticmethod
    def _serialize_couplings(couplings):
        """序列化耦合数据"""
        serialized = []
        for coupling_id, c in couplings.items():
            serialized.append({
                "id": coupling_id,
                "source_id": c.source_patch_id,
                "target_id": c.target_patch_id,
                "type": c.type,
                "strength": ProjectManager._convert_to_json_serializable(c.strength),
                "delay": ProjectManager._convert_to_json_serializable(c.delay)
            })
        return serialized
