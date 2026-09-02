# -*- coding: utf-8 -*-
"""
系统信息收集模块
"""

import platform
import subprocess
import re
import os
from typing import Dict, Any


class SystemInfoCollector:
    """系统信息收集器"""

    def __init__(self):
        self.info: Dict[str, Any] = {}

    def collect(self) -> Dict[str, Any]:
        """收集系统信息"""
        print("正在获取系统基本信息...")

        system = platform.system()
        machine = platform.machine()
        processor = platform.processor()
        node = platform.node()

        self.info = {
            "操作系统": system,
            "主机名": node,
            "处理器架构": machine,
            "处理器": processor,
            "Python版本": platform.python_version()
        }

        if system == "Linux":
            self._collect_linux_info()
        elif system == "Windows":
            self._collect_windows_info()
        elif system == "Darwin":
            self._collect_macos_info()

        return self.info

    def _collect_linux_info(self):
        """收集Linux系统信息"""
        # 获取Linux发行版信息
        distro_info = self._get_linux_distro()
        if distro_info:
            self.info.update(distro_info)

        # 读取DMI信息
        dmi_files = {
            "制造商": "/sys/class/dmi/id/sys_vendor",
            "产品型号": "/sys/class/dmi/id/product_name",
            "产品序列号": "/sys/class/dmi/id/product_serial",
            "BIOS版本": "/sys/class/dmi/id/bios_version",
            "BIOS日期": "/sys/class/dmi/id/bios_date"
        }

        for key, filepath in dmi_files.items():
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r') as f:
                        value = f.read().strip()
                        if value:
                            self.info[key] = value
                except (IOError, OSError):
                    pass

        # 尝试使用dmidecode命令
        try:
            result = subprocess.run(['dmidecode', '-t', 'system'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout
                if 'Manufacturer:' in output:
                    match = re.search(r'Manufacturer:\s*(.+)', output)
                    if match:
                        self.info["系统制造商"] = match.group(1).strip()
                if 'Product Name:' in output:
                    match = re.search(r'Product Name:\s*(.+)', output)
                    if match:
                        self.info["产品名称"] = match.group(1).strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

    def _collect_windows_info(self):
        """收集Windows系统信息"""
        try:
            result = subprocess.run(
                ['wmic', 'csproduct', 'get', 'Vendor,Name,Version'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].strip().split()
                    if len(parts) >= 2:
                        self.info["制造商"] = parts[0]
                        self.info["产品型号"] = parts[1]

            result = subprocess.run(
                ['wmic', 'bios', 'get', 'SerialNumber,Version'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    serial = lines[1].strip()
                    if serial:
                        self.info["序列号"] = serial
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

    def _collect_macos_info(self):
        """收集macOS系统信息"""
        try:
            result = subprocess.run(['system_profiler', 'SPhardwareDataType'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout
                if 'Model Name:' in output:
                    match = re.search(r'Model Name:\s*(.+)', output)
                    if match:
                        self.info["产品型号"] = match.group(1).strip()
                if 'Serial Number:' in output:
                    match = re.search(r'Serial Number:\s*(.+)', output)
                    if match:
                        self.info["序列号"] = match.group(1).strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

    def _get_linux_distro(self) -> Dict[str, str]:
        """获取Linux发行版信息"""
        distro_info = {}

        # 方法1: 读取 /etc/os-release
        os_release_file = "/etc/os-release"
        if os.path.exists(os_release_file):
            try:
                with open(os_release_file, 'r') as f:
                    content = f.read()

                name_match = re.search(r'^NAME="?([^"\n]+)"?', content, re.MULTILINE)
                if name_match:
                    distro_info["发行版"] = name_match.group(1).strip()

                version_match = re.search(r'^VERSION="?([^"\n]+)"?', content, re.MULTILINE)
                if version_match:
                    distro_info["版本"] = version_match.group(1).strip()

                if distro_info:
                    return distro_info
            except (IOError, OSError):
                pass

        # 方法2: 读取 /etc/lsb-release
        lsb_release_file = "/etc/lsb-release"
        if os.path.exists(lsb_release_file):
            try:
                with open(lsb_release_file, 'r') as f:
                    content = f.read()

                dist_match = re.search(r'^DISTRIB_ID="?([^"\n]+)"?', content, re.MULTILINE)
                if dist_match:
                    distro_info["发行版"] = dist_match.group(1).strip()

                dist_desc_match = re.search(r'^DISTRIB_DESCRIPTION="?([^"\n]+)"?', content, re.MULTILINE)
                if dist_desc_match:
                    distro_info["完整名称"] = dist_desc_match.group(1).strip()

                if distro_info:
                    return distro_info
            except (IOError, OSError):
                pass

        # 方法3: 读取 /etc/redhat-release
        redhat_release_file = "/etc/redhat-release"
        if os.path.exists(redhat_release_file):
            try:
                with open(redhat_release_file, 'r') as f:
                    release_info = f.read().strip()

                distro_info["完整名称"] = release_info

                if "CentOS" in release_info:
                    distro_info["发行版"] = "CentOS"
                    version_match = re.search(r'release (\d+\.?\d*)', release_info)
                    if version_match:
                        distro_info["版本"] = version_match.group(1)
                elif "Red Hat Enterprise Linux" in release_info or "RHEL" in release_info:
                    distro_info["发行版"] = "Red Hat Enterprise Linux"
                    version_match = re.search(r'release (\d+\.?\d*)', release_info)
                    if version_match:
                        distro_info["版本"] = version_match.group(1)
                elif "Fedora" in release_info:
                    distro_info["发行版"] = "Fedora"
                    version_match = re.search(r'release (\d+)', release_info)
                    if version_match:
                        distro_info["版本"] = version_match.group(1)

                if distro_info:
                    return distro_info
            except (IOError, OSError):
                pass

        return distro_info
