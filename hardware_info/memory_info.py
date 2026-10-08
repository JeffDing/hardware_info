# -*- coding: utf-8 -*-
"""
内存信息收集模块
"""

import platform
import subprocess
import re
from collections import Counter
from typing import Dict, Any, List

import psutil

from .base import format_size, parse_size_to_bytes


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
        """收集Linux内存详细信息（需要root权限运行dmidecode）"""
        try:
            result = subprocess.run(['dmidecode', '-t', 'memory'],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self._parse_dmidecode_memory(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

    def _parse_dmidecode_memory(self, output: str):
        """解析dmidecode内存信息，统计内存条数量、总容量及每根容量"""
        # 按空行分割成多个DMI记录块，逐块提取字段，避免各字段列表错位
        blocks = re.split(r'\n\s*\n', output)

        memory_details: List[Dict[str, str]] = []
        for block in blocks:
            if 'Memory Device' not in block:
                continue

            size = self._extract_field(block, 'Size')
            if not size or 'No Module Installed' in size or size.lower() == 'unknown':
                continue

            memory_details.append({
                "插槽": self._extract_field(block, 'Locator') or "未知",
                "容量": size,
                "速度": self._extract_field(block, 'Speed') or "未知",
                "制造商": self._extract_field(block, 'Manufacturer') or "未知",
                "类型": self._extract_field(block, 'Type') or "未知",
                "部件号": self._extract_field(block, 'Part Number') or "未知"
            })

        if memory_details:
            self._add_memory_summary(memory_details)

    @staticmethod
    def _extract_field(block: str, key: str):
        """从单个DMI记录块中提取字段值"""
        match = re.search(rf'^\s*{re.escape(key)}:\s*(.*?)\s*$', block, re.MULTILINE)
        return match.group(1).strip() if match else None

    def _add_memory_summary(self, memory_details: List[Dict[str, str]]):
        """根据内存条明细添加汇总统计：物理总容量、内存条数量、每根容量"""
        total_bytes = sum(self._size_to_bytes(mem.get("容量", "")) for mem in memory_details)
        count = len(memory_details)

        # 每根容量分布（如: 32 GB x 4 / 16 GB x 2, 8 GB x 2）
        size_counter = Counter(mem.get("容量", "未知") for mem in memory_details)
        config = ", ".join(f"{size} x {num}" for size, num in size_counter.most_common())

        self.info.update({
            "内存条数量": f"{count} 根",
            "物理内存总容量": format_size(total_bytes),
            "内存配置": config,
            "内存详细信息": memory_details
        })

    @staticmethod
    def _size_to_bytes(size_str: str) -> int:
        """把 '16 GB' / '16384 MB' 之类的容量字符串转换为字节数"""
        return parse_size_to_bytes(size_str)

    def _collect_windows_memory_details(self):
        """收集Windows内存详细信息"""
        capacities = self._wmic_property('Capacity')
        if not capacities:
            return

        speeds = self._wmic_property('Speed')
        manufacturers = self._wmic_property('Manufacturer')
        part_numbers = self._wmic_property('PartNumber')

        def pick(values: List[str], index: int) -> str:
            return values[index] if index < len(values) else "未知"

        memory_details: List[Dict[str, str]] = []
        for i, cap in enumerate(capacities):
            if not cap.isdigit():
                continue
            speed = pick(speeds, i)
            memory_details.append({
                "插槽": f"DIMM {i + 1}",
                "容量": format_size(int(cap)),
                "速度": f"{speed} MHz" if speed != "未知" else "未知",
                "制造商": pick(manufacturers, i),
                "类型": "未知",
                "部件号": pick(part_numbers, i)
            })

        if memory_details:
            self._add_memory_summary(memory_details)

    @staticmethod
    def _wmic_property(prop: str) -> List[str]:
        """通过wmic获取 memorychip 的单个属性值列表"""
        try:
            result = subprocess.run(
                ['wmic', 'memorychip', 'get', prop],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return []
            lines = result.stdout.strip().split('\n')
            # 第一行是表头
            return [line.strip() for line in lines[1:] if line.strip()]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
