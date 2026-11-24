# -*- coding: utf-8 -*-
"""
网络信息收集模块
"""

import platform
import subprocess
import re
import os
import psutil
import socket
from typing import List, Dict, Any, Optional

from .base import format_size
from .vendor_db import pci_vendor_name, strip_vendor_prefix, lookup_oui


class IPGeolocationService:
    """IP地理位置查询服务"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.ip_address = None
        self.geo_info: Dict[str, Any] = {}

    IP_SERVICES = [
        {
            'name': 'ipify',
            'url': 'https://api.ipify.org?format=json',
            'ip_key': 'ip',
            'priority': 1
        },
        {
            'name': 'ipinfo.io',
            'url': 'https://ipinfo.io/json',
            'ip_key': 'ip',
            'priority': 2
        },
        {
            'name': 'ip-api',
            'url': 'http://ip-api.com/json/',
            'ip_key': 'query',
            'priority': 3
        },
        {
            'name': 'ifconfig.me',
            'url': 'https://ifconfig.me/all.json',
            'ip_key': 'ip_addr',
            'priority': 4
        },
        {
            'name': 'icanhazip',
            'url': 'https://icanhazip.com/',
            'ip_key': None,
            'is_text': True,
            'priority': 5
        },
        {
            'name': 'checkip.amazonaws.com',
            'url': 'https://checkip.amazonaws.com/',
            'ip_key': None,
            'is_text': True,
            'priority': 6
        }
    ]

    GEO_SERVICES = [
        {
            'name': 'ip-api',
            'url': 'http://ip-api.com/json/{ip}',
            'fields': 'status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query',
            'priority': 1
        },
        {
            'name': 'ipinfo.io',
            'url': 'https://ipinfo.io/{ip}/json',
            'priority': 2
        },
        {
            'name': 'ip-api.com (field)',
            'url': 'http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query',
            'priority': 3
        },
        {
            'name': 'ipapi.co',
            'url': 'https://ipapi.co/{ip}/json/',
            'priority': 4
        },
        {
            'name': 'ipwhois.app',
            'url': 'https://ipwhois.app/json/{ip}',
            'priority': 5
        }
    ]

    def get_public_ip(self) -> Optional[str]:
        """获取公网IP地址"""
        sorted_services = sorted(self.IP_SERVICES, key=lambda x: x['priority'])
        for service in sorted_services:
            try:
                import requests as req
                response = req.get(service['url'], timeout=self.timeout)
                response.raise_for_status()
                if service.get('is_text', False):
                    ip = response.text.strip()
                else:
                    data = response.json()
                    ip_key = service.get('ip_key', 'ip')
                    ip = data.get(ip_key)
                if ip and self._validate_ip(ip):
                    self.ip_address = ip
                    return ip
            except Exception:
                pass
        return None

    def get_geolocation_info(self, ip: str) -> Optional[Dict[str, Any]]:
        """获取IP的地理位置信息"""
        sorted_services = sorted(self.GEO_SERVICES, key=lambda x: x['priority'])
        for service in sorted_services:
            try:
                import requests as req
                url = service['url'].format(ip=ip)
                response = req.get(url, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                geo_info = self._normalize_geo_data(data, service['name'])
                if geo_info and geo_info.get('status') != 'fail':
                    self.geo_info = geo_info
                    return geo_info
            except Exception:
                pass
        return None

    def _normalize_geo_data(self, data: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
        """标准化不同服务的地理位置数据格式"""
        try:
            normalized = {
                'source': source,
                'status': 'success',
                'ip': data.get('ip') or data.get('query'),
                'country': data.get('country') or data.get('country_name'),
                'country_code': data.get('countryCode') or data.get('country_code'),
                'region': data.get('regionName') or data.get('region') or data.get('state'),
                'city': data.get('city'),
                'zip': data.get('zip') or data.get('postal'),
                'latitude': data.get('lat') or data.get('latitude'),
                'longitude': data.get('lon') or data.get('longitude'),
                'timezone': data.get('timezone'),
                'isp': data.get('isp'),
                'org': data.get('org'),
                'as': data.get('as'),
            }
            if not normalized.get('ip'):
                return None
            return normalized
        except Exception:
            return None

    def _validate_ip(self, ip: str) -> bool:
        """验证IP地址格式"""
        try:
            socket.inet_pton(socket.AF_INET, ip)
            return True
        except socket.error:
            try:
                socket.inet_pton(socket.AF_INET6, ip)
                return True
            except socket.error:
                return False

    def query_ip(self, ip: str = None) -> Optional[Dict[str, Any]]:
        """查询指定IP或本机公网IP的地理位置信息"""
        if not ip:
            ip = self.get_public_ip()
            if not ip:
                return None
        else:
            self.ip_address = ip
        geo_info = self.get_geolocation_info(ip)
        return geo_info


class NetworkInfoCollector:
    """网络信息收集器"""

    # lspci 输出行匹配（网卡类: 0200 以太网 / 0207 InfiniBand / 0280 无线）
    _LSPCI_NIC_RE = re.compile(
        r'^(?P<addr>[\da-f]{2}:[\da-f]{2}\.[\da-f])\s+'
        r'(?P<desc>.+?)\s+\[(?P<class_id>0200|0207|0280)\]:\s+'
        r'(?P<device>.+?)\s+\[(?P<vendor_id>[\da-f]{4}):(?P<device_id>[\da-f]{4})\]\s*$',
        re.IGNORECASE
    )

    def __init__(self):
        self.interfaces: List[Dict[str, Any]] = []
        self._pci_nics: List[Dict[str, str]] = []

    def collect(self) -> List[Dict[str, Any]]:
        """收集网络信息"""
        print("正在获取网卡信息...")

        self.interfaces = []

        # 获取默认网关 (网关与接口的映射)
        gateway_map = self._get_default_gateways()
        # 获取DNS服务器
        dns_servers = self._get_dns_servers()

        # 获取所有网络接口
        interfaces = psutil.net_if_addrs()
        for interface_name, interface_addresses in interfaces.items():
            # 跳过回环接口
            if interface_name == 'lo':
                continue
            self._add_interface_info(interface_name, interface_addresses,
                                     gateway_map, dns_servers)

        # 获取网络状态信息
        self._add_network_stats()

        # 获取驱动和sysfs信息（Linux）
        if platform.system() == "Linux":
            self._add_sysfs_info()
            self._add_driver_info()

        # 网卡厂商/型号信息（Linux走PCI/OUI识别，Windows走wmic；Windows/macOS失败时仅填未知）
        if platform.system() == "Linux":
            self._add_pci_vendor_info()
        elif platform.system() == "Windows":
            self._add_windows_nic_vendor_info()

        # 物理网卡优先排序
        self._sort_interfaces()

        return self.interfaces

    def _add_interface_info(self, interface_name: str, interface_addresses,
                            gateway_map: Dict[str, str], dns_servers: List[str]):
        """添加网络接口信息"""
        ipv4 = []
        ipv6 = []
        mac = ""

        for addr in interface_addresses:
            # 兼容不同平台: 用 family.name 判断
            family_name = getattr(addr.family, 'name', str(addr.family))
            if family_name == 'AF_INET':
                ipv4.append(addr.address)
            elif family_name == 'AF_INET6':
                # 过滤IPv6 link-local地址(fe80::)
                if not addr.address.startswith('fe80'):
                    ipv6.append(addr.address)
            elif family_name in ('AF_PACKET', 'AF_LINK'):
                mac = addr.address

        if ipv4 or ipv6 or mac:
            interface = {
                "接口名称": interface_name,
                "IPv4地址": ", ".join(ipv4) if ipv4 else "无",
                "IPv6地址": ", ".join(ipv6) if ipv6 else "无",
                "MAC地址": mac if mac else "未知"
            }
            # 默认网关 (按接口匹配)
            if interface_name in gateway_map:
                interface["默认网关"] = gateway_map[interface_name]
            # DNS服务器 (只加到第一个有IPv4的接口)
            if dns_servers and ipv4:
                interface["DNS服务器"] = ", ".join(dns_servers)
            self.interfaces.append(interface)

    def _get_default_gateways(self) -> Dict[str, str]:
        """获取默认网关 (接口名 -> 网关IP)"""
        gateway_map = {}
        try:
            result = subprocess.run(
                ['ip', 'route', 'show', 'default'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    # 格式: default via <gateway> dev <interface>
                    match = re.search(r'default\s+via\s+(\S+)\s+dev\s+(\S+)', line)
                    if match:
                        gateway_map[match.group(2)] = match.group(1)
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass
        return gateway_map

    def _get_dns_servers(self) -> List[str]:
        """获取DNS服务器列表"""
        dns = []
        try:
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('nameserver'):
                        parts = line.split()
                        if len(parts) >= 2:
                            dns.append(parts[1])
        except (IOError, OSError):
            pass
        return dns

    def _add_network_stats(self):
        """添加网络统计信息"""
        stats = psutil.net_if_stats()
        io_counters = psutil.net_io_counters(pernic=True)

        for interface in self.interfaces:
            name = interface["接口名称"]

            if name in stats:
                stat = stats[name]
                interface["状态"] = "启用" if stat.isup else "关闭"
                # 速度显示优化: >=1000 Mbps 显示 Gbps
                if stat.speed:
                    if stat.speed >= 1000:
                        interface["速度"] = f"{stat.speed / 1000:.0f} Gbps"
                    else:
                        interface["速度"] = f"{stat.speed} Mbps"
                else:
                    interface["速度"] = "未知"
                interface["MTU"] = str(stat.mtu) if stat.mtu else "未知"

            if name in io_counters:
                io = io_counters[name]
                interface["发送字节数"] = format_size(io.bytes_sent)
                interface["接收字节数"] = format_size(io.bytes_recv)
                interface["发送包数"] = str(io.packets_sent)
                interface["接收包数"] = str(io.packets_recv)
                interface["发送错误"] = str(io.errout)
                interface["接收错误"] = str(io.errin)

    def _add_sysfs_info(self):
        """从sysfs获取接口信息(接口类型、双工模式、链路状态)"""
        for interface in self.interfaces:
            name = interface["接口名称"]
            base_path = f'/sys/class/net/{name}'

            # 接口类型判断: /sys/class/net/{name}/device 存在则为物理网卡
            device_path = f'{base_path}/device'
            if os.path.exists(device_path) or os.path.islink(device_path):
                interface["接口类型"] = "物理网卡"
            else:
                interface["接口类型"] = "虚拟网卡"

            # 双工模式
            duplex = self._read_sysfs(f'{base_path}/duplex')
            if duplex and duplex != 'unknown':
                interface["双工模式"] = duplex

            # 链路状态 (operstate: up/down/unknown)
            operstate = self._read_sysfs(f'{base_path}/operstate')
            if operstate:
                state_map = {'up': '连接', 'down': '断开', 'unknown': '未知'}
                interface["链路状态"] = state_map.get(operstate, operstate)

    def _read_sysfs(self, path: str) -> str:
        """读取sysfs文件"""
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except (IOError, OSError):
            return ""

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
                    firmware_match = re.search(r'firmware-version:\s*(.+)', output)
                    bus_match = re.search(r'bus-info:\s*(.+)', output)

                    if driver_match:
                        interface["驱动程序"] = driver_match.group(1).strip()
                    if version_match:
                        interface["驱动版本"] = version_match.group(1).strip()
                    if firmware_match:
                        interface["固件版本"] = firmware_match.group(1).strip()
                    if bus_match:
                        interface["总线信息"] = bus_match.group(1).strip()
            except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
                pass

            # 尝试从sysfs获取驱动信息 (ethtool不可用时的fallback)
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
                except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
                    pass

    def _add_pci_vendor_info(self):
        """为每个网卡接口补充厂商/型号（sysfs PCI ID + lspci + MAC OUI 多级识别）

        仅新增"厂商"/"型号"两个字段并插入到"接口名称"之后，
        不改动其他字段的含义与顺序，对虚拟网卡安全降级为"未知"。
        """
        if not self._pci_nics:
            self._pci_nics = self._load_pci_nics()

        for interface in self.interfaces:
            name = interface.get("接口名称", "")
            vendor, model = self._detect_nic_vendor(name, interface.get("MAC地址", ""))
            self._attach_vendor_fields(interface, vendor, model)

    def _load_pci_nics(self) -> List[Dict[str, str]]:
        """运行一次 lspci -nn，解析网卡类设备（运行失败返回空列表）"""
        try:
            result = subprocess.run(['lspci', '-nn'],
                                    capture_output=True, text=True, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            return []
        if result.returncode != 0:
            return []
        return self._parse_lspci_nics(result.stdout)

    def _parse_lspci_nics(self, output: str) -> List[Dict[str, str]]:
        """解析 lspci -nn 输出中的网卡设备（以太网/IB/无线）"""
        nics: List[Dict[str, str]] = []
        for line in output.splitlines():
            match = self._LSPCI_NIC_RE.match(line.strip())
            if not match:
                continue
            device_desc = match.group('device').strip()
            vendor_id = f"0x{match.group('vendor_id').lower()}"
            vendor = pci_vendor_name(vendor_id) or self._clean_desc_vendor(device_desc)
            if not vendor:
                vendor = vendor_id
            model = strip_vendor_prefix(device_desc, vendor)
            nics.append({
                "vendor_id": vendor_id,
                "device_id": f"0x{match.group('device_id').lower()}",
                "vendor": vendor,
                "model": model or device_desc,
            })
        return nics

    @staticmethod
    def _clean_desc_vendor(desc: str) -> str:
        """从 lspci 描述文本推断厂商名（vendor ID 无映射时的兜底）"""
        desc_lower = desc.lower()
        for keyword, name in (
            ("intel", "Intel"), ("mellanox", "NVIDIA (Mellanox)"), ("nvidia", "NVIDIA"),
            ("realtek", "Realtek (瑞昱)"), ("broadcom", "Broadcom (博通)"),
            ("huawei", "华为 (Huawei/HiSilicon)"), ("hisilicon", "华为 (Huawei/HiSilicon)"),
            ("atheros", "Qualcomm Atheros"), ("qualcomm", "Qualcomm Atheros"),
            ("aquantia", "Aquantia"), ("qlogic", "QLogic"), ("emulex", "Emulex (Broadcom)"),
            ("chelsio", "Chelsio"), ("vmware", "VMware"), ("virtio", "Red Hat (Virtio)"),
            ("amazon", "Amazon (AWS)"), ("oracle", "Oracle (Sun)"), ("sun ", "Oracle (Sun)"),
        ):
            if keyword in desc_lower:
                return name
        return ""

    def _detect_nic_vendor(self, name: str, mac: str):
        """识别单个网卡的厂商与型号

        识别顺序:
        1. sysfs 的 PCI vendor/device ID 匹配 lspci 网卡列表（最准确）
        2. sysfs PCI vendor ID 查内置 PCI 厂商表
        3. MAC 地址 OUI 查内置厂商表（容器/虚拟机环境常用）
        识别不到时返回 ("未知", "未知")，不影响其他字段
        """
        vendor_id = self._read_pci_id(f'/sys/class/net/{name}/device/vendor')
        device_id = self._read_pci_id(f'/sys/class/net/{name}/device/device')

        if vendor_id:
            # 1. sysfs ID 与 lspci 列表精确匹配
            if device_id:
                for nic in self._pci_nics:
                    if nic["vendor_id"] == vendor_id and nic["device_id"] == device_id:
                        return nic["vendor"], nic["model"]
            # 2. sysfs vendor ID 查内置表
            vendor = pci_vendor_name(vendor_id)
            if vendor:
                model = f"PCI设备 {vendor_id}:{device_id}" if device_id else f"PCI设备 {vendor_id}"
                return vendor, model
            return vendor_id, f"PCI设备 {vendor_id}:{device_id}" if device_id else vendor_id

        # 3. MAC OUI 识别（虚拟网卡常见）
        oui_vendor = lookup_oui(mac)
        if oui_vendor:
            return oui_vendor, "虚拟网卡"

        return "未知", "未知"

    @staticmethod
    def _read_pci_id(path: str) -> Optional[str]:
        """读取 sysfs 中的 PCI vendor/device ID（如 '0x8086'）"""
        try:
            with open(path, 'r') as f:
                value = f.read().strip().lower()
            return value if re.match(r'^0x[\da-f]{4}$', value) else None
        except (IOError, OSError):
            return None

    @staticmethod
    def _attach_vendor_fields(interface: Dict[str, Any], vendor: str, model: str):
        """把"厂商"/"型号"插入到"接口名称"之后，保持报告列顺序稳定"""
        ordered = {
            "接口名称": interface.get("接口名称", "未知"),
            "厂商": vendor,
            "型号": model,
        }
        for key, value in interface.items():
            if key != "接口名称":
                ordered[key] = value
        interface.clear()
        interface.update(ordered)

    def _add_windows_nic_vendor_info(self):
        """Windows下通过wmic补充网卡厂商/型号（失败时填未知）"""
        try:
            result = subprocess.run(
                ['wmic', 'nic', 'where', 'NetConnectionID!=""',
                 'get', 'NetConnectionID,Manufacturer,Name,ProductName'],
                capture_output=True, text=True, timeout=10
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            self._fill_unknown_vendors()
            return

        vendor_by_conn = {}
        if result.returncode == 0:
            for line in result.stdout.splitlines()[1:]:
                if not line.strip():
                    continue
                parts = re.split(r'\s{2,}|\t', line.strip())
                if len(parts) < 2:
                    continue
                conn_id = parts[0]
                manufacturer = parts[1] if len(parts) > 1 else "未知"
                name = parts[-1] if len(parts) > 2 else "未知"
                if conn_id:
                    vendor_by_conn[conn_id] = (manufacturer or "未知", name or "未知")

        for interface in self.interfaces:
            name = interface.get("接口名称", "")
            vendor, model = vendor_by_conn.get(name, ("未知", "未知"))
            self._attach_vendor_fields(interface, vendor, model)

    def _fill_unknown_vendors(self):
        """所有平台均无法识别时填"未知"，保证字段齐全"""
        for interface in self.interfaces:
            self._attach_vendor_fields(interface, "未知", "未知")

    def _sort_interfaces(self):
        """物理网卡优先排序"""
        self.interfaces.sort(
            key=lambda x: (0 if x.get("接口类型") == "物理网卡" else 1,
                           x.get("接口名称", ""))
        )
