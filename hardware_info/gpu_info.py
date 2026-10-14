# -*- coding: utf-8 -*-
"""
GPU信息收集模块
支持：NVIDIA、AMD、Intel、摩尔线程、壁仞科技、沐曦、天数智芯、海光
"""

import platform
import subprocess
import re
import psutil
from typing import List, Dict, Any


class GPUInfoCollector:
    """GPU信息收集器"""

    def __init__(self):
        self.gpus: List[Dict[str, str]] = []
        self._seen_models: set = set()

    def collect(self) -> List[Dict[str, str]]:
        """收集GPU信息"""
        print("正在获取GPU信息...")

        self.gpus = []
        self._seen_models = set()

        # 国产GPGPU检测
        self._detect_moore_threads()  # 摩尔线程
        self._detect_biren()          # 壁仞科技
        self._detect_metax()          # 沐曦
        self._detect_iluvatar()       # 天数智芯
        self._detect_hygon()          # 海光

        # 国际GPU检测
        self._detect_nvidia()         # NVIDIA
        self._detect_amd()            # AMD
        self._detect_intel()          # Intel

        # 使用lspci检测（补充）
        self._detect_via_lspci()

        # Windows特定检测
        if platform.system() == "Windows":
            self._detect_windows_gpu()

        # macOS特定检测
        if platform.system() == "Darwin":
            self._detect_macos_gpu()

        return self.gpus

    def _detect_moore_threads(self):
        """检测摩尔线程GPU"""
        try:
            result = subprocess.run(['musa-smi'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout
                model_pattern = re.compile(r'MTT\s+\S+', re.IGNORECASE)
                models = model_pattern.findall(output)

                for model in models:
                    model_key = f"摩尔线程-{model}"
                    if model_key not in self._seen_models:
                        self.gpus.append({
                            "厂商": "摩尔线程",
                            "型号": model,
                            "类型": "GPGPU"
                        })
                        self._seen_models.add(model_key)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _detect_biren(self):
        """检测壁仞科技GPU - 显示详细信息"""
        try:
            result = subprocess.run(['brsmi'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout
                model_pattern = re.compile(r'Biren\d+[A-Z]*|BR\d+', re.IGNORECASE)
                models = model_pattern.findall(output)

                # 获取详细信息
                gpu_details = self._parse_brsmi_details(output)

                for model in models:
                    model_key = f"壁仞科技-{model}"
                    if model_key not in self._seen_models:
                        gpu = {
                            "厂商": "壁仞科技",
                            "型号": model,
                            "类型": "GPGPU"
                        }
                        gpu.update(gpu_details)
                        self.gpus.append(gpu)
                        self._seen_models.add(model_key)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _parse_brsmi_details(self, output: str) -> Dict[str, str]:
        """解析brsmi输出，获取详细信息"""
        details = {}

        # 显存信息 - 格式: "0MiB / 32512MiB" 或 "858/65536 MiB"
        mem_match = re.search(r'(\d+)\s*MiB\s*/\s*(\d+)\s*MiB', output)
        if mem_match:
            mem_used = int(mem_match.group(1))
            mem_total = int(mem_match.group(2))
            if mem_total >= 1024:
                details["显存"] = f"{mem_total/1024:.0f} GB ({mem_used} MiB已使用)"
            else:
                details["显存"] = f"{mem_total} MB"

        # 温度 - 格式: "46C"
        temp_match = re.search(r'(?:Temp|温度)[::\s]*(\d+)\s*C', output, re.IGNORECASE)
        if temp_match:
            details["温度"] = f"{temp_match.group(1)}°C"
        else:
            temp_match2 = re.search(r'\|\s*(\d+)C\s+', output)
            if temp_match2:
                details["温度"] = f"{temp_match2.group(1)}°C"

        # 功耗 - 格式: "58W / 350W"
        power_match = re.search(r'(?:Power|功耗)[::\s]*(\d+)\s*W\s*/\s*(\d+)\s*W', output, re.IGNORECASE)
        if power_match:
            details["功耗"] = f"{power_match.group(1)} W"
            details["功耗上限"] = f"{power_match.group(2)} W"
        else:
            power_match2 = re.search(r'(\d+)\s*W\s*/\s*(\d+)\s*W', output)
            if power_match2:
                details["功耗"] = f"{power_match2.group(1)} W"
                details["功耗上限"] = f"{power_match2.group(2)} W"

        # 利用率 - 格式: "0%"
        util_match = re.search(r'(?:Util|利用率)[::\s]*(\d+)%', output, re.IGNORECASE)
        if util_match:
            details["利用率"] = f"{util_match.group(1)}%"
        else:
            util_match2 = re.search(r'\|\s*(\d+)%\s+', output)
            if util_match2:
                details["利用率"] = f"{util_match2.group(1)}%"

        # 驱动版本
        driver_match = re.search(r'(?:Driver|驱动)[::\s]*Version[::\s]*([\d.]+)', output, re.IGNORECASE)
        if driver_match:
            details["驱动版本"] = driver_match.group(1)
        else:
            driver_match2 = re.search(r'Kernel Mode Driver Version[::\s]*([\d.]+)', output, re.IGNORECASE)
            if driver_match2:
                details["驱动版本"] = driver_match2.group(1)

        # BIOS版本
        bios_match = re.search(r'(?:BIOS|VBIOS)[::\s]*Version[::\s]*([\d.]+)', output, re.IGNORECASE)
        if bios_match:
            details["BIOS版本"] = bios_match.group(1)
        else:
            bios_match2 = re.search(r'BIOS Version[::\s]*([\d.]+)', output, re.IGNORECASE)
            if bios_match2:
                details["BIOS版本"] = bios_match2.group(1)

        # 性能状态
        perf_match = re.search(r'(?:Performance|性能)[::\s]*State[::\s]*(P\d+)', output, re.IGNORECASE)
        if perf_match:
            details["性能状态"] = perf_match.group(1)
        else:
            perf_match2 = re.search(r'\|\s*(P\d+)\s+\|', output)
            if perf_match2:
                details["性能状态"] = perf_match2.group(1)

        # 完整型号
        name_match = re.search(r'(?:Name|名称)[::\s]*(BR\d+)', output, re.IGNORECASE)
        if name_match:
            details["完整型号"] = f"Biren {name_match.group(1)}"
        else:
            name_match2 = re.search(r'Biren\s+(BR\d+)', output, re.IGNORECASE)
            if name_match2:
                details["完整型号"] = f"Biren {name_match2.group(1)}"

        return details

    def _detect_metax(self):
        """检测沐曦GPU - 显示详细信息"""
        try:
            result = subprocess.run(['mx-smi'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout
                model_pattern = re.compile(r'\b(?:MXC|C|N)\d{2,}\b\s*(?:VF)?', re.IGNORECASE)
                models = [m.strip() for m in model_pattern.findall(output)]

                # 获取详细信息
                gpu_details = self._parse_mxsmi_details(output)

                for model in models:
                    model_key = f"沐曦-{model}"
                    if model_key not in self._seen_models:
                        gpu = {
                            "厂商": "沐曦",
                            "型号": model,
                            "类型": "GPGPU"
                        }
                        gpu.update(gpu_details)
                        self.gpus.append(gpu)
                        self._seen_models.add(model_key)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _parse_mxsmi_details(self, output: str) -> Dict[str, str]:
        """解析mx-smi输出，获取详细信息"""
        details = {}

        # 显存信息
        mem_match = re.search(r'(\d+)\s*/\s*(\d+)\s*MiB', output)
        if mem_match:
            mem_used = int(mem_match.group(1))
            mem_total = int(mem_match.group(2))
            if mem_total >= 1024:
                details["显存"] = f"{mem_total/1024:.0f} GB ({mem_used} MiB已使用)"
            else:
                details["显存"] = f"{mem_total} MB"

        # 温度
        temp_match = re.search(r'\|\s*(\d+)C\s+', output)
        if temp_match:
            details["温度"] = f"{temp_match.group(1)}°C"

        # 功耗
        power_match = re.search(r'(\d+)\s*W\s*/\s*(\d+)\s*W', output)
        if power_match:
            details["功耗"] = f"{power_match.group(1)} W"
            details["功耗上限"] = f"{power_match.group(2)} W"

        # 利用率
        util_match = re.search(r'\|\s*(\d+)%\s+', output)
        if util_match:
            details["利用率"] = f"{util_match.group(1)}%"

        # 驱动版本
        driver_match = re.search(r'Kernel Mode Driver Version:\s*([\d.]+)', output)
        if driver_match:
            details["驱动版本"] = driver_match.group(1)

        # BIOS版本
        bios_match = re.search(r'BIOS Version:\s*([\d.]+)', output)
        if bios_match:
            details["BIOS版本"] = bios_match.group(1)

        # MACA版本
        maca_match = re.search(r'MACA Version:\s*([\d.]+)', output)
        if maca_match:
            details["MACA版本"] = maca_match.group(1)

        # 性能状态
        perf_match = re.search(r'\|\s*(P\d+)\s+\|', output)
        if perf_match:
            details["性能状态"] = perf_match.group(1)

        # GPU名称
        name_match = re.search(r'MetaX\s+(C\d+)', output)
        if name_match:
            details["完整型号"] = f"MetaX {name_match.group(1)}"

        return details

    def _detect_iluvatar(self):
        """检测天数智芯GPU"""
        try:
            result = subprocess.run(['ixsmi'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout
                model_pattern = re.compile(r'Iluvatar\s+BI-V\d+', re.IGNORECASE)
                models = model_pattern.findall(output)

                for model in models:
                    model_key = f"天数智芯-{model}"
                    if model_key not in self._seen_models:
                        self.gpus.append({
                            "厂商": "天数智芯",
                            "型号": model,
                            "类型": "GPGPU"
                        })
                        self._seen_models.add(model_key)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _detect_hygon(self):
        """检测海光DCU - 显示详细信息"""
        try:
            result = subprocess.run(['rocm-smi', '--showproductname'],
                                   capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return
            output = result.stdout
            model_pattern = re.compile(r'Card Series:\s*(.+?)(?:\n|$)', re.IGNORECASE)
            models = model_pattern.findall(output)

            details = self._collect_hygon_dcu_details()

            for model in models:
                model = model.strip()
                if model and model not in ["", "N/A"]:
                    model_key = f"海光-{model}"
                    if model_key not in self._seen_models:
                        self.gpus.append({
                            "厂商": "海光",
                            "型号": model,
                            "类型": "GPGPU",
                            **details
                        })
                        self._seen_models.add(model_key)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _collect_hygon_dcu_details(self) -> Dict[str, str]:
        """收集海光DCU详细信息，合并多个rocm-smi命令的输出"""
        details: Dict[str, str] = {}
        cmd = [
            'rocm-smi',
            '--showallinfo',
            '--showmeminfo', 'all',
            '--showmemvendor',
            '--showmemdc',
            '--showfwinfo',
            '--showserial',
            '--showbus',
            '--showperflevel',
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                details = self._parse_hygon_dcu_details(result.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return details

    def _parse_hygon_dcu_details(self, output: str) -> Dict[str, str]:
        """解析海光DCU详细信息"""
        details: Dict[str, str] = {}

        # Device ID
        device_id_match = re.search(r'Device ID:\s*(0x[0-9a-fA-F]+)', output)
        if device_id_match:
            details["设备ID"] = device_id_match.group(1)

        # VBIOS版本
        vbios_match = re.search(r'VBIOS version:\s*(.+)', output)
        if vbios_match:
            details["VBIOS版本"] = vbios_match.group(1).strip()

        # 温度 (Edge/Junction/Mem/Core)
        temp_patterns = {
            "温度(Edge)": r'Temperature \(Sensor edge\) \(C\):\s*([\d.]+)',
            "温度(Junction)": r'Temperature \(Sensor junction\) \(C\):\s*([\d.]+)',
            "温度(Memory)": r'Temperature \(Sensor mem\) \(C\):\s*([\d.]+)',
            "温度(Core)": r'Temperature \(Sensor core\) \(C\):\s*([\d.]+)',
        }
        for key, pat in temp_patterns.items():
            m = re.search(pat, output)
            if m:
                details[key] = f"{m.group(1)}°C"

        # 时钟频率
        clock_patterns = {
            "FCLK频率": r'fclk clock level:\s*\d+\s*\(([\d.]+)Mhz\)',
            "MCLK频率": r'mclk clock level:\s*\d+\s*\(([\d.]+)Mhz\)',
            "SCLK频率": r'sclk clock level:\s*\d+\s*\(([\d.]+)Mhz\)',
            "SOCCLK频率": r'socclk clock level:\s*\d+\s*\(([\d.]+)Mhz\)',
        }
        for key, pat in clock_patterns.items():
            m = re.search(pat, output)
            if m:
                details[key] = f"{m.group(1)} MHz"

        # PCIe速度
        pcie_match = re.search(r'pcie clock level:\s*\d+\s*\(([\d.]+)GT/s', output)
        if pcie_match:
            details["PCIe速度"] = f"{pcie_match.group(1)} GT/s"

        # 功耗
        power_max_match = re.search(r'Max Graphics Package Power \(W\):\s*([\d.]+)', output)
        if power_max_match:
            details["功耗上限"] = f"{power_max_match.group(1)} W"
        power_avg_match = re.search(r'Average Graphics Package Power \(W\):\s*([\d.]+)', output)
        if power_avg_match:
            details["功耗"] = f"{power_avg_match.group(1)} W"

        # 利用率
        hcu_use_match = re.search(r'HCU use \(%\):\s*([\d.]+)', output)
        if hcu_use_match:
            details["HCU利用率"] = f"{hcu_use_match.group(1)}%"
        hcu_mem_match = re.search(r'HCU memory use \(%\):\s*(\d+)', output)
        if hcu_mem_match:
            details["显存利用率"] = f"{hcu_mem_match.group(1)}%"

        # 内存信息 - VRAM
        vram_total_match = re.search(r'vram Total Memory \(MiB\):\s*(\d+)', output)
        vram_used_match = re.search(r'vram Total Used Memory \(MiB\):\s*(\d+)', output)
        if vram_total_match:
            vram_total_mib = int(vram_total_match.group(1))
            vram_used = int(vram_used_match.group(1)) if vram_used_match else 0
            if vram_total_mib >= 1024:
                details["显存"] = f"{vram_total_mib / 1024:.0f} GB ({vram_used} MiB已使用)"
            else:
                details["显存"] = f"{vram_total_mib} MB ({vram_used} MiB已使用)"

        # GTT内存
        gtt_match = re.search(r'gtt Total Memory \(MiB\):\s*(\d+)', output)
        if gtt_match:
            gtt_mib = int(gtt_match.group(1))
            details["GTT内存"] = f"{gtt_mib / 1024:.0f} GB" if gtt_mib >= 1024 else f"{gtt_mib} MB"

        # vis_vram
        vis_vram_match = re.search(r'vis_vram Total Memory \(MiB\):\s*(\d+)', output)
        if vis_vram_match:
            vis_vram_mib = int(vis_vram_match.group(1))
            details["VIS VRAM"] = f"{vis_vram_mib / 1024:.0f} GB" if vis_vram_mib >= 1024 else f"{vis_vram_mib} MB"

        # 可用显存
        avail_match = re.search(r'Available memory size \(MiB\):\s*(\d+)', output)
        if avail_match:
            avail_mib = int(avail_match.group(1))
            details["可用显存"] = f"{avail_mib / 1024:.0f} GB" if avail_mib >= 1024 else f"{avail_mib} MB"

        # 显存颗粒厂商
        mem_vendor_match = re.search(r'HCU Memory Vendor:\s*(.+)', output)
        if mem_vendor_match:
            details["显存颗粒厂商"] = mem_vendor_match.group(1).strip()

        # 显存颗粒日期码
        mem_dc_match = re.search(r'HCU Memory Date Code:\s*(.+)', output)
        if mem_dc_match:
            details["显存颗粒日期码"] = mem_dc_match.group(1).strip()

        # 序列号
        serial_match = re.search(r'Serial Number:\s*(.+)', output)
        if serial_match:
            details["序列号"] = serial_match.group(1).strip()

        # PCI总线
        bus_match = re.search(r'PCI Bus:\s*(.+)', output)
        if bus_match:
            details["PCI总线"] = bus_match.group(1).strip()

        # 电压 (mV -> V)
        voltage_match = re.search(r'Voltage \(mV\):\s*([\d]+)', output)
        if voltage_match:
            voltage_mv = int(voltage_match.group(1))
            details["电压"] = f"{voltage_mv / 1000:.3f} V"

        # 性能等级
        perf_match = re.search(r'Performance Level:\s*(\w+)', output)
        if perf_match:
            details["性能等级"] = perf_match.group(1).strip()

        # 固件版本
        fw_patterns = {
            "MEC固件": r'MEC\s+Firmware Version:\s*(\S+)',
            "MEC2固件": r'MEC2\s+Firmware Version:\s*(\S+)',
            "RLC固件": r'RLC\s+Firmware Version:\s*(\S+)',
            "SDMA固件": r'SDMA\s+Firmware Version:\s*(\S+)',
            "SDMA2固件": r'SDMA2\s+Firmware Version:\s*(\S+)',
            "SMC固件": r'SMC\s+Firmware Version:\s*(\S+)',
        }
        for key, pat in fw_patterns.items():
            m = re.search(pat, output)
            if m:
                details[key] = m.group(1).strip()

        return details

    def _detect_nvidia(self):
        """检测NVIDIA GPU"""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 1:
                        model_key = f"NVIDIA-{parts[0]}"
                        if model_key not in self._seen_models:
                            self.gpus.append({
                                "厂商": "NVIDIA",
                                "型号": parts[0],
                                "驱动版本": parts[1] if len(parts) > 1 else "未知",
                                "显存": parts[2] if len(parts) > 2 else "未知",
                                "类型": "GPU"
                            })
                            self._seen_models.add(model_key)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _detect_amd(self):
        """检测AMD GPU"""
        try:
            result = subprocess.run(['rocm-smi', '--showproductname'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'Card series' in line or 'GPU' in line:
                        model = line.split(':')[-1].strip()
                        model_key = f"AMD-{model}"
                        if model_key not in self._seen_models:
                            self.gpus.append({
                                "厂商": "AMD",
                                "型号": model,
                                "类型": "GPU"
                            })
                            self._seen_models.add(model_key)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _detect_intel(self):
        """检测Intel GPU"""
        # Intel集成显卡通常通过lspci检测
        pass

    def _detect_via_lspci(self):
        """使用lspci检测GPU"""
        try:
            result = subprocess.run(['lspci', '-nn', '-d', '::0300'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    self._parse_lspci_line(line)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _parse_lspci_line(self, line: str):
        """解析lspci输出行"""
        if not line.strip():
            return

        line_upper = line.upper()
        vendor = "未知"
        model = "未知"

        # 国产GPU检测
        if "MOORE THREADS" in line_upper or "摩尔线程" in line:
            vendor = "摩尔线程"
            model_match = re.search(r'MTT\s+\S+', line, re.IGNORECASE)
            if model_match:
                model = model_match.group(0)
            else:
                model = "摩尔线程GPU"
        elif "BR" in line_upper and "BIRENTECH" not in line_upper:
            vendor = "壁仞科技"
            model_match = re.search(r'BR\d+', line, re.IGNORECASE)
            if model_match:
                model = model_match.group(0)
            else:
                model = "壁仞科技GPU"
        elif "ILUVATAR" in line_upper or "天数" in line:
            vendor = "天数智芯"
            model_match = re.search(r'Iluvatar\s+BI-V\d+', line, re.IGNORECASE)
            if not model_match:
                model_match = re.search(r'BI-V\d+', line, re.IGNORECASE)
            if model_match:
                model = model_match.group(0)
            else:
                model = "天数智芯GPU"
        elif "MAXXIR" in line_upper or "沐曦" in line:
            vendor = "沐曦"
            model_match = re.search(r'\b(?:MXC|C|N)\d{2,}\b\s*(?:VF)?', line, re.IGNORECASE)
            if model_match:
                model = model_match.group(0)
            else:
                model = "沐曦GPU"
        elif "HYGON" in line_upper or "海光" in line:
            vendor = "海光"
            model_match = re.search(r'K\d+[A-Z_]*', line, re.IGNORECASE)
            if model_match:
                model = model_match.group(0)
            else:
                model = "海光DCU"
        elif "NVIDIA" in line_upper:
            vendor = "NVIDIA"
            model = line.split(':')[-1].strip() if ':' in line else "NVIDIA GPU"
        elif "AMD" in line_upper or "ADVANCED MICRO DEVICES" in line_upper:
            vendor = "AMD"
            model = line.split(':')[-1].strip() if ':' in line else "AMD GPU"
        elif "INTEL" in line_upper:
            vendor = "Intel"
            model = line.split(':')[-1].strip() if ':' in line else "Intel GPU"

        if vendor != "未知":
            gpu_id = line.split()[0] if line.split() else "未知"
            model_key = f"{vendor}-{model}-{gpu_id}"
            if model_key not in self._seen_models:
                self.gpus.append({
                    "厂商": vendor,
                    "型号": model,
                    "设备ID": gpu_id,
                    "类型": "GPGPU" if vendor in ["摩尔线程", "壁仞科技", "天数智芯", "沐曦", "海光"] else "GPU"
                })
                self._seen_models.add(model_key)

    def _detect_windows_gpu(self):
        """Windows下GPU检测"""
        try:
            result = subprocess.run(
                ['wmic', 'path', 'win32_VideoController', 'get', 'name,AdapterRAM,DriverVersion'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:
                    parts = line.strip().split()
                    if parts:
                        vendor = "未知"
                        model = parts[0]

                        if any(keyword in model.upper() for keyword in ["MOORE", "摩尔", "THREADS"]):
                            vendor = "摩尔线程"
                        elif any(keyword in model.upper() for keyword in ["BR", "BIREN", "壁仞"]):
                            vendor = "壁仞科技"
                        elif any(keyword in model.upper() for keyword in ["ILUVATAR", "天数"]):
                            vendor = "天数智芯"
                        elif any(keyword in model.upper() for keyword in ["MAXXIR", "沐曦"]):
                            vendor = "沐曦"
                        elif any(keyword in model.upper() for keyword in ["HYGON", "海光"]):
                            vendor = "海光"
                        elif "NVIDIA" in model.upper():
                            vendor = "NVIDIA"
                        elif "AMD" in model.upper():
                            vendor = "AMD"
                        elif "INTEL" in model.upper():
                            vendor = "Intel"

                        gpu_type = "GPGPU" if vendor in ["摩尔线程", "壁仞科技", "天数智芯", "沐曦", "海光"] else "GPU"

                        model_key = f"{vendor}-{model}"
                        if model_key not in self._seen_models:
                            self.gpus.append({
                                "厂商": vendor,
                                "型号": model,
                                "类型": gpu_type
                            })
                            self._seen_models.add(model_key)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def _detect_macos_gpu(self):
        """macOS下GPU检测"""
        try:
            result = subprocess.run(['system_profiler', 'SPDisplaysDataType'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout
                matches = re.findall(r'Chipset Model:\s*(.+)', output)
                for model in matches:
                    model = model.strip()
                    model_key = f"Apple-{model}"
                    if model_key not in self._seen_models:
                        self.gpus.append({
                            "厂商": "Apple",
                            "型号": model,
                            "类型": "GPU"
                        })
                        self._seen_models.add(model_key)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
