# -*- coding: utf-8 -*-
"""
NPU信息收集模块
支持：华为昇腾910/950/310P系列
"""

import subprocess
import re
import os
from typing import List, Dict, Any, Optional


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

        # 方法2: 查询设备文件
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
        pending_npu = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith('+') or line.startswith('| npu-smi'):
                continue

            # 匹配NPU信息行 (第一行数据)
            # 格式: | NPU_ID Name | Health | Power(W) Temp(C) Hugepages_Used / Hugepages_Total |
            # 旧版(如910/310P): NPU ID 和 Name 在同一列用空格分隔, 如 "| 0        Ascend910B4  | OK  ..."
            # 新版(如950PR/npu-smi 25.x): NPU ID 和 Name 拆成两列, 如 "| 0      | Ascend950PR      | OK  ..."
            # (\d+) 后的 \s*\|?\s* 兼容两种列分隔; Power可能是数字(67.5)、NA(310P3)或-(无数据)
            npu_match = re.match(
                r'\|\s*(\d+)\s*\|?\s*(\S+?)\s*\|\s*(\w+)\s+\|\s*([\d.\-]+|NA)\s+(\d+)\s+(\d+)\s*/\s*(\d+)\s*\|',
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
                if power_val not in ('NA', '-'):
                    pending_npu["功耗"] = f"{power_val} W"
                elif power_val == 'NA':
                    pending_npu["功耗"] = "不支持"
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
                    # 提取Chip ID和Device ID (格式: "Chip Device", 仅部分多芯片设备单独成列;
                    # 单卡设备该列为空, parts[0]此时是Bus-Id本身, 不能误取)
                    chip_id, device_id = '0', '0'
                    chip_device_match = re.fullmatch(r'(\d+)\s+(\d+)', parts[0]) if parts else None
                    if chip_device_match:
                        chip_id = chip_device_match.group(1)
                        device_id = chip_device_match.group(2)
                    pending_npu["Chip ID"] = chip_id
                    pending_npu["Device ID"] = device_id
                    pending_npu["Bus-Id"] = bus_id

                    # 解析后续列
                    after_bus = parts[bus_id_idx + 1:]
                    if len(after_bus) == 1:
                        # 950单卡格式 或 310P格式 (所有数据合并在一列)
                        text = after_bus[0]
                        first_num = re.match(r'\s*(\d+)', text)
                        npu_util = first_num.group(1) if first_num else '0'
                        slash_matches = re.findall(r'(\d+)\s*/\s*(\d+)', text)
                        memory_str = f'{slash_matches[0][0]} / {slash_matches[0][1]}' if len(slash_matches) > 0 else '0 / 0'
                        hbm_str = f'{slash_matches[1][0]} / {slash_matches[1][1]}' if len(slash_matches) > 1 else ''
                    else:
                        # 910/950多卡格式 (数据分散在多列)
                        npu_util = after_bus[0].rstrip('%') if len(after_bus) > 0 else '0'
                        memory_str = after_bus[1] if len(after_bus) > 1 else '0 / 0'
                        hbm_str = after_bus[2] if len(after_bus) > 2 else ''

                    pending_npu["NPU利用率"] = f"{npu_util}%"
                    pending_npu["内存使用"] = memory_str
                    if hbm_str:
                        pending_npu["HBM使用"] = hbm_str

                    # 查询详细信息 (board/memory/product/usages)
                    self._query_npu_details(pending_npu)

                    self.npus.append(pending_npu)
                    pending_npu = None

    def _query_npu_details(self, npu: Dict[str, str]):
        """查询NPU详细信息（board, memory, product, usages）"""
        card_id = npu.get("NPU ID", "0")
        chip_id = npu.get("Chip ID", "0")

        # board信息: 型号、芯片版本、板卡ID、固件版本
        board_info = self._run_npu_smi_type('board', card_id, chip_id)
        if board_info:
            chip_type = self._extract_field(board_info, r'Chip\s*Type\s*:\s*(\S+)')
            chip_name = self._extract_field(board_info, r'Chip\s*Name\s*:\s*(\S+)')
            chip_version = self._extract_field(board_info, r'Chip\s*Version\s*:\s*(\S+)')
            board_id = self._extract_field(board_info, r'Board\s*ID\s*:\s*(\S+)')
            firmware = self._extract_field(board_info, r'Firmware\s*Version\s*:\s*(\S+)')
            # 新版(npu-smi 25.x)新增字段
            product_name = self._extract_field(board_info, r'Product\s*Name\s*:\s*(\S+)')
            npu_name = self._extract_field(board_info, r'NPU\s*Name\s*:\s*(\S+)')
            manufacturer = self._extract_field(board_info, r'Manufacturer\s*:\s*(\S+)')
            serial_number = self._extract_field(board_info, r'Serial\s*Number\s*:\s*(\S+)')
            sw_version = self._extract_field(board_info, r'Software\s*Version\s*:\s*(\S+)')
            compatibility = self._extract_field(board_info, r'Compatibility\s*:\s*(\S+)')
            pcie_bus = self._extract_field(board_info, r'PCIe\s*Bus\s*Info\s*:\s*(\S+)')
            slot_id = self._extract_field(board_info, r'Slot\s*ID\s*:\s*(\d+)')
            main_board_id = self._extract_field(board_info, r'Main\s*Board\s*ID\s*:\s*(\S+)')
            pcb_id = self._extract_field(board_info, r'PCB\s*ID\s*:\s*(\S+)')
            bom_id = self._extract_field(board_info, r'BOM\s*ID\s*:\s*(\d+)')
            chip_count = self._extract_field(board_info, r'Chip\s*Count\s*:\s*(\d+)')
            pci_vendor_id = self._extract_field(board_info, r'PCI\s*Vendor\s*ID\s*:\s*(\S+)')
            pci_device_id = self._extract_field(board_info, r'PCI\s*Device\s*ID\s*:\s*(\S+)')
            sub_vendor_id = self._extract_field(board_info, r'Subsystem\s*Vendor\s*ID\s*:\s*(\S+)')
            sub_device_id = self._extract_field(board_info, r'Subsystem\s*Device\s*ID\s*:\s*(\S+)')

            # 型号显示为 "Ascend 310P3" 等完整名称; 新版无Chip Type时用Chip Name(如Ascend950PR)
            if chip_type and chip_name:
                npu["型号"] = f"{chip_type} {chip_name}"
            elif chip_name:
                npu["型号"] = chip_name

            # 产品类型: 旧版取自product查询(Atlas 300I Duo), 新版950用board的Product Name
            if product_name and "产品类型" not in npu:
                npu["产品类型"] = product_name

            if npu_name:
                npu["NPU名称"] = npu_name
            if manufacturer:
                npu["制造商"] = manufacturer
            if serial_number:
                npu["序列号"] = serial_number
            if chip_version:
                npu["芯片版本"] = chip_version
            if board_id:
                npu["板卡ID"] = board_id
            if main_board_id:
                npu["主板ID"] = main_board_id
            if pcb_id:
                npu["PCB ID"] = pcb_id
            if bom_id:
                npu["BOM ID"] = bom_id
            if chip_count:
                npu["芯片数量"] = chip_count
            if firmware:
                npu["固件版本"] = firmware
            if sw_version:
                npu["软件版本"] = sw_version
            if compatibility:
                npu["兼容性"] = compatibility
            if pcie_bus:
                npu["PCIe总线"] = pcie_bus
            if slot_id:
                npu["插槽ID"] = slot_id
            if pci_vendor_id:
                npu["PCI供应商ID"] = pci_vendor_id
            if pci_device_id:
                npu["PCI设备ID"] = pci_device_id
            if sub_vendor_id:
                npu["子系统供应商ID"] = sub_vendor_id
            if sub_device_id:
                npu["子系统设备ID"] = sub_device_id

        # memory信息: HBM容量(910/950) 或 DDR容量(310P)
        mem_info = self._run_npu_smi_type('memory', card_id, chip_id)
        if mem_info:
            hbm_cap = self._extract_field(mem_info, r'HBM\s*Capacity\(MB\)\s*:\s*(\d+)')
            hbm_clock = self._extract_field(mem_info, r'HBM\s*Clock\s*Speed\(MHz\)\s*:\s*(\d+)')
            hbm_temp = self._extract_field(mem_info, r'HBM\s*Temperature\(C\)\s*:\s*(\d+)')
            total_ddr = self._extract_field(mem_info, r'Total\s*DDR\s*Capacity\(MB\)\s*:\s*(\d+)')
            # 用行首锚定避免误匹配 "Total DDR Capacity" 行
            ddr_cap = self._extract_field(mem_info, r'^\s*DDR\s*Capacity\(MB\)\s*:\s*(\d+)', re.MULTILINE)
            ddr_clock = self._extract_field(mem_info, r'^\s*DDR\s*Clock\s*Speed\(MHz\)\s*:\s*(\d+)', re.MULTILINE)

            # 容量/频率/温度为0表示硬件不存在该项(如950无DDR), 跳过不显示
            if hbm_cap and int(hbm_cap) > 0:
                npu["HBM容量"] = self._format_mb(int(hbm_cap))
            if hbm_clock and int(hbm_clock) > 0:
                npu["HBM频率"] = f"{hbm_clock} MHz"
            if hbm_temp and int(hbm_temp) > 0:
                npu["HBM温度"] = f"{hbm_temp} C"
            if total_ddr and int(total_ddr) > 0:
                npu["DDR总容量"] = self._format_mb(int(total_ddr))
            if ddr_cap and int(ddr_cap) > 0:
                npu["DDR容量"] = self._format_mb(int(ddr_cap))
            if ddr_clock and int(ddr_clock) > 0:
                npu["DDR频率"] = f"{ddr_clock} MHz"

        # product信息: 产品类型 (如 Atlas 300I Duo)
        prod_info = self._run_npu_smi_type('product', card_id, chip_id)
        if prod_info:
            product = self._extract_field(prod_info, r'Product\s*Type\s*:\s*(.+)')
            if product:
                npu["产品类型"] = product.strip()

        # usages信息: AICore利用率、DDR使用率等
        usage_info = self._run_npu_smi_type('usages', card_id, chip_id)
        if usage_info:
            aicore = self._extract_field(usage_info, r'Aicore\s*Usage\s*Rate\(%\)\s*:\s*(\d+)')
            aicpu = self._extract_field(usage_info, r'Aicpu\s*Usage\s*Rate\(%\)\s*:\s*(\d+)')
            ctrl_cpu = self._extract_field(usage_info, r'Ctrlcpu\s*Usage\s*Rate\(%\)\s*:\s*(\d+)')
            ddr_usage = self._extract_field(usage_info, r'DDR\s*Usage\s*Rate\(%\)\s*:\s*(\d+)')
            ddr_bw = self._extract_field(usage_info, r'DDR\s*Bandwidth\s*Usage\s*Rate\(%\)\s*:\s*(\d+)')
            hbm_usage = self._extract_field(usage_info, r'HBM\s*Usage\s*Rate\(%\)\s*:\s*(\d+)')
            hbm_bw = self._extract_field(usage_info, r'HBM\s*Bandwidth\s*Usage\s*Rate\(%\)\s*:\s*(\d+)')
            if aicore:
                npu["AICore利用率"] = f"{aicore}%"
            if aicpu:
                npu["AiCPU利用率"] = f"{aicpu}%"
            if ctrl_cpu:
                npu["CtrlCPU利用率"] = f"{ctrl_cpu}%"
            if ddr_usage:
                npu["DDR使用率"] = f"{ddr_usage}%"
            if ddr_bw:
                npu["DDR带宽使用率"] = f"{ddr_bw}%"
            if hbm_usage:
                npu["HBM使用率"] = f"{hbm_usage}%"
            if hbm_bw:
                npu["HBM带宽使用率"] = f"{hbm_bw}%"

    def _run_npu_smi_type(self, type_name: str, card_id: str, chip_id: str) -> Optional[str]:
        """运行npu-smi info -t type -i card [-c chip]
        部分设备(如Ascend 950单芯片)不支持-c参数, 自动降级为仅-i重试
        """
        arg_variants = [
            ['npu-smi', 'info', '-t', type_name, '-i', str(card_id), '-c', str(chip_id)],
            ['npu-smi', 'info', '-t', type_name, '-i', str(card_id)],
        ]
        for args in arg_variants:
            try:
                result = subprocess.run(args, capture_output=True, text=True, timeout=10)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return None
            if result.returncode != 0:
                continue
            # 不支持该参数/子命令时npu-smi返回提示文本(不含字段冒号), 降级重试
            if result.stdout and ':' in result.stdout and 'does not support' not in result.stdout:
                return result.stdout
        return None

    def _extract_field(self, text: str, pattern: str, flags: int = 0) -> Optional[str]:
        """从文本中提取字段"""
        match = re.search(pattern, text, flags)
        if match:
            return match.group(1)
        return None

    def _format_mb(self, mb: int) -> str:
        """格式化MB为可读格式"""
        if mb >= 1024:
            return f"{mb / 1024:.0f} GB"
        return f"{mb} MB"

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
                                    if val and ('ascend' in val.lower() or '950' in val or '910' in val or '310p' in val.lower()):
                                        entry["型号"] = val
                                except (IOError, OSError):
                                    pass
                        break
        except (IOError, OSError):
            pass
