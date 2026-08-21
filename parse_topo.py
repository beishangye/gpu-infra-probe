#!/usr/bin/env python3
# gpu-infra-probe 阶段2：解析层
# 解析 nvidia-smi topo -m 输出的拓扑矩阵，输出为 JSON 供可视化使用

import re
import json
from pathlib import Path

# 拓扑矩阵中的连接类型含义（与 test.txt 任务3.2 一致）
LINK_TYPE_MAP = {
    'NV': 'NVLink',     # NV# = NVLink
    'PIX': 'PCIe Bridge',
    'PXB': 'PCIe Switch',
    'SYS': 'Cross-NUMA',
    'X': 'Self',        # 对角线
    'N/A': 'Unavailable',
}


def parse_topo(txt_path):
    """解析nvidia-smi topo -m输出的拓扑矩阵"""
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 找到矩阵开始的行（包含 GPU0 表头的那一行）
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith('GPU0'):
            start = i
            break

    if start is None:
        return None

    # 表头行：GPU0  GPU1  GPU2 ... CPU Affinity  NUMA Affinity
    header = lines[start].strip().split()
    gpu_columns = [h for h in header if re.match(r'^GPU\d+$', h)]

    # 解析矩阵行（简化的解析）
    topo_data = {}
    rows = []
    for line in lines[start + 1:]:
        parts = line.strip().split()
        if parts and re.match(r'^GPU\d+$', parts[0]):
            rows.append(parts)
        # 一旦遇到非矩阵行（如 Legend），就停止
        elif rows and not line.strip():
            break

    # rows[i][0] = GPUi, rows[i][1:1+N] = 到 GPU0..GPUN 的连接类型
    for row in rows:
        gpu_id = row[0]
        connections = {}
        for j, target in enumerate(gpu_columns):
            cell = row[j + 1] if j + 1 < len(row) else 'N/A'
            if gpu_id == target:
                connections[target] = 'X'  # 对角线
            else:
                connections[target] = cell
        # CPU Affinity / NUMA Affinity 是最后两列
        cpu_affinity = row[1 + len(gpu_columns)] if 1 + len(gpu_columns) < len(row) else None
        numa_affinity = row[2 + len(gpu_columns)] if 2 + len(gpu_columns) < len(row) else None
        topo_data[gpu_id] = {
            'connections': connections,
            'cpu_affinity': cpu_affinity,
            'numa_affinity': numa_affinity,
        }

    return {
        'gpu_list': gpu_columns,
        'matrix': topo_data,
        'link_types': LINK_TYPE_MAP,
    }


def main():
    data_dir = Path("./data")
    files = sorted(data_dir.glob("topology_*.txt"), reverse=True)
    if not files:
        print("未找到 topology_*.txt 文件")
        return

    topo = parse_topo(files[0])
    if not topo:
        print("拓扑矩阵解析失败")
        return

    out_path = Path("./data/gpu_topology.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(topo, f, indent=2, ensure_ascii=False)

    gpu_count = len(topo.get('gpu_list', []))
    print(f"拓扑解析完成，共 {gpu_count} 张 GPU")
    for gpu_id, data in topo.get('matrix', {}).items():
        conns = data['connections']
        non_self = [f"{k}={v}" for k, v in conns.items() if v != 'X']
        print(f"  - {gpu_id}: {', '.join(non_self) if non_self else '单卡/无互联'}")
    print(f"  -> JSON 已写出: {out_path}")


if __name__ == "__main__":
    main()
