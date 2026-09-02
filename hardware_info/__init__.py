# -*- coding: utf-8 -*-
"""
hardware_info 包

硬件信息查询工具，支持多种硬件类型：
- 系统信息
- CPU信息
- GPU信息（NVIDIA、AMD、Intel、摩尔线程、壁仞科技、沐曦、天数智芯、海光）
- NPU信息（华为昇腾）
- 内存信息
- 磁盘信息
- 网络信息

用法:
    from hardware_info import HardwareInfoCollector
    
    collector = HardwareInfoCollector()
    collector.collect_all()
    collector.print_report()
"""

from .collector import HardwareInfoCollector
from .base import HardwareType, GPUVendor, NPUVendor, CPUVendor, format_size

__version__ = "1.0.0"
__all__ = [
    "HardwareInfoCollector",
    "HardwareType",
    "GPUVendor",
    "NPUVendor",
    "CPUVendor",
    "format_size",
]
