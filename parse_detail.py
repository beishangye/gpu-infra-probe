#!/usr/bin/env python3
# gpu-infra-probe 阶段2：解析层
# 解析 nvidia-smi -q 输出的文本文件，提取关键字段
# 扩展：PCIe 链路、性能状态、显存使用率（任务2.2 扩展练习）

import re
import json
from pathlib import Path


def extract_value(content, field):
    """通用提取：从键值对文本中提取字段值
    nvidia-smi -q 的输出格式为 `    Field Name : value`
    """
    # 字段名可能前缀若干空格；值前可能也有空格
    match = re.search(r'^\s*' + re.escape(field) + r'\s*:\s*(.+?)\s*$', content, re.MULTILINE)
    return match.group(1).strip() if match else None


def extract_section(content, section_name):
    """提取某个段（如 FB Memory Usage）下的所有键值对，返回 dict"""
    pattern = re.compile(
        r'^\s*' + re.escape(section_name) + r'\s*$\n((?:\s+\S.*:\s*.+\n?)+)',
        re.MULTILINE
    )
    m = pattern.search(content)
    if not m:
        return {}
    block = m.group(1)
    result = {}
    for line in block.splitlines():
        km = re.match(r'\s+(\S.*?):\s*(.+)$', line)
        if km:
            result[km.group(1).strip()] = km.group(2).strip()
    return result


def parse_detail(txt_path):
    """解析nvidia-smi -q输出的文本文件"""
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取关键字段
    driver_match = re.search(r'Driver Version\s*:\s*(.+)', content)
    cuda_match = re.search(r'CUDA Version\s*:\s*(.+)', content)

    # 提取GPU相关信息（第一个GPU）
    gpu_match = re.search(r'Product Name\s*:\s*(.+)', content)
    mem_match = re.search(r'Total\s*:\s*(.+)', content)

    # 扩展练习：PCIe、性能状态、显存使用率
    pci_gen = extract_value(content, 'PCIe Generation')
    link_width = extract_value(content, 'Link Width')
    perf_state = extract_value(content, 'Performance State')
    fb_mem = extract_section(content, 'FB Memory Usage')

    # 健康检查需要的字段（任务4.2）：温度、功耗、Power Limit
    gpu_temp = extract_value(content, 'GPU Current Temp')
    power_draw = extract_value(content, 'Power Draw')
    power_limit = extract_value(content, 'Power Limit')

    info = {
        "driver_version": driver_match.group(1).strip() if driver_match else None,
        "cuda_version": cuda_match.group(1).strip() if cuda_match else None,
        "product_name": gpu_match.group(1).strip() if gpu_match else None,
        "memory_total": mem_match.group(1).strip() if mem_match else None,
        # 扩展字段
        "pcie_generation": pci_gen,
        "link_width": link_width,
        "performance_state": perf_state,
        "fb_memory_usage": {
            "total": fb_mem.get('Total'),
            "used": fb_mem.get('Used'),
            "free": fb_mem.get('Free'),
        },
        # 健康检查所需字段
        "gpu_current_temp": gpu_temp,
        "power_draw": power_draw,
        "power_limit": power_limit,
    }
    return info


def main():
    data_dir = Path("./data")
    files = sorted(data_dir.glob("gpu_detail_*.txt"), reverse=True)
    if not files:
        print("未找到 gpu_detail_*.txt 文件")
        return
    info = parse_detail(files[0])

    out_path = Path("./data/gpu_detail.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

    print("详情解析完成：")
    for k, v in info.items():
        if k == 'fb_memory_usage':
            print(f"  - fb_memory_usage: {v}")
        else:
            print(f"  - {k}: {v}")
    print(f"  -> JSON 已写出: {out_path}")


if __name__ == "__main__":
    main()
