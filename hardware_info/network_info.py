# -*- coding: utf-8 -*-
"""
网络信息收集模块
"""

import platform
import subprocess
import re
import psutil
import socket
from typing import List, Dict, Any

from .base import format_size


class NetworkInfoCollector:
    """网络信息收集器"""

    def __init__(self):
        self.interfaces: List[Dict[str, Any]] = []

    def collect(self) -> List[Dict[str, Any]]:
        """收集网络信息"""
        print("正在获取网卡信息...")

        self.interfaces = []

        # 获取所有网络接口
        interfaces = psutil.net_if_addrs()
        for interface_name, interface_addresses in interfaces.items():
            self._add_interface_info(interface_name, interface_addresses)

        # 获取网络状态信息
        self._add_network_stats()

        # 获取驱动信息（Linux）
        if platform.system() == "Linux":
            self._add_driver_info()

        return self.interfaces

    def _add_interface_info(self, interface_name: str, interface_addresses):
        """添加网络接口信息"""
        ipv4 = []
        ipv6 = []
        mac = ""

        for addr in interface_addresses:
            if str(addr.family) == 'AddressFamily.AF_INET':
                ipv4.append(addr.address)
            elif str(addr.family) == 'AddressFamily.AF_INET6':
                ipv6.append(addr.address)
            elif str(addr.family) == 'AddressFamily.AF_PACKET':
                mac = addr.address

        if ipv4 or ipv6 or mac:
            interface = {
                "接口名称": interface_name,
                "IPv4地址": ipv4 if ipv4 else "无",
                "IPv6地址": ipv6 if ipv6 else "无",
                "MAC地址": mac if mac else "未知"
            }
            self.interfaces.append(interface)

    def _add_network_stats(self):
        """添加网络统计信息"""
        stats = psutil.net_if_stats()
        io_counters = psutil.net_io_counters(pernic=True)

        for interface in self.interfaces:
            name = interface["接口名称"]

            if name in stats:
                stat = stats[name]
                interface["状态"] = "启用" if stat.isup else "关闭"
                interface["速度"] = f"{stat.speed} Mbps" if stat.speed else "未知"
                interface["MTU"] = str(stat.mtu) if stat.mtu else "未知"

            if name in io_counters:
                io = io_counters[name]
                interface["发送字节数"] = format_size(io.bytes_sent)
                interface["接收字节数"] = format_size(io.bytes_recv)
                interface["发送包数"] = str(io.packets_sent)
                interface["接收包数"] = str(io.packets_recv)
                interface["发送错误"] = str(io.errout)
                interface["接收错误"] = str(io.errin)

    def _add_driver_info(self):
        """添加驱动信息（Linux）"""
        for interface in self.interfaces:
            name = interface["接口名称"]
            try:
                # 使用ethtool获取驱动信息
                result = subprocess.run(
                    ['ethtool', '-i', name],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    output = result.stdout
                    driver_match = re.search(r'driver:\s*(.+)', output)
                    version_match = re.search(r'version:\s*(.+)', output)

                    if driver_match:
                        interface["驱动程序"] = driver_match.group(1).strip()
                    if version_match:
                        interface["驱动版本"] = version_match.group(1).strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            # 尝试从sysfs获取驱动信息
            if "驱动程序" not in interface:
                try:
                    result = subprocess.run(
                        ['readlink', f'/sys/class/net/{name}/device/driver/module'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        output = result.stdout.strip()
                        if output:
                            interface["驱动程序"] = output.split('/')[-1]
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
