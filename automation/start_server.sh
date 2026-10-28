#!/bin/bash

# Zotero PDF2ZH Server 启动脚本 (新版)
# 利用 server.py 的 --enable_venv 自动管理虚拟环境

PROJECT_PATH="/Users/你的用户名/Documents/zotero-pdf2zh"
SERVER_PATH="$PROJECT_PATH/server"
LOG_DIR="$PROJECT_PATH/logs"
SERVER_LOG="$LOG_DIR/server_direct.log"
PID_FILE="$LOG_DIR/server_direct.pid"
CONDA_PATH="/opt/anaconda3"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 停止函数
stop_server() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] 正在停止服务器 (PID: $pid)..."
            kill -9 "$pid" 2>/dev/null
            rm -f "$PID_FILE"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] 服务器已停止"
        else
            rm -f "$PID_FILE"
        fi
    fi
}

# 启动函数
start_server() {
    # 先停止旧进程
    stop_server
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动 Zotero PDF2ZH 服务器..."
    
    cd "$SERVER_PATH" || exit 1
    
    # 使用系统 Python 启动，让 server.py 自己管理虚拟环境
    # 设置环境变量确保能找到 conda
    export PATH="$CONDA_PATH/bin:$PATH"
    export CONDA_PREFIX="$CONDA_PATH"
    
    # 启动服务器，让它自己管理虚拟环境
    nohup python3 server.py \
        --port 8888 \
        --enable_venv True \
        --env_tool conda \
        --skip_install True \
        > "$SERVER_LOG" 2>&1 &
    
    local server_pid=$!
    sleep 2
    
    if ps -p "$server_pid" > /dev/null; then
        echo "$server_pid" > "$PID_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 服务器已启动 (PID: $server_pid)"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 日志文件: $SERVER_LOG"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 错误：服务器启动失败"
        echo "最近的日志："
        tail -n 20 "$SERVER_LOG"
        exit 1
    fi
}

# 主程序
case "${1:-start}" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        start_server
        ;;
    status)
        if [ -f "$PID_FILE" ]; then
            local pid=$(cat "$PID_FILE")
            if ps -p "$pid" > /dev/null; then
                echo "服务器正在运行 (PID: $pid)"
            else
                echo "服务器未运行（PID文件存在但进程已停止）"
            fi
        else
            echo "服务器未运行"
        fi
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac