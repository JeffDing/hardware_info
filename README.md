# 硬件信息查询工具

一个功能强大的硬件信息查询工具，支持多种硬件类型，包括国产GPU/NPU设备。

## 功能特性

### 支持的硬件类型

| 类型 | 支持设备 |
|------|----------|
| **系统信息** | 操作系统、主机名、处理器架构、BIOS版本等 |
| **CPU信息** | Intel、AMD、海光、兆芯、飞腾、鲲鹏等 |
| **GPU信息** | NVIDIA、AMD、Intel、摩尔线程、壁仞科技、沐曦、天数智芯、海光 |
| **NPU信息** | 华为昇腾（Ascend 910/950/310P） |
| **内存信息** | 总内存、可用内存、内存条数量、物理内存总容量、每根容量、内存厂商、内存型号、内存条详细信息 |
| **磁盘信息** | 分区信息、硬盘数量、硬盘总容量、每块容量、磁盘物理信息、SMART数据 |
| **网络信息** | IP地址、MAC地址、网卡厂商、网卡型号、网卡驱动、网络统计 |

### 国产GPGPU详细信息支持

- **壁仞科技 (brsmi)**: 型号、显存、温度、功耗、利用率、驱动版本、BIOS版本、性能状态
- **沐曦 (mx-smi)**: 型号、显存、温度、功耗、利用率、驱动版本、BIOS版本、MACA版本
- **摩尔线程 (musa-smi)**: MTT系列型号
- **天数智芯 (ixsmi)**: Iluvatar BI-V系列
- **海光 (rocm-smi)**: DCU系列

## 安装要求

### 系统要求

- Python 3.7+
- Linux / Windows / macOS

### 依赖包

```bash
pip install -r requirements.txt
```

或手动安装：

```bash
pip install psutil requests
```

### 可选依赖（用于特定硬件检测）

```bash
# GPU/NPU 检测工具
nvidia-smi     # NVIDIA GPU
rocm-smi       # AMD GPU / 海光 DCU
musa-smi       # 摩尔线程 GPU
brsmi          # 壁仞科技 GPU
mx-smi         # 沐曦 GPU
ixsmi          # 天数智芯 GPU
npu-smi        # 华为昇腾 NPU

# 系统信息增强检测
dmidecode      # 需要root权限
smartctl       # 磁盘SMART信息
ethtool        # 网卡驱动信息
lsblk          # 磁盘信息
```

## 使用方法

### 方式1：直接运行主程序

```bash
# 进入项目目录
cd /tmp/code

# 运行主程序（默认输出Markdown格式）
python3 main.py

# 保存到文件
python3 main.py --output report.md
```

### 方式2：作为模块导入

```python
from hardware_info import HardwareInfoCollector

collector = HardwareInfoCollector()
collector.collect_all()
collector.print_report()
```

### 输出示例

```
============================================================
硬件信息报告
============================================================

## 系统信息

| 操作系统 | Linux |
| 主机名 | server-01 |
| 处理器架构 | x86_64 |
| 发行版 | Ubuntu 22.04.5 LTS |
| 制造商 | ZTE |
| 产品型号 | R6900 G5 |

## GPU信息

### 设备 1

| 厂商 | 壁仞科技 |
| 型号 | BR100 |
| 类型 | GPGPU |
| 显存 | 64 GB (858 MiB已使用) |
| 温度 | 65°C |
| 功耗 | 280 W |
| 功耗上限 | 350 W |
| 利用率 | 15% |
| 驱动版本 | 3.4.4 |
| BIOS版本 | 1.24.3.0 |
| 性能状态 | P0 |

## 网卡信息

### 设备 1: eth0

| 厂商 | Intel |
| 型号 | 82599ES 10 Gigabit Network Connection |
| IPv4地址 | 192.168.1.10 |
| MAC地址 | 00:1B:21:11:22:33 |
| 驱动程序 | ixgbe |
```

## 硬件厂商/型号识别说明

### 网卡（Linux）

识别顺序（按可靠度从高到低，任一级成功即停止）：

1. **lspci + sysfs**：读取 `/sys/class/net/<接口>/device/vendor`、`device` 得到
   PCI Vendor/Device ID，与 `lspci -nn` 输出的网卡类设备（以太网 `[0200]`、
   InfiniBand `[0207]`、无线 `[0280]`）精确匹配，给出完整厂商与型号
2. **PCI 厂商表**：无 lspci 时，用 sysfs 的 PCI Vendor ID 查内置厂商表
   （`vendor_db.PCI_VENDOR_NAMES`）
3. **MAC OUI 表**：虚拟网卡（容器/虚拟机）无 PCI 设备时，用 MAC 地址前三段
   查内置厂商表（`vendor_db.MAC_OUI_VENDORS`，含 VMware/Hyper-V/KVM/Xen 等）

均识别不到时厂商/型号显示"未知"，不影响其余字段。

### 内存

`dmidecode -t memory` 解析出的每个内存条均包含制造商与部件号，报告在
"内存信息"中额外汇总输出"内存厂商"（如 `Samsung x 4`）与"内存型号"
（如 `M393A4K40DB3-CWE x 4`）。

## 单元测试

```bash
cd /tmp/code
python3 -m unittest discover -s tests -v
```

## 项目结构

```
hardware_info/
├── __init__.py          # 包初始化
├── base.py              # 基础常量和工具函数
├── vendor_db.py         # 厂商识别数据库（PCI ID / MAC OUI）
├── collector.py         # 主收集器
├── system_info.py       # 系统信息模块
├── cpu_info.py          # CPU信息模块
├── gpu_info.py          # GPU信息模块
├── npu_info.py          # NPU信息模块
├── memory_info.py       # 内存信息模块
├── disk_info.py         # 磁盘信息模块
└── network_info.py      # 网络信息模块

tests/
└── test_vendor_detection.py  # 厂商/型号识别单元测试

main.py                  # 主程序入口
requirements.txt         # 依赖包清单
README.md                # 说明文档
```

## 模块说明

| 模块 | 功能 |
|------|------|
| `base.py` | 基础常量、枚举定义、单位格式化、命令执行工具 |
| `vendor_db.py` | 厂商识别数据库：PCI Vendor ID → 厂商名、MAC OUI → 厂商名、型号名称清洗 |
| `system_info.py` | 系统信息收集（Linux/Windows/macOS DMI信息） |
| `cpu_info.py` | CPU信息收集（含国产CPU厂商识别） |
| `gpu_info.py` | GPU信息收集（支持壁仞、沐曦等详细信息） |
| `npu_info.py` | NPU信息收集（华为昇腾910/950/310P） |
| `memory_info.py` | 内存信息收集（含内存条数量、物理总容量、每根容量、厂商、型号及内存条详细信息） |
| `disk_info.py` | 磁盘信息收集（含硬盘数量、总容量、每块容量、SMART数据） |
| `network_info.py` | 网络信息收集（含网卡厂商/型号识别、驱动信息） |
| `collector.py` | 主收集器，整合所有模块 |

## 支持的国产硬件

### GPU/GPGPU

| 厂商 | 检测工具 | 详细信息 |
|------|----------|----------|
| NVIDIA | nvidia-smi | 型号、驱动版本、显存 |
| AMD | rocm-smi | 型号 |
| Intel | lspci | 型号 |
| 摩尔线程 | musa-smi | 型号 |
| 壁仞科技 | brsmi | 显存、温度、功耗、利用率、驱动、BIOS、性能状态 |
| 沐曦 | mx-smi | 显存、温度、功耗、利用率、驱动、BIOS、MACA、性能状态 |
| 天数智芯 | ixsmi | 型号 |
| 海光 | rocm-smi | 型号 |

### NPU

| 厂商 | 检测工具 | 详细信息 |
|------|----------|----------|
| 华为昇腾 | npu-smi | 型号、产品类型、HBM/DDR容量、温度、功耗、利用率、固件版本、板卡ID、芯片版本 |

### CPU

| 厂商 | 识别方式 |
|------|----------|
| Intel | model name、vendor ID (GenuineIntel) |
| AMD | model name、vendor ID (AuthenticAMD) |
| 海思 (鲲鹏) | model name、CPU implementer |
| 飞腾 | model name、CPU part |
| 海光 | vendor ID、model name |
| 兆芯 | vendor ID、model name |

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request。
