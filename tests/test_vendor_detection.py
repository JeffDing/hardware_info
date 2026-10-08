# -*- coding: utf-8 -*-
"""硬件厂商/型号识别单元测试（标准库 unittest，可直接 python3 -m unittest 发现）"""

import os
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
