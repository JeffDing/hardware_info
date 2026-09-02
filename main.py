#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬件信息查询工具 - 主程序入口

用法:
    python3 main.py [--output FILE]

示例:
    python3 main.py                     # 打印报告
    python3 main.py --output report.md  # 保存到文件
"""

import argparse

from hardware_info import HardwareInfoCollector


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="硬件信息查询工具")
    parser.add_argument('--output', '-o', type=str, help='输出到文件')
    parser.add_argument('--version', '-v', action='version', version='%(prog)s 1.0.0')
    args = parser.parse_args()

    # 收集硬件信息
    collector = HardwareInfoCollector()
    collector.collect_all()

    # 输出Markdown格式报告
    output = collector._generate_report()

    # 输出到文件或屏幕
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"报告已保存到: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
