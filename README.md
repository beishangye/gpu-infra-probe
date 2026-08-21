# gpu-infra-probe

> GPU 数据中心资产自动巡检工具 + HTML 可视化报告
>
> 一条命令完成硬件采集、数据解析、健康检查与交互式 HTML 报告生成。

## 项目简介

`gpu-infra-probe` 通过 `nvidia-smi`、`lspci`、`dmidecode` 等工具自动采集 GPU 服务器的硬件原始数据，使用 Python 解析为结构化 JSON，再根据阈值规则做健康评分，最终生成一份包含基本信息表、健康评分、异常提示、互联拓扑图的 HTML 报告。

适用于数据中心巡检、上架验收、运维周报等场景。

## 功能特性

- **5 阶段一键流程**：采集 → 解析 → 健康检查 → 报告生成 → 浏览器自启动
- **采集项**：基础信息、显存使用率、温度/功耗、ECC、拓扑矩阵、PCIe 设备、系统/DMI 信息
- **解析层**：纯 Python 标准库实现（无第三方依赖），输出 JSON
- **可视化**：Bootstrap 5 + ECharts，表格 / 评分卡 / 力导向拓扑图
- **健康评分**：温度、功耗/ TDP、P-State、ECC 四项加权评分（0-100）
- **vGPU 友好**：vGPU 无法读取的字段标记为 `N/A`，不会误报异常

## 目录结构

```
gpu-infra-probe/
├── collect.sh                # 阶段1：硬件数据采集脚本
├── parse_basic.py            # 阶段2：CSV 基础信息解析
├── parse_detail.py           # 阶段2：nvidia-smi -q 文本字段解析
├── parse_topo.py             # 阶段2：topo -m 拓扑矩阵解析
├── health_check.py           # 阶段4：健康检查 + 评分
├── report_template.html      # 阶段3：HTML 报告模板
├── generate_report.py        # 阶段3：数据注入模板生成最终报告
├── run_probe.py              # 阶段5：主入口
├── docs/
│   └── 字段速查手册.md        # GPU 硬件字段含义速查表
├── data/                     # 采集 & 解析产物（运行时生成，不入库）
├── report_*.html             # 最终报告（运行时生成，不入库）
└── README.md
```

## 快速开始

### 环境要求

| 组件 | 版本/说明 |
|------|----------|
| 操作系统 | Linux（推荐）/ WSL2 / Git Bash |
| Python | ≥ 3.8 |
| NVIDIA Driver | ≥ 470 |
| 命令行工具 | `nvidia-smi`（必需）、`lspci`（推荐）、`dmidecode`（可选） |

> 在没有 GPU 的机器上也可运行：`collect.sh` 会自动检测工具缺失并写入占位数据，下游流程不受影响，可用来验证流程是否跑通。

### 部署步骤

```bash
# 1. 克隆仓库
git clone https://github.com/<your-name>/gpu-infra-probe.git
cd gpu-infra-probe

# 2. 给采集脚本执行权限
chmod +x collect.sh

# 3. 一键执行全套流程
python3 run_probe.py
```

### 跳过采集（复用已有数据）

如果你只想重新生成报告（例如改了模板），不需要重新跑 `nvidia-smi`：

```bash
python3 run_probe.py --skip-collect
```

### 分步执行（调试用）

```bash
# 阶段1：采集
./collect.sh

# 阶段2：分别解析
python3 parse_basic.py
python3 parse_detail.py
python3 parse_topo.py

# 阶段4：健康检查
python3 health_check.py

# 阶段3：生成 HTML 报告
python3 generate_report.py
```

## 验证

执行 `python3 run_probe.py` 后：

1. 终端会依次打印 `[1/5] ~ [5/5]` 步骤进度
2. `data/` 目录下应有以下 JSON 产物：
   - `gpu_info.json` —— GPU 基础信息列表
   - `gpu_detail.json` —— 关键字段（驱动/CUDA/PCIe/P-State/FB Memory）
   - `gpu_topology.json` —— 拓扑矩阵
   - `health_report.json` —— 健康评分 + 检查项
3. 项目根目录会生成 `report_YYYYMMDD_HHMMSS.html`，浏览器自动打开
4. 报告中应能看到：GPU 基本信息表、健康评分、拓扑图、系统信息

## 健康检查阈值

| 指标 | 正常 | 警告 | 异常 | 数据来源 |
|------|------|------|------|----------|
| GPU 温度 | ≤75°C | 75-82°C | >82°C | `nvidia-smi -q` 的 `GPU Current Temp` |
| 功耗/TDP | <80% | 80-90% | >90% | `Power Draw` / `Power Limit` |
| ECC 错误计数 | 0 | — | >0 | `nvidia-smi -q -d ECC` |
| P-State | P0-P2 | P3-P5 | P6-P12 | `Performance State` |

评分规则：基础分 100，每条 `error` 扣 20，每条 `warn` 扣 5，最低 0；所有指标均为 N/A 时评分显示 `N/A`。

## 交付物清单

| 交付物 | 路径 | 说明 |
|--------|------|------|
| 源代码仓库 | GitHub | 包含全部 Shell / Python 脚本 |
| README 文档 | `README.md` | 部署步骤 + 使用说明 |
| HTML 报告 | `report_*.html` | 浏览器中可交互 |
| 字段速查手册 | `docs/字段速查手册.md` | 20+ 核心字段定义 |

## 局限性

- 当前主要面向 NVIDIA GPU；AMD / Intel GPU 需替换采集命令
- vGPU 场景下温度、功耗、ECC 字段常为 `N/A`，报告中会明确标注
- 拓扑图对单卡场景会显示孤立节点（符合预期，为多卡预留）

## License

MIT
