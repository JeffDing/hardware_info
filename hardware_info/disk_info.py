# -*- coding: utf-8 -*-
"""
磁盘信息收集模块
"""

import platform
import subprocess
import re
import psutil
from typing import List, Dict, Any

from .base import format_size


class DiskInfoCollector:
    """磁盘信息收集器"""

    def __init__(self):
        self.disks: List[Dict[str, Any]] = []

    def collect(self) -> List[Dict[str, Any]]:
        """收集磁盘信息"""
        print("正在获取硬盘信息...")

        self.disks = []

        # 获取所有磁盘分区
        partitions = psutil.disk_partitions()
        for partition in partitions:
            self._add_partition_info(partition)

        # 获取磁盘物理信息
        if platform.system() == "Linux":
            self._collect_linux_disk_info()
        elif platform.system() == "Windows":
            self._collect_windows_disk_info()

        return self.disks

    def _add_partition_info(self, partition):
        """添加分区信息"""
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk = {
                "设备": partition.device,
                "挂载点": partition.mountpoint,
                "文件系统类型": partition.fstype,
                "总容量": format_size(usage.total),
                "已使用": format_size(usage.used),
                "可用空间": format_size(usage.free),
                "使用率": f"{usage.percent}%"
            }
            self.disks.append(disk)
        except (PermissionError, Exception):
            pass

    def _collect_linux_disk_info(self):
        """收集Linux磁盘物理信息"""
        # 使用lsblk获取磁盘信息
        try:
            result = subprocess.run(
                ['lsblk', '-d', '-o', 'NAME,SIZE,MODEL,VENDOR,TYPE'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:
                    parts = line.split()
                    if parts and parts[-1] == 'disk':
                        disk_detail = {
                            "设备名": parts[0],
                            "容量": parts[1] if len(parts) > 1 else "未知",
                            "型号": parts[2] if len(parts) > 2 else "未知",
                            "厂商": parts[3] if len(parts) > 3 else "未知"
                        }
                        # 更新对应的磁盘信息
                        for disk in self.disks:
                            if parts[0] in disk.get("设备", ""):
                                disk.update(disk_detail)
                                break
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # 使用smartctl获取详细信息
        try:
            result = subprocess.run(['lsblk', '-d', '-n', '-o', 'NAME'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                disk_names = result.stdout.strip().split('\n')
                for disk_name in disk_names:
                    if disk_name:
                        self._get_smartctl_info(disk_name)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def _get_smartctl_info(self, disk_name: str):
        """获取smartctl信息"""
        try:
            result = subprocess.run(
                ['smartctl', '-i', f'/dev/{disk_name}'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                output = result.stdout

                vendor = "未知"
                model = "未知"
                serial = "未知"

                vendor_match = re.search(r'Vendor:\s*(.+)', output)
                if vendor_match:
                    vendor = vendor_match.group(1).strip()

                model_match = re.search(r'Device Model:\s*(.+)', output) or \
                             re.search(r'Model Family:\s*(.+)', output)
                if model_match:
                    model = model_match.group(1).strip()

                serial_match = re.search(r'Serial Number:\s*(.+)', output)
                if serial_match:
                    serial = serial_match.group(1).strip()

                # 更新对应磁盘信息
                for disk in self.disks:
                    if disk_name in disk.get("设备", ""):
                        if "厂商" not in disk:
                            disk["厂商"] = vendor
                        if "型号" not in disk:
                            disk["型号"] = model
                        if "序列号" not in disk:
                            disk["序列号"] = serial
                        break
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def _collect_windows_disk_info(self):
        """收集Windows磁盘信息"""
        try:
            result = subprocess.run(
                ['wmic', 'diskdrive', 'get', 'Model,Size,SerialNumber,InterfaceType'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:
                    parts = line.strip().split()
                    if parts:
                        disk_detail = {
                            "型号": parts[0] if len(parts) > 0 else "未知",
                            "容量": format_size(int(parts[1])) if len(parts) > 1 and parts[1].isdigit() else "未知",
                            "序列号": parts[2] if len(parts) > 2 else "未知",
                            "接口类型": parts[3] if len(parts) > 3 else "未知"
                        }
                        self.disks.append(disk_detail)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
