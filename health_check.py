#!/usr/bin/env python3
# gpu-infra-probe 阶段4：健康检查模块
# 检测异常指标，给出健康评分（0-100）
#
# 阈值定义（来自 test.txt 任务4.1）：
#   GPU温度    正常 30-75°C    警告 75-82°C    异常 >82°C
#   功耗       <80% TDP        80-90% TDP     >90% TDP
#   ECC错误    0               >0             持续增长
#   P-State    P0-P2           P3-P5          P6-P12

import re
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# 阈值定义（任务4.1）
# ---------------------------------------------------------------------------
THRESHOLDS = {
    'temp': {'ok_max': 75, 'warn_max': 82},
    'power_ratio': {'ok_max': 0.8, 'warn_max': 0.9},
}


def extract_value(detail_data, field):
    """从 detail_data（字符串内容或 dict）中提取字段值
    detail_data 可以是：
      - 字符串：nvidia-smi -q 的原文（用正则）
      - dict：parse_detail 产出的字典（直接按 key 取）
    """
    if detail_data is None:
        return None
    if isinstance(detail_data, dict):
        # 字段名可能含空格，做一次映射
        key_map = {
            'GPU Current Temp': 'gpu_current_temp',
            'Power Draw': 'power_draw',
            'Power Limit': 'power_limit',
            'Performance State': 'performance_state',
        }
        return detail_data.get(key_map.get(field, field.lower().replace(' ', '_')))
    # 字符串模式
    if isinstance(detail_data, str):
        m = re.search(r'^\s*' + re.escape(field) + r'\s*:\s*(.+?)\s*$',
                      detail_data, re.MULTILINE)
        return m.group(1).strip() if m else None
    return None


def _parse_number(val):
    """把 nvidia-smi 输出的 '45.32 W' / '40 C' 解析成 float；失败返回 None"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    m = re.search(r'-?\d+(\.\d+)?', str(val))
    return float(m.group(0)) if m else None


def _is_na(val):
    """判断 vGPU 等场景下字段是否不可用"""
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in ('', 'n/a', '[n/a]', 'na', 'none')


def parse_ecc_summary(ecc_text):
    """从 nvidia-smi -q -d ECC 输出中汇总 Aggregate 错误计数（跨所有 GPU 的最大值）
    返回 {'double_bit': int, 'single_bit': int}
    """
    if not ecc_text:
        return {'double_bit': 0, 'single_bit': 0}

    # Aggregate 段下的 Double Bit / Single Bit Device Memory 行
    double_bits = re.findall(r'Double Bit\s*\n\s*Device Memory\s*:\s*(\d+)', ecc_text)
    single_bits = re.findall(r'Single Bit\s*\n\s*Device Memory\s*:\s*(\d+)', ecc_text)

    def _max(values):
        try:
            return max(int(v) for v in values) if values else 0
        except ValueError:
            return 0

    return {
        'double_bit': _max(double_bits),
        'single_bit': _max(single_bits),
    }


def check_health(detail_data):
    """检查GPU健康状态"""
    results = []

    # 提取指标
    temp = extract_value(detail_data, 'GPU Current Temp')
    power = extract_value(detail_data, 'Power Draw')
    power_limit = extract_value(detail_data, 'Power Limit')
    perf_state = extract_value(detail_data, 'Performance State')

    # 温度检查
    if _is_na(temp):
        results.append({'level': 'na', 'msg': '温度: N/A（vGPU 或不支持读取）'})
    else:
        temp_val = _parse_number(temp)
        if temp_val is not None:
            if temp_val > 82:
                results.append({'level': 'error', 'msg': f'温度过高: {temp_val:.1f}°C'})
            elif temp_val > 75:
                results.append({'level': 'warn', 'msg': f'温度偏高: {temp_val:.1f}°C'})
            else:
                results.append({'level': 'ok', 'msg': f'温度正常: {temp_val:.1f}°C'})
        else:
            results.append({'level': 'na', 'msg': f'温度无法解析: {temp}'})

    # 功耗检查
    if _is_na(power) or _is_na(power_limit):
        results.append({'level': 'na', 'msg': '功耗: N/A（vGPU 或不支持读取）'})
    else:
        p = _parse_number(power)
        pl = _parse_number(power_limit)
        if p is not None and pl and pl > 0:
            ratio = p / pl
            if ratio > 0.9:
                results.append({'level': 'error',
                                'msg': f'功耗过高: {p:.1f}W / {pl:.0f}W ({ratio*100:.0f}%)'})
            elif ratio > 0.8:
                results.append({'level': 'warn',
                                'msg': f'功耗偏高: {p:.1f}W / {pl:.0f}W ({ratio*100:.0f}%)'})
            else:
                results.append({'level': 'ok',
                                'msg': f'功耗正常: {p:.1f}W / {pl:.0f}W ({ratio*100:.0f}%)'})
        else:
            results.append({'level': 'na', 'msg': f'功耗无法解析: {power}/{power_limit}'})

    # 性能状态检查
    if _is_na(perf_state):
        results.append({'level': 'na', 'msg': 'P-State: N/A'})
    else:
        # perf_state 形如 'P0' / 'P2'
        m = re.match(r'P(\d+)', str(perf_state))
        if m:
            n = int(m.group(1))
            if n <= 2:
                results.append({'level': 'ok', 'msg': f'性能状态: P{n}（高性能）'})
            elif n <= 5:
                results.append({'level': 'warn', 'msg': f'性能状态: P{n}（中等）'})
            else:
                results.append({'level': 'error', 'msg': f'性能状态: P{n}（低性能）'})
        else:
            results.append({'level': 'warn', 'msg': f'性能状态: {perf_state}（非最高性能）'})

    # ECC 错误检查（detail_data['ecc_errors'] 为解析出的 {double_bit, single_bit}）
    ecc = detail_data.get('ecc_errors') if isinstance(detail_data, dict) else None
    if _is_na(ecc):
        # 没有 ECC 数据时，不算异常（vGPU 通常无 ECC 字段）
        results.append({'level': 'na', 'msg': 'ECC: N/A（未采集或不支持）'})
    elif isinstance(ecc, dict):
        double_bit = ecc.get('double_bit', 0) or 0
        single_bit = ecc.get('single_bit', 0) or 0
        if double_bit > 0:
            results.append({'level': 'error',
                            'msg': f'ECC: 不可纠正错误 {double_bit}（需立即处理）'})
        elif single_bit > 0:
            results.append({'level': 'warn',
                            'msg': f'ECC: 可纠正错误 {single_bit}（建议关注）'})
        else:
            results.append({'level': 'ok', 'msg': 'ECC: 无错误'})
    else:
        results.append({'level': 'ok', 'msg': f'ECC: {ecc}'})

    return results


def calc_health_score(checks):
    """计算健康评分（0-100）"""
    score = 100
    for check in checks:
        if check['level'] == 'error':
            score -= 20
        elif check['level'] == 'warn':
            score -= 5
        # 'na' / 'ok' 不扣分
    return max(0, score)


def run_health_check(detail_data):
    """完整健康检查流程：返回 {score, checks}"""
    checks = check_health(detail_data)
    score = calc_health_score(checks)
    # 若所有指标都是 N/A，则评分标记为 N/A（避免误导）
    if all(c['level'] == 'na' for c in checks):
        score = None
    return {'score': score, 'checks': checks}


def main():
    """读取 parse_detail 产出的 JSON 并生成 health_report.json"""
    data_dir = Path(__file__).parent / "data"
    detail_path = data_dir / "gpu_detail.json"
    if not detail_path.exists():
        print("未找到 gpu_detail.json，请先执行 parse_detail.py")
        return
    with open(detail_path, 'r', encoding='utf-8') as f:
        detail = json.load(f)

    # 附加 ECC 解析结果：把 ecc_errors_*.txt 解析成 {double_bit, single_bit} 总数
    ecc_files = sorted(data_dir.glob("ecc_errors_*.txt"), reverse=True)
    if ecc_files:
        try:
            with open(ecc_files[0], 'r', encoding='utf-8') as f:
                ecc_text = f.read()
            detail['ecc_errors'] = parse_ecc_summary(ecc_text)
        except Exception:
            pass

    report = run_health_check(detail)

    out_path = data_dir / "health_report.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"健康评分: {report['score'] if report['score'] is not None else 'N/A'} / 100")
    for c in report['checks']:
        print(f"  [{c['level'].upper():5s}] {c['msg']}")
    print(f"  -> JSON 已写出: {out_path}")


if __name__ == "__main__":
    main()
