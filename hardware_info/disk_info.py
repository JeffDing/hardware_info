# -*- coding: utf-8 -*-
"""
磁盘信息收集模块
"""

import platform
import subprocess
import re
from collections import Counter
from typing import List, Dict, Any

import psutil

from .base import format_size, parse_size_to_bytes


class DiskInfoCollector:
    """磁盘信息收集器"""

    def __init__(self):
        self.disks: List[Dict[str, Any]] = []
        self.physical_disks: List[Dict[str, Any]] = []
        self.summary: Dict[str, Any] = {}

    def collect(self) -> List[Dict[str, Any]]:
        """收集磁盘信息"""
        print("正在获取硬盘信息...")

        self.disks = []
        self.physical_disks = []
        self.summary = {}

        # 获取所有磁盘分区
        partitions = psutil.disk_partitions()
        for partition in partitions:
            self._add_partition_info(partition)

        # 获取磁盘物理信息
        if platform.system() == "Linux":
            self._collect_linux_disk_info()
        elif platform.system() == "Windows":
            self._collect_windows_disk_info()

        # 汇总统计：硬盘数量、总容量、每块容量
        self._add_disk_summary()

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
        except Exception:
            pass

    def _collect_linux_disk_info(self):
        """收集Linux磁盘物理信息（lsblk + smartctl）"""
        # lsblk -P 以 KEY="VALUE" 输出，型号含空格也不会错位
        output = self._run_command(['lsblk', '-d', '-b', '-P',
                                    '-o', 'NAME,SIZE,TYPE,MODEL,VENDOR,ROTA,TRAN,SERIAL'],
                                   timeout=10)
        if not output:
            # 兼容不支持 TRAN/SERIAL 列的老版本lsblk，逐步降级
            output = self._run_command(['lsblk', '-d', '-b', '-P',
                                        '-o', 'NAME,SIZE,TYPE,MODEL,VENDOR,ROTA'], timeout=10)

        for line in output.splitlines():
            fields = self._parse_pairs(line)
            if not fields or fields.get('TYPE', '') != 'disk':
                continue
            size_bytes = int(fields.get('SIZE', '0') or 0)
            self.physical_disks.append({
                "设备名": fields.get('NAME', '未知'),
                "容量": format_size(size_bytes),
                "型号": fields.get('MODEL', '') or "未知",
                "厂商": fields.get('VENDOR', '') or "未知",
                "序列号": fields.get('SERIAL', '') or "未知",
                "接口类型": fields.get('TRAN', '') or "未知",
                "磁盘类型": "机械硬盘" if fields.get('ROTA') == '1'
                           else ("固态硬盘" if fields.get('ROTA') == '0' else "未知")
            })

        # smartctl补充型号/厂商/序列号
        for disk_name in self._run_command(['lsblk', '-d', '-n', '-o', 'NAME']).splitlines():
            if disk_name.strip():
                self._get_smartctl_info(disk_name.strip())

        # 把物理磁盘信息合并到分区条目（补充分区缺失的字段）
        self._merge_physical_disks()

    @staticmethod
    def _parse_pairs(line: str) -> Dict[str, str]:
        """解析 lsblk -P 输出的 KEY="VALUE" 对"""
        return dict(re.findall(r'(\w+)="([^"]*)"', line))

    def _merge_physical_disks(self):
        """把物理磁盘信息合并到对应的分区条目"""
        for disk in self.disks:
            device = disk.get("设备", "")
            for physical in self.physical_disks:
                name = physical.get("设备名", "")
                if name and name in device:
                    for key, value in physical.items():
                        if key != "设备名" and value not in (None, "", "未知"):
                            disk.setdefault(key, value)
                    break

    def _get_smartctl_info(self, disk_name: str):
        """用smartctl补充磁盘型号/厂商/序列号"""
        output = self._run_command(['smartctl', '-i', f'/dev/{disk_name}'])
        if not output:
            return

        vendor = self._search_one(r'Vendor:\s*(.+)', output)
        model = self._search_one(r'Device Model:\s*(.+)', output) \
            or self._search_one(r'Model Number:\s*(.+)', output) \
            or self._search_one(r'Model Family:\s*(.+)', output)
        serial = self._search_one(r'Serial Number:\s*(.+)', output)

        for disk in self.physical_disks:
            if disk.get("设备名") != disk_name:
                continue
            if vendor and disk.get("厂商") in (None, "", "未知"):
                disk["厂商"] = vendor
            if model and disk.get("型号") in (None, "", "未知"):
                disk["型号"] = model
            if serial and disk.get("序列号") in (None, "", "未知"):
                disk["序列号"] = serial
            break

    @staticmethod
    def _search_one(pattern: str, text: str):
        """在文本中搜索单个匹配值"""
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    def _add_disk_summary(self):
        """汇总统计：硬盘数量、总容量及每块容量分布"""
        sized = [d for d in self.physical_disks if parse_size_to_bytes(d.get("容量", "")) > 0]
        if not sized:
            return

        total_bytes = sum(parse_size_to_bytes(d["容量"]) for d in sized)
        count = len(sized)

        # 每块容量分布（如: 476G x 2 / 1.8 TB x 1）
        size_counter = Counter(d["容量"] for d in sized)
        config = ", ".join(f"{size} x {num}" for size, num in size_counter.most_common())

        self.summary = {
            "硬盘数量": f"{count} 块",
            "硬盘总容量": format_size(total_bytes),
            "每块硬盘容量": config
        }

    def _collect_windows_disk_info(self):
        """收集Windows磁盘物理信息"""
        models = self._wmic_property('diskdrive', 'Model')
        if not models:
            return

        sizes = self._wmic_property('diskdrive', 'Size')
        serials = self._wmic_property('diskdrive', 'SerialNumber')
        interfaces = self._wmic_property('diskdrive', 'InterfaceType')

        for i, model in enumerate(models):
            size_str = sizes[i] if i < len(sizes) else "未知"
            self.physical_disks.append({
                "设备名": f"PhysicalDisk{i}",
                "容量": format_size(int(size_str)) if size_str.isdigit() else "未知",
                "型号": model,
                "厂商": "未知",
                "序列号": serials[i] if i < len(serials) else "未知",
                "接口类型": interfaces[i] if i < len(interfaces) else "未知",
                "磁盘类型": "未知"
            })

        # Windows无法与分区对应，物理盘直接作为条目输出
        self.disks.extend(self.physical_disks)

    @staticmethod
    def _wmic_property(alias: str, prop: str) -> List[str]:
        """通过wmic获取指定类别单个属性的值列表"""
        try:
            result = subprocess.run(['wmic', alias, 'get', prop],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return []
            lines = result.stdout.strip().split('\n')
            # 第一行是表头
            return [line.strip() for line in lines[1:] if line.strip()]
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            return []

    @staticmethod
    def _run_command(cmd: list, timeout: int = 10) -> str:
        """运行命令并返回标准输出（失败返回空字符串）"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.stdout if result.returncode == 0 else ""
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            return ""
