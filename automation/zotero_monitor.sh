#!/bin/bash

# --- 配置 ---
PROJECT_PATH="/Users/你的用户名/Documents/zotero-pdf2zh"
CONDA_ENV_NAME="zotero-pdf2zh-venv"
LOG_DIR="$PROJECT_PATH/logs"
PID_FILE="$LOG_DIR/zotero_python.pid"
MONITOR_LOG="$LOG_DIR/monitor.log"
SERVER_LOG="$LOG_DIR/server.log"
SERVER_SCRIPT="server/server.py"
SERVER_PORT=8888

# --- 初始化 ---
mkdir -p "$LOG_DIR"

# --- 工具函数 ---

# 日志记录
log() {
    # 使用 tee 同时输出到 stdout (用于 launchd 日志) 和监控日志文件
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$MONITOR_LOG"
}

# 发送 macOS 通知
notify() {
    local title="$1"
    local message="$2"
    
    # 确保 terminal-notifier 存在
    if command -v /opt/homebrew/bin/terminal-notifier >/dev/null 2>&1 || command -v terminal-notifier >/dev/null 2>&1; then
        # 在后台运行通知，以避免阻塞脚本
        /opt/homebrew/bin/terminal-notifier -title "$title" -message "$message" -group "zotero-pdf2zh" >/dev/null 2>&1 &
    fi
    # 无论如何都记录日志
    log "通知: $title - $message"
}

# 检查进程是否正在运行 (通过 PID 文件)
is_server_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if [ -n "$pid" ] && ps -p "$pid" > /dev/null; then
            return 0 # true
        fi
    fi
    return 1 # false
}

# 检查 Zotero 是否正在运行
is_zotero_running() {
    if pgrep -f "Zotero.app" > /dev/null; then
        return 0 # true
    else
        return 1 # false
    fi
}

# --- 核心功能 ---

# 启动服务器
start_server() {
    log "尝试启动 Python 服务器..."
    
    # **重要**: 这是 Conda 环境中 Python 解释器的典型路径。
    # 如果你的 anaconda/miniconda 安装在不同位置，请相应修改。
    local python_executable="/opt/anaconda3/envs/$CONDA_ENV_NAME/bin/python"

    if [ ! -f "$python_executable" ]; then
        log "错误: 找不到 Conda 环境中的 Python 解释器: $python_executable"
        log "请检查 CONDA_ENV_NAME 变量和你的 anaconda 安装路径。"
        return 1
    fi

    # 检查端口是否被占用
    if lsof -i :$SERVER_PORT > /dev/null; then
        log "错误：端口 $SERVER_PORT 已被占用。无法启动。"
        return 1
    fi

    # 进入项目目录
    cd "$PROJECT_PATH" || { log "错误：无法进入项目目录 $PROJECT_PATH"; return 1; }

    # 使用 Conda 环境的 Python 直接启动服务器
    log "使用解释器直接启动: $python_executable"
    nohup "$python_executable" "$SERVER_SCRIPT" --port "$SERVER_PORT" --enable_venv True --env_tool conda --skip_install True > "$SERVER_LOG" 2>&1 &

    local server_pid=$!

    # 短暂等待以确认进程是否成功启动
    sleep 1 

    if ps -p "$server_pid" > /dev/null; then
        echo "$server_pid" > "$PID_FILE"
        log "服务器已启动，PID: $server_pid。日志位于 $SERVER_LOG"
        notify "Zotero PDF2ZH" "✅ PDF 翻译服务已启动"
    else
        log "错误：服务器未能启动。请检查 $SERVER_LOG 获取详细信息。"
        log "--- 最近的服务器日志 ---"
        if [ -f "$SERVER_LOG" ]; then
            tail -n 20 "$SERVER_LOG" >> "$MONITOR_LOG"
        else
            log "Server log 文件不存在。"
        fi
        log "-------------------------"
        notify "Zotero PDF2ZH 错误" "❌ PDF 翻译服务启动失败"
    fi
}

# 停止服务器
stop_server() {
    if is_server_running; then
        local pid
        pid=$(cat "$PID_FILE")
        log "正在停止服务器 (PID: $pid)..."
        
        # 强制停止
        kill -9 "$pid" 2>/dev/null
        
        rm -f "$PID_FILE"
        log "服务器已停止。"
        notify "Zotero PDF2ZH" "🔴 PDF 翻译服务已停止"
    else
        log "服务器未在运行，无需停止。"
        # 清理可能存在的无效 PID 文件
        rm -f "$PID_FILE"
    fi
}

# --- 主逻辑 ---

log "--- 开始监控检查 ---"

if is_zotero_running; then
    log "Zotero 正在运行。"
    if is_server_running; then
        log "服务器也正在运行。一切正常。"
    else
        log "Zotero 正在运行，但服务器已停止。正在重启服务器..."
        start_server
    fi
else
    log "Zotero 未运行。"
    if is_server_running; then
        log "Zotero 已关闭，但服务器仍在运行。正在停止服务器..."
        stop_server
    else
        log "服务器也未运行。一切正常。"
    fi
fi

log "--- 监控检查结束 ---"
exit 0
