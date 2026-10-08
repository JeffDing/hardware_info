# -*- coding: utf-8 -*-
"""
主硬件信息收集器
整合所有模块
"""

from typing import Dict, List, Any, Optional

from .base import format_size
from .system_info import SystemInfoCollector
from .cpu_info import CPUInfoCollector
from .gpu_info import GPUInfoCollector
from .npu_info import NPUInfoCollector
from .memory_info import MemoryInfoCollector
from .disk_info import DiskInfoCollector
from .network_info import NetworkInfoCollector, IPGeolocationService


class HardwareInfoCollector:
    """硬件信息收集器 - 主类"""

    def __init__(self):
        self.system_info: Dict[str, Any] = {}
        self.cpu_info: Dict[str, Any] = {}
        self.gpu_info: List[Dict[str, str]] = []
        self.npu_info: List[Dict[str, str]] = []
        self.memory_info: Dict[str, Any] = {}
        self.disk_info: List[Dict[str, Any]] = []
        self.disk_summary: Dict[str, Any] = {}
        self.network_info: List[Dict[str, Any]] = []
        self.ip_info: Dict[str, Any] = {}

    def collect_all(self) -> Dict[str, Any]:
        """收集所有硬件信息"""
        print("=" * 60)
        print("开始收集硬件信息...")
        print("=" * 60)

        # 系统信息
        self.system_info = SystemInfoCollector().collect()

        # CPU信息
        self.cpu_info = CPUInfoCollector().collect()

        # GPU信息
        self.gpu_info = GPUInfoCollector().collect()

        # NPU信息
        self.npu_info = NPUInfoCollector().collect()

        # 内存信息
        self.memory_info = MemoryInfoCollector().collect()

        # 磁盘信息
        disk_collector = DiskInfoCollector()
        self.disk_info = disk_collector.collect()
        self.disk_summary = disk_collector.summary

        # 网络信息
        self.network_info = NetworkInfoCollector().collect()

        # IP地理位置信息
        self.ip_info = IPGeolocationService().query_ip()

        print("=" * 60)
        print("硬件信息收集完成!")
        print("=" * 60)

        return {
            "system": self.system_info,
            "cpu": self.cpu_info,
            "gpu": self.gpu_info,
            "npu": self.npu_info,
            "memory": self.memory_info,
            "disk": self.disk_info,
            "disk_summary": self.disk_summary,
            "network": self.network_info,
            "ip": self.ip_info
        }

    def get_system_info(self) -> Dict[str, str]:
        """获取系统信息"""
        if not self.system_info:
            self.system_info = SystemInfoCollector().collect()
        return self.system_info

    def get_cpu_info(self) -> Dict[str, str]:
        """获取CPU信息"""
        if not self.cpu_info:
            self.cpu_info = CPUInfoCollector().collect()
        return self.cpu_info

    def get_gpu_info(self) -> List[Dict[str, str]]:
        """获取GPU信息"""
        if not self.gpu_info:
            self.gpu_info = GPUInfoCollector().collect()
        return self.gpu_info

    def get_npu_info(self) -> List[Dict[str, str]]:
        """获取NPU信息"""
        if not self.npu_info:
            self.npu_info = NPUInfoCollector().collect()
        return self.npu_info

    def get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息"""
        if not self.memory_info:
            self.memory_info = MemoryInfoCollector().collect()
        return self.memory_info

    def get_disk_info(self) -> List[Dict[str, Any]]:
        """获取磁盘信息"""
        if not self.disk_info:
            self.disk_info = DiskInfoCollector().collect()
        return self.disk_info

    def get_network_info(self) -> List[Dict[str, Any]]:
        """获取网络信息"""
        if not self.network_info:
            self.network_info = NetworkInfoCollector().collect()
        return self.network_info

    def get_external_ip_info(self) -> Dict[str, Any]:
        """获取外网IP信息"""
        return self.ip_info

    def print_report(self):
        """打印硬件信息报告"""
        report = self._generate_report()
        print(report)

    def _generate_report(self) -> str:
        """生成报告文本"""
        lines = []
        lines.append("=" * 60)
        lines.append("硬件信息报告")
        lines.append("=" * 60)

        # 系统信息
        lines.append("\n## 系统信息\n")
        for key, value in self.system_info.items():
            lines.append(f"| {key} | {value} |")

        # CPU信息
        lines.append("\n## CPU信息\n")
        for key, value in self.cpu_info.items():
            lines.append(f"| {key} | {value} |")

        # GPU信息
        lines.append("\n## GPU信息\n")
        if self.gpu_info:
            for i, gpu in enumerate(self.gpu_info, 1):
                lines.append(f"### 设备 {i}\n")
                for key, value in gpu.items():
                    lines.append(f"| {key} | {value} |")
        else:
            lines.append("*无数据*")

        # NPU信息
        lines.append("\n## NPU信息\n")
        if self.npu_info:
            for i, npu in enumerate(self.npu_info, 1):
                lines.append(f"### 设备 {i}\n")
                for key, value in npu.items():
                    lines.append(f"| {key} | {value} |")
        else:
            lines.append("*无数据*")

        # 内存信息
        lines.append("\n## 内存信息\n")
        for key, value in self.memory_info.items():
            if key == "内存详细信息":
                lines.append(f"\n### {key}\n")
                for mem in value:
                    lines.append(f"| {mem.get('插槽', '未知')} | {mem.get('容量', '未知')} | {mem.get('速度', '未知')} | {mem.get('制造商', '未知')} |")
            else:
                lines.append(f"| {key} | {value} |")

        # 磁盘信息
        lines.append("\n## 硬盘信息\n")
        for key, value in self.disk_summary.items():
            lines.append(f"| {key} | {value} |")
        if self.disk_info:
            lines.append("")
        for i, disk in enumerate(self.disk_info, 1):
            lines.append(f"### 设备 {i}\n")
            for key, value in disk.items():
                lines.append(f"| {key} | {value} |")

        # 网络信息
        lines.append("\n## 网卡信息\n")
        if self.network_info:
            for i, interface in enumerate(self.network_info, 1):
                lines.append(f"### 设备 {i}: {interface.get('接口名称', '未知')}\n")
                for key, value in interface.items():
                    if key != "接口名称":
                        lines.append(f"| {key} | {value} |")
        else:
            lines.append("*无数据*")

        # IP地理位置信息
        lines.append("\n## IP地理位置信息\n")
        if self.ip_info:
            lines.append(f"| IP地址 | {self.ip_info.get('ip', '未知')} |")
            lines.append(f"| 国家 | {self.ip_info.get('country', '未知')} ({self.ip_info.get('country_code', '未知')}) |")
            lines.append(f"| 地区/省 | {self.ip_info.get('region', '未知')} |")
            lines.append(f"| 城市 | {self.ip_info.get('city', '未知')} |")
            lines.append(f"| 邮政编码 | {self.ip_info.get('zip', '未知')} |")
            lat = self.ip_info.get('latitude')
            lon = self.ip_info.get('longitude')
            if lat and lon:
                lines.append(f"| 纬度 | {lat} |")
                lines.append(f"| 经度 | {lon} |")
            if self.ip_info.get('timezone'):
                lines.append(f"| 时区 | {self.ip_info.get('timezone')} |")
            lines.append(f"| ISP运营商 | {self.ip_info.get('isp', '未知')} |")
            lines.append(f"| 组织 | {self.ip_info.get('org', '未知')} |")
            lines.append(f"| AS号 | {self.ip_info.get('as', '未知')} |")
        else:
            lines.append("*无数据*")

        lines.append("\n---")
        lines.append("*报告生成时间*")

        return "\n".join(lines)
