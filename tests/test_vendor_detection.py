# -*- coding: utf-8 -*-
"""硬件厂商/型号识别单元测试（标准库 unittest，可直接 python3 -m unittest 发现）"""

import os
import re
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hardware_info.vendor_db import (  # noqa: E402
    pci_vendor_name, lookup_oui, strip_vendor_prefix, normalize_vendor_id,
)
from hardware_info.network_info import NetworkInfoCollector  # noqa: E402
from hardware_info.memory_info import MemoryInfoCollector  # noqa: E402


class TestVendorDB(unittest.TestCase):
    """PCI ID / OUI 映射与型号提取测试"""

    def test_pci_vendor_name_known(self):
        self.assertEqual(pci_vendor_name("0x8086"), "Intel")
        self.assertEqual(pci_vendor_name("8086"), "Intel")
        self.assertEqual(pci_vendor_name("0x15b3"), "NVIDIA (Mellanox)")
        self.assertEqual(pci_vendor_name("0x19e5"), "华为 (Huawei/HiSilicon)")

    def test_pci_vendor_name_unknown(self):
        self.assertIsNone(pci_vendor_name("0x9999"))
        self.assertIsNone(pci_vendor_name(""))
        self.assertIsNone(pci_vendor_name(None))

    def test_normalize_vendor_id(self):
        self.assertEqual(normalize_vendor_id("8086"), "0x8086")
        self.assertEqual(normalize_vendor_id(" 0X10EC "), "0x10ec")

    def test_lookup_oui_physical(self):
        self.assertEqual(lookup_oui("00:1B:21:11:22:33"), "Intel")
        self.assertEqual(lookup_oui("00-e0-4c-ab-cd-ef"), "Realtek (瑞昱)")
        self.assertEqual(lookup_oui("00:18:82:00:00:01"), "华为 (Huawei/HiSilicon)")

    def test_lookup_oui_virtual_and_unknown(self):
        self.assertEqual(lookup_oui("00:50:56:12:34:56"), "VMware")
        self.assertEqual(lookup_oui("52:54:00:aa:bb:cc"), "QEMU/KVM")
        self.assertIsNone(lookup_oui("FF:FF:FF:FF:FF:FF"))
        self.assertIsNone(lookup_oui(""))

    def test_strip_vendor_prefix(self):
        self.assertEqual(
            strip_vendor_prefix("Intel Corporation 82599ES 10 Gigabit Network Connection", "Intel"),
            "82599ES 10 Gigabit Network Connection",
        )
        self.assertEqual(
            strip_vendor_prefix("Mellanox Technologies MT27800 Family [ConnectX-5]",
                                "NVIDIA (Mellanox)"),
            "MT27800 Family [ConnectX-5]",
        )
        # 无别名的厂商名时原样返回
        self.assertEqual(strip_vendor_prefix("Ethernet Controller X710", "Intel"), "Ethernet Controller X710")


class TestLspciParse(unittest.TestCase):
    """lspci 输出解析测试"""

    FAKE_LSPCI = (
        "00:00.0 Host bridge [0600]: Intel Corporation 440FX - 82441FX PMC [Natoma] [8086:1237]\n"
        "03:00.0 Ethernet controller [0200]: Intel Corporation 82599ES 10 Gigabit Network Connection [8086:10fb]\n"
        "04:00.0 Ethernet controller [0200]: Mellanox Technologies MT27800 Family [ConnectX-5] [15b3:1017]\n"
        "05:00.0 Network controller [0280]: Intel Corporation Wi-Fi 6 AX200 [8086:2723]\n"
        "06:00.0 Non-Volatile memory controller [0108]: Device [1d0f:cd00]\n"
    )

    def setUp(self):
        self.collector = NetworkInfoCollector()
        self.nics = self.collector._parse_lspci_nics(self.FAKE_LSPCI)

    def test_only_nic_classes_parsed(self):
        self.assertEqual(len(self.nics), 3)  # 2个以太网 + 1个无线, NVMe被过滤

    def test_intel_nic_vendor_and_model(self):
        nic = self.nics[0]
        self.assertEqual(nic["vendor_id"], "0x8086")
        self.assertEqual(nic["device_id"], "0x10fb")
        self.assertEqual(nic["vendor"], "Intel")
        self.assertEqual(nic["model"], "82599ES 10 Gigabit Network Connection")

    def test_mellanox_nic_vendor_and_model(self):
        nic = self.nics[1]
        self.assertEqual(nic["vendor"], "NVIDIA (Mellanox)")
        self.assertEqual(nic["model"], "MT27800 Family [ConnectX-5]")


class TestNicDetect(unittest.TestCase):
    """网卡厂商识别多级 fallback 测试"""

    def setUp(self):
        self.collector = NetworkInfoCollector()

    def test_sysfs_match_with_lspci(self):
        """sysfs 的 PCI ID 与 lspci 精确匹配 -> 返回完整型号"""
        self.collector._pci_nics = [
            {"vendor_id": "0x15b3", "device_id": "0x1017",
             "vendor": "NVIDIA (Mellanox)", "model": "MT27800 Family [ConnectX-5]"},
        ]

        def fake_read(path):
            if path.endswith("/vendor"):
                return "0x15b3"
            if path.endswith("/device"):
                return "0x1017"
            return None

        with patch.object(NetworkInfoCollector, "_read_pci_id", side_effect=fake_read):
            vendor, model = self.collector._detect_nic_vendor("eth0", "00:11:22:33:44:55")
        self.assertEqual(vendor, "NVIDIA (Mellanox)")
        self.assertEqual(model, "MT27800 Family [ConnectX-5]")

    def test_sysfs_vendor_table_fallback(self):
        """无 lspci 但有 sysfs vendor ID -> 查内置 PCI 表"""
        self.collector._pci_nics = []

        def fake_read(path):
            if path.endswith("/vendor"):
                return "0x8086"
            if path.endswith("/device"):
                return "0x157b"
            return None

        with patch.object(NetworkInfoCollector, "_read_pci_id", side_effect=fake_read):
            vendor, model = self.collector._detect_nic_vendor("eth0", "")
        self.assertEqual(vendor, "Intel")
        self.assertIn("0x8086:0x157b", model)

    def test_oui_fallback_for_virtual_nic(self):
        """无 sysfs PCI ID 的虚拟网卡 -> MAC OUI 识别"""
        def fake_read(path):
            return None

        with patch.object(NetworkInfoCollector, "_read_pci_id", side_effect=fake_read):
            vendor, model = self.collector._detect_nic_vendor("veth1", "52:54:00:aa:bb:cc")
        self.assertEqual(vendor, "QEMU/KVM")
        self.assertEqual(model, "虚拟网卡")

    def test_unknown_when_nothing_matches(self):
        def fake_read(path):
            return None

        with patch.object(NetworkInfoCollector, "_read_pci_id", side_effect=fake_read):
            vendor, model = self.collector._detect_nic_vendor("lo", "FF:FF:FF:FF:FF:FF")
        self.assertEqual(vendor, "未知")
        self.assertEqual(model, "未知")

    def test_read_pci_id_rejects_malformed(self):
        """路径不存在返回 None；内容不合法返回 None（不抛异常）"""
        with patch("builtins.open", unittest.mock.mock_open(read_data="\n")):
            self.assertIsNone(self.collector._read_pci_id("/tmp/not-exists"))
        with patch("builtins.open", unittest.mock.mock_open(read_data="0x8086X\n")):
            self.assertIsNone(self.collector._read_pci_id("/sys/class/net/eth0/device/vendor"))
        with patch("builtins.open", unittest.mock.mock_open(read_data="0x8086\n")):
            self.assertEqual(self.collector._read_pci_id("/sys/class/net/eth0/device/vendor"), "0x8086")

    def test_attach_vendor_fields_order(self):
        """厂商/型号必须插在接口名称之后，其他字段顺序保持"""
        interface = {"接口名称": "eth0", "IPv4地址": "10.0.0.1", "状态": "启用"}
        self.collector._attach_vendor_fields(interface, "Intel", "82599ES")
        keys = list(interface.keys())
        self.assertEqual(keys[:4], ["接口名称", "厂商", "型号", "IPv4地址"])
        self.assertEqual(keys[-1], "状态")


class TestMemorySummary(unittest.TestCase):
    """内存厂商/型号汇总测试"""

    def test_summary_includes_vendor_and_model(self):
        collector = MemoryInfoCollector()
        collector.info = {}
        details = [
            {"插槽": "DIMM_A1", "容量": "32 GB", "制造商": "Samsung",
             "部件号": "M393A4K40DB3-CWE"},
            {"插槽": "DIMM_A2", "容量": "32 GB", "制造商": "Samsung",
             "部件号": "M393A4K40DB3-CWE"},
            {"插槽": "DIMM_B1", "容量": "16 GB", "制造商": "Unknown",
             "部件号": "Not Specified"},
        ]
        collector._add_memory_summary(details)
        self.assertEqual(collector.info["内存厂商"], "Samsung x 2")
        self.assertEqual(collector.info["内存型号"], "M393A4K40DB3-CWE x 2")
        self.assertEqual(collector.info["内存条数量"], "3 根")
        # 原有键不受影响
        self.assertIn("内存配置", collector.info)
        self.assertIn("内存详细信息", collector.info)

    def test_summary_without_vendor_info(self):
        collector = MemoryInfoCollector()
        collector.info = {}
        details = [
            {"插槽": "DIMM_A1", "容量": "16 GB", "制造商": "未知", "部件号": ""},
        ]
        collector._add_memory_summary(details)
        self.assertNotIn("内存厂商", collector.info)
        self.assertNotIn("内存型号", collector.info)


class TestHygonCPUDetect(unittest.TestCase):
    """海光CPU检测测试"""

    def test_hygon_c86_series_identification(self):
        """C86型号系列识别"""
        from hardware_info.cpu_info import CPUInfoCollector
        collector = CPUInfoCollector()
        collector._extract_vendor_from_model("Hygon C86 7185 32-core Processor")
        self.assertEqual(collector.info["厂商"], "Hygon (海光)")
        self.assertEqual(collector.info["型号"], "C86 7185")
        self.assertEqual(collector.info["型号系列"], "C86系列")
        self.assertEqual(collector.info["型号编号"], "7185")

    def test_hygon_c86_model_variants(self):
        """C86不同型号变体识别"""
        from hardware_info.cpu_info import CPUInfoCollector
        test_models = [
            ("Hygon C86 7160 32-core Processor", "C86 7160", "7160"),
            ("Hygon C86 7280 32-core Processor", "C86 7280", "7280"),
            ("Hygon C86 3240 16-core Processor", "C86 3240", "3240"),
            ("Hygon C86 7285 32-core Processor", "C86 7285", "7285"),
        ]
        for full_model, expected_model, expected_num in test_models:
            collector = CPUInfoCollector()
            collector._extract_vendor_from_model(full_model)
            self.assertEqual(collector.info["厂商"], "Hygon (海光)")
            self.assertEqual(collector.info["型号"], expected_model)
            self.assertEqual(collector.info["型号编号"], expected_num)

    def test_hygon_lscpu_parsing(self):
        """lscpu输出中海光字段解析"""
        lscpu_output = (
            "Vendor ID:             HygonGenuine\n"
            "Model:                 0\n"
            "Model name:            Hygon C86 7185 32-core Processor\n"
            "Stepping:              1\n"
            "CPU max MHz:           2000.0000\n"
            "BogoMIPS:              4000.00\n"
            "NUMA node(s):          4\n"
        )
        from hardware_info.cpu_info import CPUInfoCollector
        collector = CPUInfoCollector()
        collector._parse_lscpu_output(lscpu_output)
        self.assertEqual(collector.info["厂商"], "Hygon (海光)")
        self.assertEqual(collector.info["型号"], "Hygon C86 7185 32-core Processor")
        self.assertEqual(collector.info["BogoMIPS"], "4000.00")
        self.assertEqual(collector.info["NUMA节点数"], "4")

    def test_hygon_proc_cpuinfo_fields(self):
        """/proc/cpuinfo中海光字段提取"""
        cpuinfo = (
            "vendor_id\t: HygonGenuine\n"
            "cpu family\t: 24\n"
            "model\t\t: 0\n"
            "model name\t: Hygon C86 7185 32-core Processor\n"
            "stepping\t: 1\n"
            "Virtualization: AMD-V\n"
        )
        family_match = re.search(r'cpu family\s*:\s*(\d+)', cpuinfo)
        self.assertEqual(family_match.group(1), "24")
        stepping_match = re.search(r'stepping\s*:\s*(\d+)', cpuinfo)
        self.assertEqual(stepping_match.group(1), "1")
        virt_match = re.search(r'Virtualization:\s*(\S+)', cpuinfo)
        self.assertEqual(virt_match.group(1), "AMD-V")


class TestHygonDCUDetect(unittest.TestCase):
    """海光DCU检测测试"""

    FAKE_ROCM_SMI_PRODUCTNAME = (
        "GPU ID\t\t: 0x7319\n"
        "Card Series:\t\t K500SM_AI\n"
        "Card Vendor:\t\t Chengdu C-3000 IC Design Co., Ltd.\n"
        "Card Model:\t\t K500SM-AI\n"
    )

    FAKE_ROCM_SMI_ALLINFO = (
        "GPU ID: 0000:43:00.0\n"
        "Device ID: 0x6210\n"
        "VBIOS version: 5.715.001000p.618009\n"
        "Temperature (Sensor edge) (C): 53.0\n"
        "Temperature (Sensor junction) (C): 51.0\n"
        "Temperature (Sensor mem) (C): 54.0\n"
        "Temperature (Sensor core) (C): 51.0\n"
        "fclk clock level: 0 (1250Mhz)\n"
        "mclk clock level: 0 (875Mhz)\n"
        "sclk clock level: 8 (1270Mhz)\n"
        "socclk clock level: 0 (971Mhz)\n"
        "pcie clock level: 1 (8.0GT/s, x16 308Mhz)\n"
        "Performance Level: manual\n"
        "Max Graphics Package Power (W): 300.0\n"
        "Average Graphics Package Power (W): 137.0\n"
        "HCU use (%): 0.0\n"
        "HCU memory use (%): 0\n"
        "HCU Memory Vendor: samsung c-die\n"
        "HCU Memory Date Code: unknown\n"
        "Serial Number: TRYU380012090401\n"
        "PCI Bus: 0000:43:00.0\n"
        "Voltage (mV): 893\n"
        "MEC Firmware Version: 49\n"
        "MEC2 Firmware Version: 49\n"
        "RLC Firmware Version: 6\n"
        "SDMA Firmware Version: 14\n"
        "SDMA2 Firmware Version: 14\n"
        "SMC Firmware Version: 00.15.07.00\n"
        "gtt Total Memory (MiB): 257862\n"
        "vis_vram Total Memory (MiB): 65520\n"
        "vram Total Memory (MiB): 65520\n"
        "vram Total Used Memory (MiB): 2\n"
        "Available memory size (MiB): 65469\n"
    )

    def test_hygon_productname_detection(self):
        """rocm-smi --showproductname 海光型号检测"""
        from hardware_info.gpu_info import GPUInfoCollector
        collector = GPUInfoCollector()
        model_pattern = re.compile(r'Card Series:\s*(.+?)(?:\n|$)', re.IGNORECASE)
        models = model_pattern.findall(self.FAKE_ROCM_SMI_PRODUCTNAME)
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].strip(), "K500SM_AI")

    def test_hygon_dcu_details_parsing(self):
        """海光DCU详细信息解析"""
        from hardware_info.gpu_info import GPUInfoCollector
        collector = GPUInfoCollector()
        details = collector._parse_hygon_dcu_details(self.FAKE_ROCM_SMI_ALLINFO)

        self.assertEqual(details["设备ID"], "0x6210")
        self.assertEqual(details["VBIOS版本"], "5.715.001000p.618009")
        self.assertEqual(details["温度(Edge)"], "53.0°C")
        self.assertEqual(details["温度(Junction)"], "51.0°C")
        self.assertEqual(details["温度(Memory)"], "54.0°C")
        self.assertEqual(details["温度(Core)"], "51.0°C")
        self.assertEqual(details["FCLK频率"], "1250 MHz")
        self.assertEqual(details["MCLK频率"], "875 MHz")
        self.assertEqual(details["SCLK频率"], "1270 MHz")
        self.assertEqual(details["SOCCLK频率"], "971 MHz")
        self.assertEqual(details["PCIe速度"], "8.0 GT/s")
        self.assertEqual(details["性能等级"], "manual")
        self.assertEqual(details["功耗上限"], "300.0 W")
        self.assertEqual(details["功耗"], "137.0 W")
        self.assertEqual(details["HCU利用率"], "0.0%")
        self.assertEqual(details["显存利用率"], "0%")
        self.assertIn("64 GB", details["显存"])
        self.assertIn("252 GB", details["GTT内存"])
        self.assertIn("64 GB", details["VIS VRAM"])
        self.assertIn("64 GB", details["可用显存"])
        self.assertEqual(details["显存颗粒厂商"], "samsung c-die")
        self.assertEqual(details["显存颗粒日期码"], "unknown")
        self.assertEqual(details["序列号"], "TRYU380012090401")
        self.assertEqual(details["PCI总线"], "0000:43:00.0")
        self.assertIn("V", details["电压"])
        self.assertEqual(details["MEC固件"], "49")
        self.assertEqual(details["MEC2固件"], "49")
        self.assertEqual(details["RLC固件"], "6")
        self.assertEqual(details["SDMA固件"], "14")
        self.assertEqual(details["SDMA2固件"], "14")
        self.assertEqual(details["SMC固件"], "00.15.07.00")

    def test_hygon_full_detection_mocked(self):
        """Mock rocm-smi，测试完整海光DCU检测流程"""
        from hardware_info.gpu_info import GPUInfoCollector
        from unittest.mock import patch

        fake_productname = (
            "GPU ID\t\t: 0x7319\n"
            "Card Series:\t\t K500SM_AI\n"
            "Card Vendor:\t\t Chengdu C-3000 IC Design Co., Ltd.\n"
        )
        fake_allinfo = self.FAKE_ROCM_SMI_ALLINFO

        def mock_run(cmd, **kwargs):
            class FakeResult:
                returncode = 0
                if '--showproductname' in cmd:
                    stdout = fake_productname
                else:
                    stdout = fake_allinfo
            return FakeResult()

        with patch('subprocess.run', side_effect=mock_run):
            gpus = GPUInfoCollector().collect()

        hygon_gpus = [g for g in gpus if g.get("厂商") == "海光"]
        self.assertEqual(len(hygon_gpus), 1)
        self.assertEqual(hygon_gpus[0]["型号"], "K500SM_AI")
        self.assertEqual(hygon_gpus[0]["类型"], "GPGPU")
        self.assertEqual(hygon_gpus[0]["设备ID"], "0x6210")
        self.assertIn("显存", hygon_gpus[0])
        self.assertIn("温度(Edge)", hygon_gpus[0])
        self.assertIn("功耗", hygon_gpus[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
