# -*- coding: utf-8 -*-
"""
CPU信息收集模块
"""

import platform
import subprocess
import re
import psutil
from typing import Dict, Any


class CPUInfoCollector:
    """CPU信息收集器"""

    def __init__(self):
        self.info: Dict[str, Any] = {}

    def collect(self) -> Dict[str, Any]:
        """收集CPU信息"""
        print("正在获取CPU信息...")

        self.info = {
            "厂商": "未知",
            "型号": "未知",
            "架构": platform.machine(),
            "核心数": str(psutil.cpu_count(logical=False)),
            "逻辑核心数": str(psutil.cpu_count(logical=True)),
            "频率": "未知"
        }

        if platform.system() == "Linux":
            self._collect_linux_cpu_info()
        elif platform.system() == "Windows":
            self._collect_windows_cpu_info()
        elif platform.system() == "Darwin":
            self._collect_macos_cpu_info()

        # 通用信息补充
        self._add_common_cpu_info()

        return self.info

    def _collect_linux_cpu_info(self):
        """收集Linux CPU信息"""
        # 方法1: 读取/proc/cpuinfo
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()

            # 提取model name
            model_match = re.search(r'model name\s*:\s*(.+)', cpuinfo)
            if model_match:
                model = model_match.group(1).strip()
                self.info["型号"] = model
                self._extract_vendor_from_model(model)

            # 如果没有model name，尝试从CPU part字段提取
            if self.info["型号"] == "未知":
                self._extract_arm_cpu_info(cpuinfo)

            # 提取CPU频率
            freq_match = re.search(r'cpu MHz\s*:\s*([\d.]+)', cpuinfo)
            if freq_match:
                freq_mhz = float(freq_match.group(1))
                if freq_mhz >= 1000:
                    self.info["频率"] = f"{freq_mhz/1000:.2f} GHz"
                else:
                    self.info["频率"] = f"{freq_mhz:.0f} MHz"

            # 提取缓存信息
            self._extract_cache_info(cpuinfo)

            # 提取CPU family
            family_match = re.search(r'cpu family\s*:\s*(\d+)', cpuinfo)
            if family_match:
                self.info["CPU family"] = family_match.group(1).strip()

            # 提取stepping
            stepping_match = re.search(r'stepping\s*:\s*(\d+)', cpuinfo)
            if stepping_match:
                self.info["Stepping"] = stepping_match.group(1).strip()

            # 提取虚拟化类型
            virt_match = re.search(r'Virtualization:\s*(\S+)', cpuinfo)
            if virt_match:
                self.info["虚拟化类型"] = virt_match.group(1).strip()

        except (FileNotFoundError, IOError):
            pass

        # 方法2: 使用lscpu命令
        try:
            result = subprocess.run(['lscpu'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout
                self._parse_lscpu_output(output)
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

        # 方法3: 使用dmidecode
        try:
            result = subprocess.run(['dmidecode', '-t', 'processor'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self._parse_dmidecode_output(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

    def _extract_vendor_from_model(self, model: str):
        """从型号字符串中提取厂商"""
        model_upper = model.upper()
        if "INTEL" in model_upper or "INTEL(R)" in model_upper:
            self.info["厂商"] = "Intel"
        elif "AMD" in model_upper or "ADVANCED MICRO DEVICES" in model_upper:
            self.info["厂商"] = "AMD"
        elif "ARM" in model_upper:
            self.info["厂商"] = "ARM"
        elif "QUALCOMM" in model_upper:
            self.info["厂商"] = "Qualcomm"
        elif "HUAWEI" in model_upper or "KUNPENG" in model_upper or "鲲鹏" in model or "海思" in model:
            self.info["厂商"] = "HiSilicon (海思)"
            self._identify_hygon_c86_series(model)
        elif "HYGON" in model_upper or "海光" in model:
            self.info["厂商"] = "Hygon (海光)"
            self._identify_hygon_c86_series(model)
        elif "ZHAOXIN" in model_upper or "兆芯" in model:
            self.info["厂商"] = "Zhaoxin (兆芯)"
        elif "CENTAUR" in model_upper or "VIA" in model_upper or "威盛" in model:
            self.info["厂商"] = "VIA (威盛)"
        elif "PHYTEC" in model_upper:
            self.info["厂商"] = "Phytec"

    def _extract_arm_cpu_info(self, cpuinfo: str):
        """提取ARM架构CPU信息"""
        implementer_match = re.search(r'CPU implementer\s*:\s*(.+)', cpuinfo)
        part_match = re.search(r'CPU part\s*:\s*(.+)', cpuinfo)

        if implementer_match and part_match:
            implementer = implementer_match.group(1).strip()
            part = part_match.group(1).strip()

            implementer_map = {
                "0x41": "ARM", "0x42": "Broadcom", "0x43": "Cavium",
                "0x44": "DEC", "0x46": "Fujitsu", "0x48": "HiSilicon (海思)",
                "0x49": "Infineon", "0x4D": "Motorola/Freescale", "0x4E": "NVIDIA",
                "0x50": "APM", "0x51": "Qualcomm", "0x53": "Samsung",
                "0x56": "Marvell", "0x61": "Apple", "0x66": "Faraday",
                "0x69": "Intel", "0x70": "Phytium (飞腾)", "0xC0": "Ampere"
            }

            part_map = {
                "0xd01": "Kunpeng 920 (鲲鹏920)", "0xd02": "Kunpeng 920 (鲲鹏920)",
                "0xd03": "Kunpeng 930 (鲲鹏930)", "0xd40": "Kunpeng 920 (鲲鹏920)",
                "0xd41": "Kunpeng 930 (鲲鹏930)",
                "0xd18": "FT-2000/4", "0xd19": "FT-2000/64",
                "0xd1b": "FT-2000+", "0xd1c": "S2500", "0xd1d": "S5000",
                "0xd07": "Cortex-A57", "0xd08": "Cortex-A72", "0xd03": "Cortex-A53",
                "0xd04": "Cortex-A35", "0xd0b": "Cortex-A76", "0xd0c": "Cortex-A76AE",
                "0xd0d": "Cortex-A77", "0xd0e": "Cortex-A78", "0xd40": "Neoverse N1",
                "0xd41": "Cortex-A78", "0xd44": "Cortex-X1", "0xd47": "Cortex-A710",
                "0xd48": "Cortex-X2", "0xd49": "Neoverse N2", "0xd4a": "Neoverse E1",
                "0xd4b": "Cortex-A78C", "0xd4c": "Cortex-A715", "0xd4d": "Cortex-X3",
            }

            vendor = implementer_map.get(implementer.lower(), implementer)
            model = part_map.get(part.lower(), f"ARM (Implementer: {vendor}, Part: {part})")

            if self.info["厂商"] == "未知":
                self.info["厂商"] = vendor
            self.info["型号"] = model

    def _identify_hygon_c86_series(self, model: str):
        """识别海光C86系列型号并更新self.info"""
        c86_match = re.search(r'C86\s+(\d{4})', model)
        if c86_match:
            model_number = c86_match.group(1)
            self.info["型号"] = f"C86 {model_number}"
            self.info["型号系列"] = "C86系列"
            self.info["型号编号"] = model_number
        else:
            self.info["型号"] = model.strip()

    def _extract_cache_info(self, cpuinfo: str):
        """提取缓存信息"""
        cache_patterns = {
            "L1数据缓存": r'L1d cache\s*:\s*(.+)',
            "L1指令缓存": r'L1i cache\s*:\s*(.+)',
            "L2缓存": r'L2 cache\s*:\s*(.+)',
            "L3缓存": r'L3 cache\s*:\s*(.+)'
        }

        for key, pattern in cache_patterns.items():
            match = re.search(pattern, cpuinfo)
            if match:
                self.info[key] = match.group(1).strip()

    def _parse_lscpu_output(self, output: str):
        """解析lscpu命令输出"""
        # 提取厂商信息
        vendor_match = re.search(r'Vendor ID:\s*(.+)', output)
        if vendor_match:
            vendor_id = vendor_match.group(1).strip()
            vendor_id_upper = vendor_id.upper()

            if vendor_id == "GenuineIntel":
                self.info["厂商"] = "Intel"
            elif vendor_id == "AuthenticAMD":
                self.info["厂商"] = "AMD"
            elif vendor_id == "ARM":
                self.info["厂商"] = "ARM"
            elif "HYGON" in vendor_id_upper or "海光" in vendor_id_upper:
                self.info["厂商"] = "Hygon (海光)"
            elif vendor_id_upper in ["ZHAOXIN", "兆芯"]:
                self.info["厂商"] = "Zhaoxin (兆芯)"
            elif vendor_id_upper in ["HUAWEI", "KUNPENG", "HI", "HISILICON", "海思"]:
                self.info["厂商"] = "HiSilicon (海思)"
            else:
                self.info["厂商"] = vendor_id

        # 提取型号
        model_match = re.search(r'Model name:\s*(.+)', output)
        if model_match:
            self.info["型号"] = model_match.group(1).strip()

        # 提取频率
        max_freq_match = re.search(r'CPU max MHz:\s*([\d.]+)', output)
        if max_freq_match:
            max_freq = float(max_freq_match.group(1))
            self.info["最大频率"] = f"{max_freq/1000:.2f} GHz"

        min_freq_match = re.search(r'CPU min MHz:\s*([\d.]+)', output)
        if min_freq_match:
            min_freq = float(min_freq_match.group(1))
            self.info["最小频率"] = f"{min_freq/1000:.2f} GHz"

        # 提取BogoMIPS
        bogo_match = re.search(r'BogoMIPS:\s*([\d.]+)', output)
        if bogo_match:
            self.info["BogoMIPS"] = bogo_match.group(1).strip()

        # 提取NUMA节点数
        numa_match = re.search(r'NUMA node\(s\):\s*(\d+)', output)
        if numa_match:
            self.info["NUMA节点数"] = numa_match.group(1).strip()

    def _parse_dmidecode_output(self, output: str):
        """解析dmidecode输出"""
        # 提取制造商
        manufacturer_match = re.search(r'Manufacturer:\s*(.+)', output)
        if manufacturer_match:
            manufacturer = manufacturer_match.group(1).strip().upper()
            if "INTEL" in manufacturer:
                self.info["厂商"] = "Intel"
            elif "AMD" in manufacturer:
                self.info["厂商"] = "AMD"
            elif "HYGON" in manufacturer or "海光" in manufacturer:
                self.info["厂商"] = "Hygon (海光)"
            elif "ZHAOXIN" in manufacturer or "兆芯" in manufacturer:
                self.info["厂商"] = "Zhaoxin (兆芯)"
            elif "HUAWEI" in manufacturer or "KUNPENG" in manufacturer:
                self.info["厂商"] = "HiSilicon (海思)"

        # 提取版本
        version_match = re.search(r'Version:\s*(.+)', output)
        if version_match and self.info["型号"] == "未知":
            self.info["型号"] = version_match.group(1).strip()

        # 提取当前速度
        speed_match = re.search(r'Current Speed:\s*(.+)', output)
        if speed_match:
            self.info["当前速度"] = speed_match.group(1).strip()

        # 提取最大速度
        max_speed_match = re.search(r'Max Speed:\s*(.+)', output)
        if max_speed_match:
            self.info["最大速度"] = max_speed_match.group(1).strip()

    def _collect_windows_cpu_info(self):
        """收集Windows CPU信息"""
        try:
            result = subprocess.run(
                ['wmic', 'cpu', 'get', 'Manufacturer,Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = [p.strip() for p in lines[1].split(maxsplit=4)]
                    if parts:
                        self.info["厂商"] = parts[0]
                    if len(parts) > 1:
                        self.info["型号"] = parts[1]
                    if len(parts) > 2 and parts[2]:
                        self.info["核心数"] = parts[2]
                    if len(parts) > 3 and parts[3]:
                        self.info["逻辑核心数"] = parts[3]
                    if len(parts) > 4 and parts[4]:
                        try:
                            mhz = float(parts[4])
                            self.info["最大频率"] = f"{mhz/1000:.2f} GHz"
                        except ValueError:
                            pass
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

    def _collect_macos_cpu_info(self):
        """收集macOS CPU信息"""
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                model = result.stdout.strip()
                self.info["型号"] = model
                if "INTEL" in model.upper():
                    self.info["厂商"] = "Intel"
                elif "APPLE" in model.upper():
                    self.info["厂商"] = "Apple"
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

        try:
            result = subprocess.run(['sysctl', '-n', 'hw.cpufrequency'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                freq_hz = int(result.stdout.strip())
                self.info["频率"] = f"{freq_hz/1000000000:.2f} GHz"
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass

    def _add_common_cpu_info(self):
        """添加通用CPU信息"""
        try:
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                if cpu_freq.max and "最大频率" not in self.info:
                    self.info["最大频率"] = f"{cpu_freq.max/1000:.2f} GHz"
                if cpu_freq.min and "最小频率" not in self.info:
                    self.info["最小频率"] = f"{cpu_freq.min/1000:.2f} GHz"
                if cpu_freq.current:
                    self.info["当前频率"] = f"{cpu_freq.current/1000:.2f} GHz"
        except Exception:
            pass

        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            self.info["CPU使用率"] = f"{cpu_percent}%"
        except Exception:
            pass
