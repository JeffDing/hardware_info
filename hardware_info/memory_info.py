# -*- coding: utf-8 -*-
"""
内存信息收集模块
"""

import platform
import subprocess
import re
import psutil
from typing import Dict, Any

from .base import format_size


class MemoryInfoCollector:
    """内存信息收集器"""

    def __init__(self):
        self.info: Dict[str, Any] = {}

    def collect(self) -> Dict[str, Any]:
        """收集内存信息"""
        print("正在获取内存信息...")

        self.info = {}

        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            self.info = {
                "总内存": format_size(mem.total),
                "可用内存": format_size(mem.available),
                "已使用内存": format_size(mem.used),
                "内存使用率": f"{mem.percent}%",
                "总交换空间": format_size(swap.total),
                "已使用交换空间": format_size(swap.used),
                "交换空间使用率": f"{swap.percent if swap.total > 0 else 0}%"
            }

            if platform.system() == "Linux":
                self._collect_linux_memory_details()
            elif platform.system() == "Windows":
                self._collect_windows_memory_details()

        except Exception as e:
            print(f"获取内存信息时出错: {e}")
            self.info = {"错误": str(e)}

        return self.info

    def _collect_linux_memory_details(self):
        """收集Linux内存详细信息"""
        try:
            result = subprocess.run(['dmidecode', '-t', 'memory'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout
                self._parse_dmidecode_memory(output)
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

    def _parse_dmidecode_memory(self, output: str):
        """解析dmidecode内存信息"""
        slots = re.findall(r'Device Locator:\s*(.+)', output)
        sizes = re.findall(r'Size:\s*(.+)', output)
        speeds = re.findall(r'Speed:\s*(.+)', output)
        manufacturers = re.findall(r'Manufacturer:\s*(.+)', output)
        types = re.findall(r'Type:\s*(.+)', output)

        memory_details = []
        for i, (slot, size, speed, manufacturer, mem_type) in enumerate(
            zip(slots, sizes, speeds, manufacturers, types)
        ):
            if 'No Module Installed' not in size:
                memory_details.append({
                    "插槽": slot.strip(),
                    "容量": size.strip(),
                    "速度": speed.strip(),
                    "制造商": manufacturer.strip(),
                    "类型": mem_type.strip()
                })

        if memory_details:
            self.info["内存详细信息"] = memory_details

    def _collect_windows_memory_details(self):
        """收集Windows内存详细信息"""
        try:
            result = subprocess.run(
                ['wmic', 'memorychip', 'get', 'Capacity,Speed,Manufacturer,PartNumber'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                memory_details = []
                for line in lines[1:]:
                    parts = line.strip().split()
                    if parts:
                        memory_details.append({
                            "容量": format_size(int(parts[0])) if parts[0].isdigit() else parts[0],
                            "速度": parts[1] if len(parts) > 1 else "未知",
                            "制造商": parts[2] if len(parts) > 2 else "未知"
                        })
                if memory_details:
                    self.info["内存详细信息"] = memory_details
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
