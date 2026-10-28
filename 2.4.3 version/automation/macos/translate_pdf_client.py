#!/usr/bin/env python3
import os
import sys
import base64
import json
import time
import requests
import subprocess
import shutil
from pathlib import Path

class PDFTranslatorClient:
    def __init__(self, server_url="http://localhost:8888"):
        self.server_url = server_url
        self.project_path = Path(__file__).parent
        self.conda_env = "zotero-pdf2zh"
        
    def send_notification(self, title, message):
        """发送 macOS 通知"""
        try:
            if self._command_exists('terminal-notifier'):
                cmd = [
                    'terminal-notifier',
                    '-title', title,
                    '-message', message,
                    '-group', 'pdf-translate-quickaction'
                ]
                subprocess.run(cmd, check=False, capture_output=True)
            else:
                cmd = ['osascript', '-e', f'display notification "{message}" with title "{title}"']
                subprocess.run(cmd, check=False, capture_output=True)
        except Exception as e:
            print(f"通知发送失败: {e}")
    
    def _command_exists(self, command):
        """检查命令是否存在"""
        try:
            subprocess.run(['which', command], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def is_server_running(self):
        """检查翻译服务器是否运行"""
        try:
            response = requests.get(f"{self.server_url}/", timeout=2)
            return response.status_code < 500
        except:
            return False
    
    def start_server(self):
        """启动翻译服务器"""
        self.send_notification("PDF 翻译", "正在启动翻译服务...")
        
        # 查找 Python 解释器
        python_paths = [
            f"/opt/anaconda3/envs/{self.conda_env}/bin/python",
            f"/Users/{os.environ.get('USER')}/opt/anaconda3/envs/{self.conda_env}/bin/python",
            f"/usr/local/anaconda3/envs/{self.conda_env}/bin/python"
        ]
        
        python_exe = None
        for path in python_paths:
            if os.path.exists(path):
                python_exe = path
                break
        
        if not python_exe:
            raise Exception("找不到 Python 环境，请检查 conda 环境配置")
        
        # 启动服务器
        server_script = self.project_path / "server.py"
        subprocess.Popen(
            [python_exe, str(server_script), "8888"],
            cwd=str(self.project_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # 等待服务器启动
        for i in range(30):  # 最多等待30秒
            time.sleep(1)
            if self.is_server_running():
                self.send_notification("PDF 翻译", "翻译服务已启动")
                return True
        
        raise Exception("翻译服务启动失败")
    
    def translate_pdf(self, pdf_path):
        """翻译 PDF 文件"""
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"文件不存在: {pdf_path}")
        
        if pdf_path.suffix.lower() != '.pdf':
            raise ValueError("只支持 PDF 文件")
        
        # 确保服务器运行
        if not self.is_server_running():
            self.start_server()
        
        # 发送开始通知
        self.send_notification(
            "PDF 翻译开始",
            f"正在翻译: {pdf_path.name}"
        )
        
        # 读取文件并编码
        with open(pdf_path, 'rb') as f:
            file_content = base64.b64encode(f.read()).decode('utf-8')
        
        # 读取配置
        config_path = self.project_path / "config.json"
        config_data = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        
        # 准备请求数据
        request_data = {
            'fileName': pdf_path.name,
            'fileContent': f'data:application/pdf;base64,{file_content}',
            'service': config_data.get('translators', [{}])[0].get('name', 'deepseek'),
            'engine': 'pdf2zh',
            'threadNum': 4,
            'outputPath': str(self.project_path / 'translated'),
            'configPath': str(config_path),
            'sourceLang': 'en',
            'targetLang': 'zh'
        }
        
        # 发送翻译请求
        try:
            response = requests.post(
                f"{self.server_url}/translate",
                json=request_data,
                timeout=600  # 10分钟超时
            )
            
            if response.status_code == 200:
                # 查找生成的 dual PDF
                translated_dir = self.project_path / 'translated'
                base_name = pdf_path.stem
                dual_pdf = translated_dir / f"{base_name}-dual.pdf"
                
                # 等待文件生成
                for _ in range(10):
                    if dual_pdf.exists():
                        break
                    time.sleep(0.5)
                
                if dual_pdf.exists():
                    # 将文件复制到原位置
                    target_path = pdf_path.parent / f"{base_name}-dual.pdf"
                    shutil.copy2(dual_pdf, target_path)
                    
                    self.send_notification(
                        "PDF 翻译完成",
                        f"✅ 已生成: {target_path.name}"
                    )
                    
                    # 在 Finder 中显示文件
                    subprocess.run(['open', '-R', str(target_path)])
                    
                    return str(target_path)
                else:
                    raise Exception("翻译完成但未找到生成的文件")
            else:
                error_msg = response.json().get('message', '未知错误')
                raise Exception(f"翻译失败: {error_msg}")
                
        except requests.exceptions.Timeout:
            raise Exception("翻译超时，请检查文件大小")
        except Exception as e:
            raise Exception(f"翻译错误: {str(e)}")

def main():
    if len(sys.argv) < 2:
        print("用法: python translate_pdf_client.py <pdf_file_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    client = PDFTranslatorClient()
    
    try:
        result = client.translate_pdf(pdf_path)
        print(f"翻译成功: {result}")
    except Exception as e:
        error_msg = str(e)
        print(f"错误: {error_msg}")
        client.send_notification("PDF 翻译失败", f"❌ {error_msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()