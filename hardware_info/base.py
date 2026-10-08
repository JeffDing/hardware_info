# -*- coding: utf-8 -*-
"""
基础常量和枚举定义
"""

from enum import Enum
from typing import Dict, Any
import re


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


def parse_size_to_bytes(size_str: str) -> int:
    """把 '16 GB' / '16384MB' / '476G' / '1.8T' 之类的容量字符串转换为字节数"""
    if not size_str:
        return 0
    match = re.match(r'^\s*(\d+(?:\.\d+)?)\s*([KMGT]?I?B?)\s*$', size_str, re.IGNORECASE)
    if not match:
        return 0
    value = float(match.group(1))
    unit = match.group(2).upper().replace("I", "")
    factors = {
        "": 1,
        "B": 1,
        "KB": 1024,
        "MB": 1024 ** 2,
        "GB": 1024 ** 3,
        "TB": 1024 ** 4,
    }
    return int(value * factors.get(unit, 1))


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
