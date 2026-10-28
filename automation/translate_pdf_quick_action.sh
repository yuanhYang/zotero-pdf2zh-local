#!/bin/bash

# PDF 翻译 Quick Action 包装脚本
# 用于 macOS Automator Quick Action

# 配置
PROJECT_PATH="/Users/你的用户名/Documents/zotero-pdf2zh"
CONDA_ENV_NAME="zotero-pdf2zh-venv"
# 使用用户库日志目录，避免权限问题
LOG_FILE="$HOME/Library/Logs/PDFTranslateQuickAction.log"

# 创建日志目录
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

# 日志函数
log() {
    # 输出到标准错误（在 Automator 中可见）
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
    # 尝试写入日志文件，如果失败则忽略
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE" 2>/dev/null || true
}

# 开始记录
log "=== 开始 PDF 翻译 Quick Action ==="
log "接收到的参数: $@"

# 检查参数
if [ $# -eq 0 ]; then
    log "错误: 没有提供 PDF 文件路径"
    osascript -e 'display dialog "请选择一个 PDF 文件" buttons {"确定"} default button 1 with icon stop'
    exit 1
fi

# 获取 PDF 文件路径
PDF_PATH="$1"
log "PDF 文件路径: $PDF_PATH"

# 检查文件是否存在
if [ ! -f "$PDF_PATH" ]; then
    log "错误: 文件不存在 - $PDF_PATH"
    osascript -e 'display dialog "文件不存在" buttons {"确定"} default button 1 with icon stop'
    exit 1
fi

# 检查是否为 PDF 文件
if [[ ! "$PDF_PATH" =~ \.pdf$ ]] && [[ ! "$PDF_PATH" =~ \.PDF$ ]]; then
    log "错误: 不是 PDF 文件 - $PDF_PATH"
    osascript -e 'display dialog "请选择 PDF 文件" buttons {"确定"} default button 1 with icon stop'
    exit 1
fi

# 尝试查找 Python 解释器
PYTHON_PATHS=(
    "/opt/anaconda3/envs/$CONDA_ENV_NAME/bin/python"
    "/Users/$USER/opt/anaconda3/envs/$CONDA_ENV_NAME/bin/python"
    "/usr/local/anaconda3/envs/$CONDA_ENV_NAME/bin/python"
    "$HOME/miniconda3/envs/$CONDA_ENV_NAME/bin/python"
    "$HOME/anaconda3/envs/$CONDA_ENV_NAME/bin/python"
)

PYTHON_EXE=""
for path in "${PYTHON_PATHS[@]}"; do
    if [ -f "$path" ]; then
        PYTHON_EXE="$path"
        log "找到 Python: $PYTHON_EXE"
        break
    fi
done

# 如果没找到，尝试使用 conda
if [ -z "$PYTHON_EXE" ]; then
    if command -v conda >/dev/null 2>&1; then
        log "尝试通过 conda 查找环境..."
        # 尝试激活 conda
        if [ -f "$HOME/opt/anaconda3/etc/profile.d/conda.sh" ]; then
            source "$HOME/opt/anaconda3/etc/profile.d/conda.sh"
        elif [ -f "/opt/anaconda3/etc/profile.d/conda.sh" ]; then
            source "/opt/anaconda3/etc/profile.d/conda.sh"
        elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
            source "$HOME/miniconda3/etc/profile.d/conda.sh"
        fi
        
        # 激活环境
        conda activate "$CONDA_ENV_NAME" 2>/dev/null
        if [ $? -eq 0 ]; then
            PYTHON_EXE="python"
            log "成功激活 conda 环境"
        fi
    fi
fi

# 最后检查
if [ -z "$PYTHON_EXE" ] || ! command -v "$PYTHON_EXE" >/dev/null 2>&1; then
    log "错误: 找不到 Python 环境"
    osascript -e 'display dialog "找不到 Python 环境，请检查 conda 环境配置" buttons {"确定"} default button 1 with icon stop'
    exit 1
fi

# 检查客户端脚本是否存在
CLIENT_SCRIPT="$PROJECT_PATH/translate_pdf_client.py"
if [ ! -f "$CLIENT_SCRIPT" ]; then
    log "错误: 找不到客户端脚本 - $CLIENT_SCRIPT"
    osascript -e 'display dialog "翻译客户端脚本不存在" buttons {"确定"} default button 1 with icon stop'
    exit 1
fi

# 执行翻译
log "开始执行翻译..."
log "命令: $PYTHON_EXE $CLIENT_SCRIPT \"$PDF_PATH\""

# 设置环境变量
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

# 执行 Python 脚本
cd "$PROJECT_PATH"
OUTPUT=$("$PYTHON_EXE" "$CLIENT_SCRIPT" "$PDF_PATH" 2>&1)
EXIT_CODE=$?

# 记录输出
log "Python 脚本输出: $OUTPUT"
log "退出码: $EXIT_CODE"

# 检查执行结果
if [ $EXIT_CODE -eq 0 ]; then
    log "翻译成功完成"
else
    log "翻译过程出错"
    # 从输出中提取错误信息
    ERROR_MSG=$(echo "$OUTPUT" | grep -E "(错误|Error|Exception)" | head -n 1)
    if [ -z "$ERROR_MSG" ]; then
        ERROR_MSG="翻译失败，请查看日志文件: ~/Library/Logs/PDFTranslateQuickAction.log"
    fi
    osascript -e "display dialog \"$ERROR_MSG\" buttons {\"确定\"} default button 1 with icon stop"
fi

log "=== PDF 翻译 Quick Action 结束 ==="
log ""

exit $EXIT_CODE