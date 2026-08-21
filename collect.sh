#!/bin/bash
# gpu-infra-probe 采集脚本
# 阶段1：自动采集所有硬件原始数据

set -u

OUTPUT_DIR="./data"
mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "==> 开始采集 GPU 硬件数据，时间戳：$TIMESTAMP"

# 工具检测：缺工具时给出明确提示而不是直接崩溃
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

if ! command_exists nvidia-smi; then
    echo "[WARN] 未检测到 nvidia-smi，将生成占位文件以便后续流程可继续。"
    HAS_NVIDIA_SMI=0
else
    HAS_NVIDIA_SMI=1
fi

if ! command_exists lspci; then
    echo "[WARN] 未检测到 lspci，跳过 PCIe 设备采集。"
    HAS_LSPCI=0
else
    HAS_LSPCI=1
fi

# ------------------------------------------------------------------------------
# 1. 采集基础GPU信息（任务1.1）
# 同时追加任务1.2中的显存使用率、温度、功耗字段，统一输出到同一个 CSV
# ------------------------------------------------------------------------------
BASIC_CSV="$OUTPUT_DIR/gpu_basic_${TIMESTAMP}.csv"
if [ "$HAS_NVIDIA_SMI" -eq 1 ]; then
    nvidia-smi --query-gpu=name,index,uuid,memory.total,driver_version \
        --format=csv > "$BASIC_CSV"
    # 1.2 显存使用率 / 温度 / 功耗（追加为新列 CSV，便于后期合并）
    nvidia-smi --query-gpu=index,memory.used,memory.free,temperature.gpu,power.draw \
        --format=csv > "$OUTPUT_DIR/gpu_usage_${TIMESTAMP}.csv"
else
    # 占位文件，保证后续解析层能拿到稳定文件名
    echo "name,index,uuid,memory.total,driver_version" > "$BASIC_CSV"
    echo "N/A,0,N/A,N/A,N/A" >> "$BASIC_CSV"
    echo "index,memory.used,memory.free,temperature.gpu,power.draw" > "$OUTPUT_DIR/gpu_usage_${TIMESTAMP}.csv"
    echo "0,N/A,N/A,N/A,N/A" >> "$OUTPUT_DIR/gpu_usage_${TIMESTAMP}.csv"
fi

# ------------------------------------------------------------------------------
# 2. 采集详细硬件参数（任务1.1）
# ------------------------------------------------------------------------------
DETAIL_TXT="$OUTPUT_DIR/gpu_detail_${TIMESTAMP}.txt"
if [ "$HAS_NVIDIA_SMI" -eq 1 ]; then
    nvidia-smi -q > "$DETAIL_TXT"
else
    {
        echo "======== 占位数据：未检测到 nvidia-smi ========"
        echo "Driver Version : N/A"
        echo "CUDA Version : N/A"
        echo "Product Name : N/A"
        echo "FB Memory Usage"
        echo "    Total : N/A"
        echo "    Used : N/A"
        echo "    Free : N/A"
        echo "GPU Current Temp : N/A"
        echo "Power Draw : N/A"
        echo "Power Limit : N/A"
        echo "Performance State : N/A"
    } > "$DETAIL_TXT"
fi

# ------------------------------------------------------------------------------
# 3. 采集拓扑信息（任务1.1）
# ------------------------------------------------------------------------------
TOPO_TXT="$OUTPUT_DIR/topology_${TIMESTAMP}.txt"
if [ "$HAS_NVIDIA_SMI" -eq 1 ]; then
    nvidia-smi topo -m > "$TOPO_TXT"
else
    {
        echo "        GPU0    GPU1    GPU2    GPU3    CPU Affinity    NUMA Affinity"
        echo "GPU0    X       N/A     N/A     N/A     0-7             0"
    } > "$TOPO_TXT"
fi

# ------------------------------------------------------------------------------
# 4. 采集PCIe设备信息（任务1.1）
# ------------------------------------------------------------------------------
PCI_TXT="$OUTPUT_DIR/pci_devices_${TIMESTAMP}.txt"
if [ "$HAS_LSPCI" -eq 1 ]; then
    lspci | grep -i nvidia > "$PCI_TXT"
else
    echo "N/A (lspci 不可用或无 NVIDIA 设备)" > "$PCI_TXT"
fi

# ------------------------------------------------------------------------------
# 5. 采集系统信息（任务1.1 + 1.2 BIOS/DMI）
# ------------------------------------------------------------------------------
SYS_TXT="$OUTPUT_DIR/system_info_${TIMESTAMP}.txt"
uname -a > "$SYS_TXT"
if [ -f /etc/os-release ]; then
    cat /etc/os-release >> "$SYS_TXT"
fi
# 1.2 BIOS/DMI 信息：dmidecode 需要 root，失败时记录占位
{
    echo ""
    echo "======== DMI / BIOS 信息 ========"
    if command_exists dmidecode; then
        dmidecode -t system 2>/dev/null || echo "dmidecode 执行失败（可能需要 root 权限）"
    else
        echo "N/A (dmidecode 未安装或无权限)"
    fi
} >> "$SYS_TXT"

# ------------------------------------------------------------------------------
# 6. 采集 ECC 错误计数（任务1.2）
# ------------------------------------------------------------------------------
ECC_TXT="$OUTPUT_DIR/ecc_errors_${TIMESTAMP}.txt"
if [ "$HAS_NVIDIA_SMI" -eq 1 ]; then
    nvidia-smi -q -d ECC > "$ECC_TXT" 2>/dev/null || echo "ECC 采集失败（vGPU 或不支持 ECC 的卡可能无此字段）" > "$ECC_TXT"
else
    echo "N/A (无 nvidia-smi)" > "$ECC_TXT"
fi

# ------------------------------------------------------------------------------
# 7. 记录本次采集元数据
# ------------------------------------------------------------------------------
META_JSON="$OUTPUT_DIR/collect_meta_${TIMESTAMP}.json"
cat > "$META_JSON" <<EOF
{
    "timestamp": "${TIMESTAMP}",
    "collect_time": "$(date '+%Y-%m-%d %H:%M:%S')",
    "has_nvidia_smi": ${HAS_NVIDIA_SMI},
    "has_lspci": ${HAS_LSPCI},
    "files": {
        "basic_csv": "$(basename "$BASIC_CSV")",
        "usage_csv": "$(basename "$OUTPUT_DIR/gpu_usage_${TIMESTAMP}.csv")",
        "detail_txt": "$(basename "$DETAIL_TXT")",
        "topology_txt": "$(basename "$TOPO_TXT")",
        "pci_txt": "$(basename "$PCI_TXT")",
        "system_txt": "$(basename "$SYS_TXT")",
        "ecc_txt": "$(basename "$ECC_TXT")"
    }
}
EOF

# 把最新的元数据软链/复制为 latest.json，方便解析层取最新一次结果
cp "$META_JSON" "$OUTPUT_DIR/latest_meta.json"

echo "采集完成，数据保存在 $OUTPUT_DIR/"
echo "本次生成文件："
ls -1 "$OUTPUT_DIR"/*_${TIMESTAMP}.* 2>/dev/null
