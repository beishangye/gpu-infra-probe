#!/usr/bin/env python3
# gpu-infra-probe 阶段2：解析层
# 解析 nvidia-smi --query-gpu 输出的 CSV 文件，输出结构化 JSON

import csv
import json
from pathlib import Path


def parse_gpu_basic(csv_path):
    """解析nvidia-smi --query-gpu输出的CSV文件"""
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        gpus = list(reader)
    # 统一字段名（去除可能的前后空格）
    for gpu in gpus:
        for k in list(gpu.keys()):
            gpu[k.strip()] = (gpu[k] or '').strip()
    return gpus


def find_latest(data_dir, pattern):
    """在 data_dir 下找最新的匹配 pattern 的文件"""
    data_dir = Path(data_dir)
    files = sorted(data_dir.glob(pattern), reverse=True)
    return files[0] if files else None


def merge_usage(gpus, usage_csv):
    """把任务1.2追加的 usage CSV（memory.used / temperature / power）合并进 gpu 列表"""
    if not usage_csv or not Path(usage_csv).exists():
        return gpus
    with open(usage_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        usage = {row['index']: row for row in reader if 'index' in row}
    for gpu in gpus:
        idx = gpu.get('index')
        if idx in usage:
            for k, v in usage[idx].items():
                # 避免覆盖已有 key，给 usage 字段加前缀
                gpu.setdefault(k, v)
    return gpus


def main():
    # 找到最新的CSV文件
    data_dir = Path("./data")
    csv_files = sorted(data_dir.glob("gpu_basic_*.csv"), reverse=True)
    if not csv_files:
        print("未找到CSV文件")
        return

    gpus = parse_gpu_basic(csv_files[0])

    # 合并 usage CSV（温度/功耗/显存使用率）
    usage_csv = find_latest(data_dir, "gpu_usage_*.csv")
    gpus = merge_usage(gpus, usage_csv)

    # 输出JSON供后续使用
    out_path = Path("./data/gpu_info.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(gpus, f, indent=2, ensure_ascii=False)

    print(f"解析完成，共{len(gpus)}张GPU")
    for gpu in gpus:
        print(f"  - {gpu.get('name', 'N/A')}: {gpu.get('memory.total', 'N/A')}")
    print(f"  -> JSON 已写出: {out_path}")


if __name__ == "__main__":
    main()
