#!/usr/bin/env python3
# gpu-infra-probe 阶段5：整合入口
# 一个命令完成采集 → 解析 → 健康检查 → 报告生成 → 输出路径
#
# 用法：
#   python run_probe.py        # 走完整 5 步流程
#   python run_probe.py --skip-collect   # 跳过采集，复用上次 data/ 下数据

import os
import sys
import subprocess
import platform
import argparse
from pathlib import Path
from datetime import datetime

# 让 "import parse_basic" 等子模块可以直接工作
sys.path.insert(0, str(Path(__file__).parent))


def run_collect():
    """1. 执行采集脚本 collect.sh"""
    script = Path(__file__).parent / "collect.sh"
    if not script.exists():
        print("[ERROR] collect.sh 不存在")
        return False

    # 跨平台兼容：Linux 直接执行，Windows 用 Git Bash / WSL 调用
    if platform.system() == "Windows":
        # 优先使用 WSL；如果没有再尝试 git bash
        try:
            subprocess.run(["bash", str(script)], check=True)
        except FileNotFoundError:
            try:
                subprocess.run(["C:/Program Files/Git/bin/bash.exe", str(script)],
                                check=True)
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                print(f"[ERROR] Windows 下找不到 bash：{e}")
                print("  请在 WSL/Git Bash 中运行，或在 Linux GPU 实例上执行。")
                return False
    else:
        subprocess.run(["bash", str(script)], check=True)
    return True


def run_parse():
    """2. 调用各解析模块"""
    import parse_basic
    import parse_detail
    import parse_topo

    print("  - parse_basic.py ...")
    parse_basic.main()
    print("  - parse_detail.py ...")
    parse_detail.main()
    print("  - parse_topo.py ...")
    parse_topo.main()


def run_health():
    """3. 执行健康检查"""
    import health_check
    health_check.main()


def run_report():
    """4. 生成可视化报告"""
    import generate_report
    generate_report.main()
    # 找出最新生成的 report_*.html
    files = sorted(Path(__file__).parent.glob("report_*.html"), reverse=True)
    return files[0] if files else None


def main():
    parser = argparse.ArgumentParser(description="GPU 资产巡检工具")
    parser.add_argument("--skip-collect", action="store_true",
                        help="跳过采集步骤，复用 data/ 下已有数据")
    args = parser.parse_args()

    print("🔍 GPU资产巡检工具 v1.0")
    print("=" * 50)

    # 1. 执行采集
    print("[1/5] 采集硬件数据...")
    if args.skip_collect:
        print("  -> 已跳过采集（--skip-collect）")
    else:
        if not run_collect():
            print("[FATAL] 采集失败，终止流程。")
            sys.exit(1)

    # 2. 解析数据
    print("[2/5] 解析数据...")
    try:
        run_parse()
    except Exception as e:
        print(f"[ERROR] 解析阶段失败: {e}")
        sys.exit(1)

    # 3. 健康检查
    print("[3/5] 执行健康检查...")
    try:
        run_health()
    except Exception as e:
        print(f"[WARN] 健康检查失败: {e}")

    # 4. 生成可视化报告
    print("[4/5] 生成HTML报告...")
    try:
        report_path = run_report()
    except Exception as e:
        print(f"[ERROR] 报告生成失败: {e}")
        sys.exit(1)

    # 5. 输出结果
    print("[5/5] ✅ 完成！")
    if report_path:
        print(f"  报告路径: {report_path}")
        # 在 Windows / Linux 下尝试自动打开浏览器
        try:
            if platform.system() == "Windows":
                os.startfile(str(report_path))  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(report_path)])
            else:
                subprocess.run(["xdg-open", str(report_path)])
        except Exception:
            pass


if __name__ == "__main__":
    main()
