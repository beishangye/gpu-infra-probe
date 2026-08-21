#!/usr/bin/env python3
# gpu-infra-probe 阶段3：可视化层
# 读取阶段2产出的 JSON + 健康检查结果，填充 HTML 模板，生成最终报告

import json
from pathlib import Path
from datetime import datetime


TEMPLATE_PATH = Path(__file__).parent / "report_template.html"
DATA_DIR = Path(__file__).parent / "data"
PLACEHOLDER = "__REPORT_DATA_PLACEHOLDER__"


def _load_json(name):
    p = DATA_DIR / name
    if p.exists():
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def _read_text(name):
    """读取 data 下匹配 pattern 的最新文件文本"""
    files = sorted(DATA_DIR.glob(name), reverse=True)
    if not files:
        return None
    try:
        with open(files[0], 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


def generate_html(gpu_info, detail_info, topo_info, output_path,
                 health=None, system=None):
    """生成完整的HTML报告

    参数：
      gpu_info:    list[dict]  parse_basic 产出的 GPU 基础信息
      detail_info: dict        parse_detail 产出的关键字段
      topo_info:   dict        parse_topo 产出的拓扑结构
      output_path: str         最终 HTML 路径
      health:      dict        health_check 产出的 {score, checks}
      system:      dict        附加系统信息（kernel / pci_devices / ecc）
    """
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        template = f.read()

    report_data = {
        "gpus": gpu_info or [],
        "detail": detail_info or {},
        "topology": topo_info or {},
        "health": health or {"score": None, "checks": []},
        "system": system or {},
    }
    # 把 JSON 写成 JS 字面量（避免 </script> 注入风险）
    data_js = json.dumps(report_data, ensure_ascii=False, indent=2)
    data_js = data_js.replace('</', '<\\/')

    filled = template.replace(PLACEHOLDER, data_js)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(filled)
    print(f"报告已生成: {output_path}")
    return output_path


def main():
    gpus = _load_json("gpu_info.json") or []
    detail = _load_json("gpu_detail.json") or {}
    topo = _load_json("gpu_topology.json") or {}

    health = _load_json("health_report.json") or {"score": None, "checks": []}

    # 读取系统信息文本（uname/os-release / lspci / ecc）
    system = {
        "kernel": _read_text("system_info_*.txt"),
        "pci_devices": _read_text("pci_devices_*.txt"),
        "ecc": _read_text("ecc_errors_*.txt"),
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(__file__).parent / f"report_{ts}.html"
    generate_html(gpus, detail, topo, str(out_path), health=health, system=system)


if __name__ == "__main__":
    main()
