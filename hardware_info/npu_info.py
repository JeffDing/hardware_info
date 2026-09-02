# -*- coding: utf-8 -*-
"""
NPU信息收集模块
支持：华为昇腾910/950系列
"""

import subprocess
import re
import os
from typing import List, Dict, Any


class NPUInfoCollector:
    """NPU信息收集器"""

    def __init__(self):
        self.npus: List[Dict[str, str]] = []

    def collect(self) -> List[Dict[str, str]]:
        """收集NPU信息"""
        print("正在获取NPU信息...")

        self.npus = []

        # 方法1: 使用npu-smi info
        self._detect_via_npu_smi()

        # 方法2: 使用npu-smi info -t board -i 0 -c 0
        self._detect_via_npu_smi_board()

        # 方法3: 查询设备文件
        self._detect_via_device_files()

        return self.npus

    def _detect_via_npu_smi(self):
        """通过npu-smi info检测NPU"""
        try:
            result = subprocess.run(['npu-smi', 'info'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout
                self._parse_npu_smi_info(output)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _parse_npu_smi_info(self, output: str):
        """解析npu-smi info输出"""
        lines = output.split('\n')
        npu_data = {}
        pending_npu = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith('+') or line.startswith('| npu-smi'):
                continue

            # 匹配NPU信息行 (第一行数据)
            npu_match = re.match(
                r'\|\s*(\d+)\s*\|\s*(\S+)\s*\|\s*(\w+)\s+\|\s*([\d.\-]+)\s+(\d+)\s+(\d+)\s*/\s*(\d+)\s*\|',
                line
            )
            if npu_match:
                pending_npu = {
                    "NPU ID": npu_match.group(1),
                    "型号": npu_match.group(2),
                    "健康状态": npu_match.group(3),
                    "厂商": "华为"
                }
                power_val = npu_match.group(4)
                if power_val != '-':
                    pending_npu["功耗"] = f"{power_val} W"
                pending_npu["温度"] = f"{npu_match.group(5)} C"
                pending_npu["Hugepages使用"] = f"{npu_match.group(6)} / {npu_match.group(7)}"
                continue

            # 匹配Chip信息行 (第二行数据)
            if pending_npu is not None and '|' in line:
                parts = [p.strip() for p in line.split('|')]
                while parts and parts[0] == '':
                    parts.pop(0)
                while parts and parts[-1] == '':
                    parts.pop()

                # 找Bus-Id
                bus_id = None
                bus_id_idx = None
                for idx, p in enumerate(parts):
                    if re.match(r'\d{4}:[a-fA-F0-9]{2}:[a-fA-F0-9]{2}\.\d', p):
                        bus_id = p
                        bus_id_idx = idx
                        break

                if bus_id is not None:
                    # 解析后续列
                    after_bus = parts[bus_id_idx + 1:]
                    if len(after_bus) == 1:
                        # 950单卡格式
                        text = after_bus[0]
                        first_num = re.match(r'\s*(\d+)', text)
                        npu_util = first_num.group(1) if first_num else '0'
                        slash_matches = re.findall(r'(\d+)\s*/\s*(\d+)', text)
                        memory_str = f'{slash_matches[0][0]} / {slash_matches[0][1]}' if len(slash_matches) > 0 else '0 / 0'
                        hbm_str = f'{slash_matches[1][0]} / {slash_matches[1][1]}' if len(slash_matches) > 1 else '0 / 0'
                    else:
                        # 910/950多卡格式
                        npu_util = after_bus[0].rstrip('%') if len(after_bus) > 0 else '0'
                        memory_str = after_bus[1] if len(after_bus) > 1 else '0 / 0'
                        hbm_str = after_bus[2] if len(after_bus) > 2 else '0 / 0'

                    pending_npu["NPU利用率"] = f"{npu_util}%"
                    pending_npu["内存使用"] = memory_str
                    pending_npu["HBM使用"] = hbm_str

                    self.npus.append(pending_npu)
                    pending_npu = None

    def _detect_via_npu_smi_board(self):
        """通过npu-smi board命令检测"""
        try:
            result = subprocess.run(['npu-smi', 'info', '-t', 'board', '-i', '0', '-c', '0'],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout

                # 解析NPU型号和HBM大小
                chip_type_match = re.search(r'Chip\s*Type[：:]\s*(\S+)', output, re.IGNORECASE)
                hbm_match = re.search(r'HBM\s*(?:Capacity|Size|Mem)[：:\s]*(\d+)\s*(?:MB|GB)?', output, re.IGNORECASE)

                model = "昇腾NPU"
                if chip_type_match:
                    model = chip_type_match.group(1)
                elif "950" in output:
                    model = "Ascend950"
                elif "910" in output:
                    model = "Ascend910"

                hbm_size = ""
                if hbm_match:
                    hbm_val = hbm_match.group(1)
                    try:
                        hbm_mb = int(hbm_val)
                        if hbm_mb >= 1024:
                            hbm_size = f"{hbm_mb / 1024:.0f} GB"
                        else:
                            hbm_size = f"{hbm_mb} MB"
                    except ValueError:
                        hbm_size = hbm_val

                entry = {"厂商": "华为", "型号": model}
                if hbm_size:
                    entry["显存"] = hbm_size
                self.npus.append(entry)

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _detect_via_device_files(self):
        """通过设备文件检测"""
        if self.npus:
            return

        try:
            if os.path.exists('/dev/davinci0') or os.path.exists('/dev/davinci_manager'):
                npu_entry = {
                    "厂商": "华为",
                    "型号": "昇腾NPU (Davinci架构)",
                    "设备路径": "/dev/davinci*"
                }

                # 尝试从sysfs获取详细信息
                self._get_npu_model_from_sysfs(npu_entry)

                self.npus.append(npu_entry)
        except Exception:
            pass

    def _get_npu_model_from_sysfs(self, entry: Dict[str, str]):
        """从sysfs获取NPU型号"""
        try:
            for davinci_path in ['/sys/devices/davinci0', '/sys/class/davinci']:
                if os.path.exists(davinci_path):
                    for root, dirs, files in os.walk(davinci_path):
                        for fname in files:
                            if 'model' in fname.lower() or 'name' in fname.lower():
                                fpath = os.path.join(root, fname)
                                try:
                                    with open(fpath, 'r') as f:
                                        val = f.read().strip()
                                    if val and ('ascend' in val.lower() or '950' in val or '910' in val):
                                        entry["型号"] = val
                                except (IOError, OSError):
                                    pass
                        break
        except (IOError, OSError):
            pass
