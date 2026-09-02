# 硬件信息查询工具

一个功能强大的硬件信息查询工具，支持多种硬件类型，包括国产GPU/NPU设备。

## 功能特性

### 支持的硬件类型

| 类型 | 支持设备 |
|------|----------|
| **系统信息** | 操作系统、主机名、处理器架构、BIOS版本等 |
| **CPU信息** | Intel、AMD、海光、兆芯、飞腾、鲲鹏等 |
| **GPU信息** | NVIDIA、AMD、Intel、摩尔线程、壁仞科技、沐曦、天数智芯、海光 |
| **NPU信息** | 华为昇腾（Ascend 910/950） |
| **内存信息** | 总内存、可用内存、内存条详细信息 |
| **磁盘信息** | 分区信息、磁盘物理信息、SMART数据 |
| **网络信息** | IP地址、MAC地址、网卡驱动、网络统计 |

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

## 安装方法

### 方式1：克隆仓库

```bash
git clone <repository-url>
cd hardware_info
pip install -e .
```

### 方式2：直接使用

```bash
# 直接复制 hardware_info 目录到项目中使用
cp -r hardware_info /path/to/your/project/
```

## 使用方法

### 命令行使用

```bash
# 基本使用 - 打印报告
python3 main.py

# 输出JSON格式
python3 main.py --json

# 保存到文件
python3 main.py --output report.txt
python3 main.py --json --output report.json

# 显示帮助
python3 main.py --help

# 显示版本
python3 main.py --version
```

### Python API 使用

```python
from hardware_info import HardwareInfoCollector

# 创建收集器
collector = HardwareInfoCollector()

# 收集所有硬件信息
data = collector.collect_all()

# 单独收集特定类型信息
system_info = collector.get_system_info()
cpu_info = collector.get_cpu_info()
gpu_info = collector.get_gpu_info()
npu_info = collector.get_npu_info()
memory_info = collector.get_memory_info()
disk_info = collector.get_disk_info()
network_info = collector.get_network_info()

# 打印报告
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
```

## 项目结构

```
hardware_info/
├── __init__.py          # 包初始化
├── base.py              # 基础常量和工具函数
├── collector.py         # 主收集器
├── system_info.py       # 系统信息模块
├── cpu_info.py          # CPU信息模块
├── gpu_info.py          # GPU信息模块
├── npu_info.py          # NPU信息模块
├── memory_info.py       # 内存信息模块
├── disk_info.py         # 磁盘信息模块
└── network_info.py      # 网络信息模块

main.py                  # 主程序入口
README.md                # 说明文档
```

## 模块说明

| 模块 | 功能 |
|------|------|
| `base.py` | 基础常量、枚举定义、单位格式化、命令执行工具 |
| `system_info.py` | 系统信息收集（Linux/Windows/macOS DMI信息） |
| `cpu_info.py` | CPU信息收集（含国产CPU厂商识别） |
| `gpu_info.py` | GPU信息收集（支持壁仞、沐曦等详细信息） |
| `npu_info.py` | NPU信息收集（华为昇腾910/950） |
| `memory_info.py` | 内存信息收集（含内存条详细信息） |
| `disk_info.py` | 磁盘信息收集（支持SMART数据） |
| `network_info.py` | 网络信息收集（含驱动信息） |
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
| 华为昇腾 | npu-smi | 型号、功耗、温度、HBM使用率、利用率 |

### CPU

| 厂商 | 识别方式 |
|------|----------|
| Intel | model name、vendor ID (GenuineIntel) |
| AMD | model name、vendor ID (AuthenticAMD) |
| 海思 (鲲鹏) | model name、CPU implementer |
| 飞腾 | model name、CPU part |
| 海光 | vendor ID、model name |
| 兆芯 | vendor ID、model name |

## 常见问题

### Q: 为什么某些硬件信息显示"无数据"？

A: 可能原因：
1. 未安装对应的检测工具（如 brsmi、mx-smi 等）
2. 没有足够的权限（某些命令需要 root 或 sudo）
3. 硬件不存在或未正确安装

### Q: 如何获取更详细的内存信息？

A: `dmidecode` 命令需要 root 权限，可以使用：
```bash
sudo python3 main.py
```

### Q: 壁仞/沐曦 GPU 显示详细信息需要什么？

A: 需要安装对应厂商的驱动和 SMI 工具：
- 壁仞：安装 biren 驱动，确保 `brsmi` 命令可用
- 沐曦：安装 metax 驱动，确保 `mx-smi` 命令可用

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request。
