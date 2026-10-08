# -*- coding: utf-8 -*-
"""
厂商识别数据库模块

提供两套映射数据，用于在没有厂商工具（如 lspci）时识别硬件厂商：
- PCI_VENDOR_NAMES: PCI Vendor ID(如 0x8086) -> 厂商名
- MAC_OUI_VENDORS : MAC 地址前三段(OUI) -> 厂商名

另提供从 lspci 设备描述中剥离厂商前缀、提取型号的辅助函数。
"""

from typing import Dict, List, Optional


# PCI Vendor ID -> 厂商名（覆盖常见网卡/加速卡厂商，含国产厂商）
PCI_VENDOR_NAMES: Dict[str, str] = {
    "0x8086": "Intel",
    "0x10de": "NVIDIA",
    "0x14e4": "Broadcom (博通)",
    "0x10ec": "Realtek (瑞昱)",
    "0x15b3": "NVIDIA (Mellanox)",
    "0x19e5": "华为 (Huawei/HiSilicon)",
    "0x1969": "Qualcomm Atheros",
    "0x168c": "Qualcomm Atheros",
    "0x1d6a": "Aquantia",
    "0x1077": "QLogic",
    "0x10df": "Emulex (Broadcom)",
    "0x1428": "Chelsio",
    "0x1106": "VIA (威盛)",
    "0x1022": "AMD",
    "0x1002": "AMD",
    "0x1039": "SiS (矽统)",
    "0x1137": "Cisco",
    "0x108e": "Oracle (Sun)",
    "0x1d0f": "Amazon (AWS)",
    "0x1af4": "Red Hat (Virtio)",
    "0x15ad": "VMware",
    "0x80ee": "Oracle (VirtualBox)",
    "0x1414": "Microsoft (Hyper-V)",
    "0x1b85": "Mellanox (旧ID)",
    "0x0014": "Loongson (龙芯)",
    "0x1a03": "ASPEED (信骅)",
}

# MAC OUI(前三段) -> 厂商名（虚拟网卡 OUI 一并收录，便于识别来源）
MAC_OUI_VENDORS: Dict[str, str] = {
    # Intel
    "00:1B:21": "Intel", "00:1E:67": "Intel", "00:15:17": "Intel",
    "00:13:02": "Intel", "00:15:00": "Intel", "00:16:76": "Intel",
    "00:1F:3C": "Intel", "3C:FD:FE": "Intel", "94:65:9C": "Intel",
    "8C:16:45": "Intel", "F4:4C:70": "Intel", "64:CC:2E": "Intel",
    # Realtek
    "00:E0:4C": "Realtek (瑞昱)",
    # Broadcom
    "00:10:18": "Broadcom (博通)", "B8:27:EB": "Broadcom (博通, 树莓派)",
    # NVIDIA/Mellanox
    "00:02:C9": "NVIDIA (Mellanox)", "00:1B:8B": "NVIDIA (Mellanox)",
    "7C:FE:90": "NVIDIA (Mellanox)", "24:8A:07": "NVIDIA (Mellanox)",
    "B8:59:9F": "NVIDIA (Mellanox)", "E4:1D:2D": "NVIDIA (Mellanox)",
    # Huawei / HiSilicon
    "00:18:82": "华为 (Huawei/HiSilicon)", "00:E0:FC": "华为 (Huawei/HiSilicon)",
    "28:6E:D4": "华为 (Huawei/HiSilicon)", "48:57:DD": "华为 (Huawei/HiSilicon)",
    "54:25:EA": "华为 (Huawei/HiSilicon)",
    # 虚拟化平台
    "00:0C:29": "VMware", "00:50:56": "VMware", "00:05:69": "VMware",
    "00:1C:14": "VMware", "00:1C:42": "Parallels",
    "08:00:27": "Oracle (VirtualBox)", "00:16:3E": "Xen",
    "52:54:00": "QEMU/KVM", "FA:16:3E": "OpenStack", "00:15:5D": "Microsoft (Hyper-V)",
}


# lspci 设备描述中常见的公司后缀词（剥离厂商前缀时使用）
_COMPANY_SUFFIXES = (
    "corporation", "technologies", "technology", "semiconductor",
    "advanced micro devices", "co., ltd", "ltd", "inc.", "inc",
    "corp.", "corp", "gmbh", "devices", "components",
)


def normalize_vendor_id(vendor_id: str) -> Optional[str]:
    """把 '0x8086' / '8086' 形式的 PCI Vendor ID 标准化为 '0x8086'"""
    if not vendor_id:
        return None
    vid = vendor_id.strip().lower()
    if not vid.startswith("0x"):
        vid = "0x" + vid
    return vid


def pci_vendor_name(vendor_id: str) -> Optional[str]:
    """根据 PCI Vendor ID 查询厂商名（如 0x8086 -> Intel）"""
    vid = normalize_vendor_id(vendor_id)
    if not vid:
        return None
    return PCI_VENDOR_NAMES.get(vid)


# lspci 描述文本中厂商英文名的别名，用于剥离厂商前缀提取型号
_VENDOR_ALIASES: Dict[str, List[str]] = {
    "Intel": ["Intel"],
    "NVIDIA": ["NVIDIA", "Mellanox", "Mellanox Technologies"],
    "NVIDIA (Mellanox)": ["Mellanox", "Mellanox Technologies", "NVIDIA"],
    "Broadcom (博通)": ["Broadcom"],
    "Realtek (瑞昱)": ["Realtek Semiconductor", "Realtek"],
    "华为 (Huawei/HiSilicon)": ["Huawei Technologies", "Huawei", "HiSilicon"],
    "Qualcomm Atheros": ["Qualcomm Atheros", "Atheros Communications"],
    "Aquantia": ["Aquantia"],
    "QLogic": ["QLogic"],
    "Emulex (Broadcom)": ["Emulex"],
    "Chelsio": ["Chelsio Communications", "Chelsio"],
    "VIA (威盛)": ["VIA"],
    "AMD": ["Advanced Micro Devices", "AMD"],
    "SiS (矽统)": ["Silicon Integrated Systems", "SiS"],
    "Cisco": ["Cisco"],
    "Oracle (Sun)": ["Sun", "Oracle"],
    "Oracle (VirtualBox)": ["Oracle", "InnoTek"],
    "Amazon (AWS)": ["Amazon.com", "Amazon"],
    "Red Hat (Virtio)": ["Red Hat", "Virtio"],
    "VMware": ["VMware"],
    "Microsoft (Hyper-V)": ["Microsoft", "Hyper-V"],
    "Loongson (龙芯)": ["Loongson Technology", "Loongson"],
    "ASPEED (信骅)": ["ASPEED"],
}


def strip_vendor_prefix(desc: str, vendor: str) -> str:
    """从 lspci 设备描述中剥离厂商名，提取型号

    'Intel Corporation 82599ES 10 Gigabit Network Connection' -> '82599ES ...'
    """
    if not desc:
        return desc

    d = desc.strip()
    low = d.lower()
    for alias in _VENDOR_ALIASES.get(vendor, [vendor]):
        if alias and low.startswith(alias.lower()):
            rest = d[len(alias):].lstrip(" ,.-")
            changed = True
            while changed:
                changed = False
                for suffix in _COMPANY_SUFFIXES:
                    if rest.lower().startswith(suffix):
                        rest = rest[len(suffix):].lstrip(" ,.-")
                        changed = True
            return rest or desc
    return desc


def lookup_oui(mac: str) -> Optional[str]:
    """根据 MAC 地址查询 OUI 厂商（如 '00:1B:21:11:22:33' -> Intel）"""
    if not mac:
        return None
    parts = mac.strip().upper().replace("-", ":").split(":")
    if len(parts) < 3:
        return None
    oui = ":".join(parts[:3])
    return MAC_OUI_VENDORS.get(oui)
