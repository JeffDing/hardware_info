# -*- coding: utf-8 -*-
"""
基础常量和枚举定义
"""

from enum import Enum
from typing import Dict, Any


class HardwareType(Enum):
    """硬件类型"""
    GPU = "GPU"
    GPGPU = "GPGPU"
    NPU = "NPU"
    CPU = "CPU"
    MEMORY = "内存"
    DISK = "硬盘"
    NETWORK = "网卡"


class GPUVendor(Enum):
    """GPU厂商"""
    NVIDIA = "NVIDIA"
    AMD = "AMD"
    INTEL = "Intel"
    MOORE_THREADS = "摩尔线程"
    BIREN = "壁仞科技"
    METAX = "沐曦"
    ILUVATAR = "天数智芯"
    HYGON = "海光"


class NPUVendor(Enum):
    """NPU厂商"""
    ASCEND = "华为"


class CPUVendor(Enum):
    """CPU厂商"""
    INTEL = "Intel"
    AMD = "AMD"
    HUAWEI = "HiSilicon (海思)"
    PHYTUM = "Phytium (飞腾)"
    HYGON = "Hygon (海光)"
    ZHAOXIN = "Zhaoxin (兆芯)"


# 单位转换常量
KB = 1024
MB = KB * 1024
GB = MB * 1024
TB = GB * 1024


def format_size(size_in_bytes: int) -> str:
    """格式化字节大小为可读格式"""
    if size_in_bytes is None or size_in_bytes < 0:
        return "未知"
    
    if size_in_bytes >= TB:
        return f"{size_in_bytes / TB:.2f} TB"
    elif size_in_bytes >= GB:
        return f"{size_in_bytes / GB:.2f} GB"
    elif size_in_bytes >= MB:
        return f"{size_in_bytes / MB:.2f} MB"
    elif size_in_bytes >= KB:
        return f"{size_in_bytes / KB:.2f} KB"
    else:
        return f"{size_in_bytes} B"


def run_command(cmd: list, timeout: int = 5) -> tuple:
    """
    运行命令并返回结果
    
    Args:
        cmd: 命令列表
        timeout: 超时时间（秒）
    
    Returns:
        (returncode, stdout, stderr)
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return -1, "", str(e)


# 导入放在最后避免循环依赖
import subprocess
