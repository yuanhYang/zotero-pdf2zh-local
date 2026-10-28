import os
from flask import Flask, request, jsonify, send_file
import base64
import subprocess
from pypdf import PdfWriter, PdfReader
from pypdf.generic import RectangleObject
import sys
import time
import threading
import re

services = [    
    'bing', 'google',
    'deepl', 'deeplx',
    'ollama', 'xinference',
    'openai', 'azure-openai',
    'zhipu', 'ModelScope',
    'silicon', 'gemini', 'azure',
    'tencent', 'dify', 'anythingllm',
    'argos', 'grok', 'groq',
    'deepseek', 'openailiked', 'qwen-mt'
]

class PDFTranslator:
    DEFAULT_CONFIG = {
        'port': 8888,
        'engine': 'pdf2zh',
        'service': 'bing',
        'threadNum': 4,
        'outputPath': './translated/',
        'configPath': './config.json',
        'sourceLang': 'en',
        'targetLang': 'zh'
    }

    def __init__(self):
        self.app = Flask(__name__)
        self.setup_routes()

    def send_notification(self, title, message, urgency="normal", group_id="zotero-pdf2zh-translate"):
        """发送系统通知"""
        try:
            # 尝试使用terminal-notifier
            if self._command_exists('terminal-notifier'):
                cmd = [
                    'terminal-notifier',
                    '-title', title,
                    '-message', message,
                    '-group', group_id
                ]
                
                # 根据消息类型设置不同的图标
                if '开始' in message or '正在' in message or '%' in message:
                    cmd.extend(['-contentImage', '/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/DocumentIcon.icns'])
                elif '完成' in message or '成功' in message:
                    cmd.extend(['-contentImage', '/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/ToolbarInfo.icns'])
                elif '错误' in message or '失败' in message:
                    cmd.extend(['-contentImage', '/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/AlertStopIcon.icns'])
                
                subprocess.run(cmd, check=False, capture_output=True)
                print(f"[通知] {title}: {message}")
                
            # 备用方案：使用osascript
            else:
                cmd = ['osascript', '-e', f'display notification "{message}" with title "{title}"']
                subprocess.run(cmd, check=False, capture_output=True)
                print(f"[通知] {title}: {message}")
                
        except Exception as e:
            print(f"[通知发送失败] {e}")

    def send_progress_notification(self, title, base_message, progress, total_pages=0, file_name="", milestone=False):
        """发送进度通知（仅在关键节点）"""
        if not milestone:
            return  # 只在关键节点发送通知
            
        progress_bar = self._create_progress_bar(progress)
        
        if total_pages > 0:
            message = f"{base_message}\n{progress_bar} {progress:.0f}%\n📄 页数: {total_pages} | 📁 文件: {file_name}"
        else:
            message = f"{base_message}\n{progress_bar} {progress:.0f}%\n📁 文件: {file_name}"
            
        self.send_notification(title, message, "normal", "zotero-pdf2zh-progress")

    def _create_progress_bar(self, progress, length=10):
        """创建文本进度条"""
        filled = int(progress / 100 * length)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}]"

    def _should_send_milestone_notification(self, current_progress, last_progress):
        """判断是否应该发送里程碑通知"""
        milestones = [25, 50, 75, 90]
        
        for milestone in milestones:
            if last_progress < milestone <= current_progress:
                return True, milestone
        return False, None

    def _command_exists(self, command):
        """检查命令是否存在"""
        try:
            subprocess.run(['which', command], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def setup_routes(self):
        self.app.add_url_rule('/translate', 'translate', self.translate, methods=['POST'])
        self.app.add_url_rule('/cut', 'cut', self.cut_pdf, methods=['POST'])
        self.app.add_url_rule('/compare', 'compare', self.compare, methods=['POST'])
        self.app.add_url_rule('/singlecompare', 'singlecompare', self.single_compare, methods=['POST'])
        self.app.add_url_rule('/translatedFile/<filename>', 'download', self.download_file)

    class Config:
        def __init__(self, data):
            self.threads = data.get('threadNum') if data.get('threadNum') not in [None, ''] else PDFTranslator.DEFAULT_CONFIG['threadNum']
            self.service = data.get('service') if data.get('service') not in [None, ''] else PDFTranslator.DEFAULT_CONFIG['service']
            self.engine = data.get('engine') if data.get('engine') not in [None, ''] else PDFTranslator.DEFAULT_CONFIG['engine']
            self.outputPath = data.get('outputPath') if data.get('outputPath') not in [None, ''] else PDFTranslator.DEFAULT_CONFIG['outputPath']
            self.configPath = data.get('configPath') if data.get('configPath') not in [None, ''] else PDFTranslator.DEFAULT_CONFIG['configPath']
            self.sourceLang = data.get('sourceLang') if data.get('sourceLang') not in [None, ''] else PDFTranslator.DEFAULT_CONFIG['sourceLang']
            self.targetLang = data.get('targetLang') if data.get('targetLang') not in [None, ''] else PDFTranslator.DEFAULT_CONFIG['targetLang']
            self.skip_last_pages = data.get('skip_last_pages') if data.get('skip_last_pages') not in [None, ''] else 0
            self.skip_last_pages = int(self.skip_last_pages) if str(self.skip_last_pages).isdigit() else 0

            self.babeldoc = data.get('babeldoc', False)
            self.mono_cut = data.get('mono_cut', False)
            self.dual_cut = data.get('dual_cut', False)
            self.compare = data.get('compare', False) # 双栏PDF左右对照
            self.single_compare = data.get('single_compare', False) # 单栏PDF左右对照
            self.skip_subset_fonts = data.get('skip_subset_fonts', False)

            self.outputPath = self.get_abs_path(self.outputPath)
            self.configPath = self.get_abs_path(self.configPath)

            os.makedirs(self.outputPath, exist_ok=True)

            if self.engine == 'pdf2zh_next':
                self.babeldoc = True
            if self.engine != 'pdf2zh' and self.engine in services:
                print('Engine only support PDF2zh')
                self.engine = 'pdf2zh'

            print("[config]: ", self.__dict__)
            
        @staticmethod
        def get_abs_path(path):
            return path if os.path.isabs(path) else os.path.abspath(path)

    def process_request(self):
        data = request.get_json()
        config = self.Config(data)
        self.translated_dir = config.outputPath
        
        file_content = data.get('fileContent', '')
        if file_content.startswith('data:application/pdf;base64,'):
            file_content = file_content[len('data:application/pdf;base64,'):]
        
        input_path = os.path.join(config.outputPath, data['fileName'])
        with open(input_path, 'wb') as f:
            f.write(base64.b64decode(file_content))
        
        return input_path, config

    def translate_pdf(self, input_path, config, progress_callback=None):
        base_name = os.path.basename(input_path).replace('.pdf', '')
        file_name = os.path.basename(input_path)
        
        # 获取PDF页数用于进度计算
        try:
            total_pages = len(PdfReader(input_path).pages)
        except:
            total_pages = 0
            
        output_files = {
            'mono': os.path.join(config.outputPath, f"{base_name}-mono.pdf"),
            'dual': os.path.join(config.outputPath, f"{base_name}-dual.pdf")
        }
        
        if config.engine == 'pdf2zh':
            cmd = [
                config.engine,
                input_path,
                '--t', str(config.threads),
                '--output', config.outputPath,
                '--service', config.service,
                '--lang-in', config.sourceLang,
                '--lang-out', config.targetLang,
                '--config', config.configPath,
            ]
            if config.skip_last_pages and config.skip_last_pages > 0: 
                end = total_pages - config.skip_last_pages
                cmd.append('-p '+str(1)+'-'+str(end))
                total_pages = end  # 更新实际处理的页数
            if config.skip_subset_fonts == True or config.skip_subset_fonts == 'true':
                cmd.append('--skip-subset-fonts')
            if config.babeldoc == True or config.babeldoc == 'true':
                cmd.append('--babeldoc')
            
            # 运行命令并监控进度
            self._run_with_progress_monitoring(cmd, total_pages, file_name, progress_callback)
            
            if config.babeldoc == True or config.babeldoc == 'true':
                os.rename(os.path.join(config.outputPath, f"{base_name}.{config.targetLang}.mono.pdf"), output_files['mono'])
                os.rename(os.path.join(config.outputPath, f"{base_name}.{config.targetLang}.dual.pdf"), output_files['dual'])
            return output_files['mono'], output_files['dual']
            
        elif config.engine == 'pdf2zh_next':
            service = config.service
            if service == 'openailiked':
                service = 'openaicompatible'
            if service == 'tencent':
                service = 'tencentmechinetranslation'
            if service == 'ModelScope':
                service = 'modelscope'
            if service == 'silicon':
                service = 'siliconflow'
            if service == 'qwen-mt':
                service = 'qwenmt'
            cmd = [
                config.engine,
                input_path,
                '--output', config.outputPath,
                '--'+service,
                '--lang-in', config.sourceLang,
                '--lang-out', config.targetLang,
                '--qps', str(config.threads),
            ]
            if os.path.exists(config.configPath) and config.configPath != '' and len(config.configPath) > 4 and 'json' not in config.configPath:
                cmd.append('--config')
                cmd.append(config.configPath)
            if config.skip_last_pages and config.skip_last_pages > 0:
                end = total_pages - config.skip_last_pages
                cmd.append('--pages')
                cmd.append(f'{1}-{end}')
                total_pages = end  # 更新实际处理的页数
            
            print("pdf2zh_next command: ", cmd)
            
            # 运行命令并监控进度
            self._run_with_progress_monitoring(cmd, total_pages, file_name, progress_callback)

            no_watermark_mono = os.path.join(config.outputPath, f"{base_name}.no_watermark.{config.targetLang}.mono.pdf")
            no_watermark_dual = os.path.join(config.outputPath, f"{base_name}.no_watermark.{config.targetLang}.dual.pdf")
            
            if os.path.exists(no_watermark_mono) and os.path.exists(no_watermark_dual):
                os.rename(no_watermark_mono, output_files['mono'])
                os.rename(no_watermark_dual, output_files['dual'])
            else:            
                os.rename(os.path.join(config.outputPath, f"{base_name}.{config.targetLang}.mono.pdf"), output_files['mono'])
                os.rename(os.path.join(config.outputPath, f"{base_name}.{config.targetLang}.dual.pdf"), output_files['dual'])

            return output_files['mono'], output_files['dual']
        else:
            raise ValueError(f"Unsupported engine: {config.engine}")

    def _run_with_progress_monitoring(self, cmd, total_pages, file_name, progress_callback=None):
        """运行命令并监控进度"""
        
        # 启动进度监控
        progress_data = {'current': 0, 'total': total_pages, 'running': True, 'last_notified': 0}
        
        def update_progress():
            """进度更新线程"""
            while progress_data['running']:
                if progress_data['total'] > 0:
                    current_progress = min(progress_data['current'], 95)
                    
                    # 检查是否需要发送里程碑通知
                    should_notify, milestone = self._should_send_milestone_notification(
                        current_progress, progress_data['last_notified']
                    )
                    
                    if should_notify:
                        self.send_progress_notification(
                            "PDF翻译进行中",
                            f"翻译进度更新",
                            milestone,
                            progress_data['total'],
                            file_name,
                            milestone=True
                        )
                        progress_data['last_notified'] = milestone
                
                time.sleep(5)  # 每5秒检查一次是否需要发送通知
        
        # 启动进度更新线程
        if progress_callback:
            progress_thread = threading.Thread(target=update_progress)
            progress_thread.daemon = True
            progress_thread.start()
        
        try:
            # 运行命令并捕获输出
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True,
                bufsize=1
            )
            
            processed_pages = 0
            for line in iter(process.stdout.readline, ''):
                if line:
                    print(line.strip())  # 保持原有的日志输出
                    
                    # 尝试解析进度信息
                    if progress_callback:
                        # 查找页面处理信息
                        page_match = re.search(r'(?:page|页面|Page)\s*(?::|：)?\s*(\d+)', line, re.IGNORECASE)
                        progress_match = re.search(r'(\d+(?:\.\d+)?)\s*%', line)
                        
                        if page_match:
                            processed_pages = int(page_match.group(1))
                            if total_pages > 0:
                                progress_data['current'] = (processed_pages / total_pages) * 100
                            else:
                                progress_data['current'] = min(processed_pages * 2, 90)
                                
                        elif progress_match:
                            progress_data['current'] = float(progress_match.group(1))
                        
                        elif any(keyword in line.lower() for keyword in ['translating', '翻译', 'processing', '处理']):
                            if progress_data['current'] < 80:
                                progress_data['current'] += 0.5  # 更缓慢的增长
            
            # 等待进程完成
            return_code = process.wait()
            
            # 停止进度监控
            progress_data['running'] = False
            
            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, cmd)
                
        except Exception as e:
            progress_data['running'] = False
            raise e
        
    # 工具函数, 用于将pdf左右拼接
    def merge_pages_side_by_side(self, input_pdf, output_pdf):
        reader = PdfReader(input_pdf)
        writer = PdfWriter()
        num_pages = len(reader.pages)
        i = 0
        while i < num_pages:
            left_page = reader.pages[i]
            left_width = left_page.mediabox.width
            height = left_page.mediabox.height
            if i + 1 < num_pages:
                right_page = reader.pages[i + 1]
                right_width = right_page.mediabox.width
            else:
                right_page = None
                right_width = left_width  # Assume same width
            new_width = left_width + right_width
            new_page = writer.add_blank_page(width=new_width, height=height)
            new_page.merge_transformed_page(left_page, (1, 0, 0, 1, 0, 0))
            if right_page:
                new_page.merge_transformed_page(right_page, (1, 0, 0, 1, left_width, 0))
            i += 2
        with open(output_pdf, "wb") as f:
            writer.write(f)

    # 工具函数, 用于切割双栏pdf文件
    def split_pdf(self, input_pdf, output_pdf, compare=False, babeldoc=False):
        writer = PdfWriter()
        if ('dual' in input_pdf or compare == True) and babeldoc == False:
            readers = [PdfReader(input_pdf) for _ in range(4)]
            for i in range(0, len(readers[0].pages), 2):
                original_media_box = readers[0].pages[i].mediabox
                width = original_media_box.width
                height = original_media_box.height
                left_page_1 = readers[0].pages[i]
                offset = width/20
                ratio = 4.7
                for box in ['mediabox', 'cropbox', 'bleedbox', 'trimbox', 'artbox']:
                    setattr(left_page_1, box, RectangleObject((offset, 0, width/2+offset/ratio, height)))
                left_page_2 = readers[1].pages[i+1]
                for box in ['mediabox', 'cropbox', 'bleedbox', 'trimbox', 'artbox']:
                    setattr(left_page_2, box, RectangleObject((offset, 0, width/2+offset/ratio, height)))
                right_page_1 = readers[2].pages[i]
                for box in ['mediabox', 'cropbox', 'bleedbox', 'trimbox', 'artbox']:
                    setattr(right_page_1, box, RectangleObject((width/2-offset/ratio, 0, width-offset, height)))
                right_page_2 = readers[3].pages[i+1]
                for box in ['mediabox', 'cropbox', 'bleedbox', 'trimbox', 'artbox']:
                    setattr(right_page_2, box, RectangleObject((width/2-offset/ratio, 0, width-offset, height)))
                if compare == True:
                    blank_page_1 = writer.add_blank_page(width, height)
                    blank_page_1.merge_transformed_page(left_page_1, (1, 0, 0, 1, 0, 0))
                    blank_page_1.merge_transformed_page(left_page_2, (1, 0, 0, 1, width / 2, 0))
                    blank_page_2 = writer.add_blank_page(width, height)
                    blank_page_2.merge_transformed_page(right_page_1, (1, 0, 0, 1, -width / 2, 0))
                    blank_page_2.merge_transformed_page(right_page_2, (1, 0, 0, 1, 0, 0))
                else:
                    writer.add_page(left_page_1)
                    writer.add_page(left_page_2)
                    writer.add_page(right_page_1)
                    writer.add_page(right_page_2)
        else: 
            readers = [PdfReader(input_pdf) for _ in range(2)]
            for i in range(len(readers[0].pages)):
                page = readers[0].pages[i]
                original_media_box = page.mediabox
                width = original_media_box.width
                height = original_media_box.height
                w_offset = width/20
                w_ratio = 4.7
                h_offset = height/20
                left_page = readers[0].pages[i]
                left_page.mediabox = RectangleObject((w_offset, h_offset, width/2+w_offset/w_ratio, height-h_offset))
                right_page = readers[1].pages[i]
                right_page.mediabox = RectangleObject((width/2-w_offset/w_ratio, h_offset, width-w_offset, height-h_offset))
                writer.add_page(left_page)
                writer.add_page(right_page)
        with open(output_pdf, "wb") as output_file:
            writer.write(output_file)

    def translate(self):
        print("\n########## translating ##########")
        
        # 记录开始时间
        start_time = time.time()
        file_name = ""
        
        try:
            input_path, config = self.process_request()
            file_name = os.path.basename(input_path)
            
            # 发送翻译开始通知
            self.send_notification(
                "PDF翻译开始",
                f"正在翻译文件: {file_name}\n翻译引擎: {config.service}",
                "normal"
            )
            
            # 启用进度监控
            mono, dual = self.translate_pdf(input_path, config, progress_callback=True)
            processed_files = []
            
            # 发送后处理通知
            if any([config.mono_cut, config.dual_cut, config.compare, config.single_compare]):
                self.send_notification(
                    "PDF后处理",
                    f"翻译完成，正在进行后处理...\n📁 文件: {file_name}",
                    "normal"
                )
            
            if config.mono_cut == True or config.mono_cut == "true":
                output = mono.replace('-mono.pdf', '-mono-cut.pdf')
                self.split_pdf(mono, output)
                processed_files.append(output)
                
            if config.dual_cut == True or config.dual_cut == "true":
                output = dual.replace('-dual.pdf', '-dual-cut.pdf')
                self.split_pdf(dual, output, False, config.babeldoc == True or config.babeldoc == "true")
                processed_files.append(output)
                
            if config.babeldoc == False or config.babeldoc == "false":
                if config.compare == True or config.compare == "true":
                    output = dual.replace('-dual.pdf', '-compare.pdf')
                    self.split_pdf(dual, output, compare=True, babeldoc=False)
                    processed_files.append(output)
                if config.single_compare == True or config.single_compare == "true":
                    output = dual.replace('-dual.pdf', '-single-compare.pdf')
                    self.merge_pages_side_by_side(dual, output)
                    processed_files.append(output)
            
            # 计算翻译耗时
            end_time = time.time()
            duration = int(end_time - start_time)
            duration_str = f"{duration//60}分{duration%60}秒" if duration >= 60 else f"{duration}秒"
            
            # 发送翻译完成通知
            self.send_notification(
                "PDF翻译完成",
                f"✅ 文件翻译成功: {file_name}\n⏱️ 耗时: {duration_str}\n📁 生成文件: {len(processed_files) + 2}个",
                "normal",
                "zotero-pdf2zh-translate"  # 使用不同的组，避免与进度通知混淆
            )
            
            return jsonify({'status': 'success', 'processed': processed_files}), 200
        
        except Exception as e:
            # 计算错误发生时的耗时
            end_time = time.time()
            duration = int(end_time - start_time)
            duration_str = f"{duration//60}分{duration%60}秒" if duration >= 60 else f"{duration}秒"
            
            # 发送翻译错误通知
            self.send_notification(
                "PDF翻译失败",
                f"❌ 翻译失败: {file_name or '未知文件'}\n⏱️ 运行时长: {duration_str}\n🔍 错误: {str(e)[:50]}{'...' if len(str(e)) > 50 else ''}",
                "critical",
                "zotero-pdf2zh-translate"
            )
            
            print("[translate error]: ", e)
            return jsonify({'status': 'error', 'message': str(e)}), 500

    def cut_pdf(self):
        print("\n########## cutting ##########")
        try:
            input_path, config = self.process_request()
            file_name = os.path.basename(input_path)
            
            # 发送切割开始通知
            self.send_notification(
                "PDF切割开始",
                f"正在切割文件: {file_name}",
                "normal"
            )
            
            output_path = input_path.replace('.pdf', '-cut.pdf')
            self.split_pdf(input_path, output_path) # 保留原逻辑
            
            # 发送切割完成通知
            self.send_notification(
                "PDF切割完成",
                f"✅ 文件切割成功: {file_name}",
                "normal"
            )
            
            return jsonify({'status': 'success', 'path': output_path}), 200
        except Exception as e:
            # 发送切割错误通知
            file_name = getattr(locals(), 'file_name', '未知文件')
            self.send_notification(
                "PDF切割失败",
                f"❌ 切割失败: {file_name}\n🔍 错误: {str(e)[:50]}{'...' if len(str(e)) > 50 else ''}",
                "critical"
            )
            
            print("[cut error]: ", e)
            return jsonify({'status': 'error', 'message': str(e)}), 500

    def single_compare(self):
        print("\n########## single compare ##########")
        try:
            input_path, config = self.process_request()
            file_name = os.path.basename(input_path)
            
            if '-mono.pdf' in input_path:
                raise Exception('Please provide dual PDF or origial PDF for dual-comparison')
            
            # 发送对比开始通知
            self.send_notification(
                "PDF对比开始",
                f"正在生成对比版本: {file_name}",
                "normal"
            )
            
            if not 'dual' in input_path:
                _, dual = self.translate_pdf(input_path, config, progress_callback=True)
                input_path = dual
            output_path = input_path.replace('-dual.pdf', '-single-compare.pdf')
            self.merge_pages_side_by_side(input_path, output_path)
            
            # 发送对比完成通知
            self.send_notification(
                "PDF对比完成",
                f"✅ 对比版本生成成功: {file_name}",
                "normal"
            )
            
            return jsonify({'status': 'success', 'path': output_path}), 200
        except Exception as e:
            # 发送对比错误通知
            file_name = getattr(locals(), 'file_name', '未知文件')
            self.send_notification(
                "PDF对比失败",
                f"❌ 对比生成失败: {file_name}\n🔍 错误: {str(e)[:50]}{'...' if len(str(e)) > 50 else ''}",
                "critical"
            )
            
            print("[compare error]: ", e)
            return jsonify({'status': 'error', 'message': str(e)}), 500
        
    def compare(self):
        print("\n########## compare ##########")
        try:
            input_path, config = self.process_request()
            file_name = os.path.basename(input_path)
            
            if 'mono' in input_path:
                raise Exception('Please provide dual PDF or origial PDF for dual-comparison')
            
            # 发送双栏对比开始通知
            self.send_notification(
                "PDF双栏对比开始",
                f"正在生成双栏对比版本: {file_name}",
                "normal"
            )
            
            if not 'dual' in input_path:
                _, dual = self.translate_pdf(input_path, config, progress_callback=True)
                input_path = dual
            output_path = input_path.replace('-dual.pdf', '-compare.pdf')
            self.split_pdf(input_path, output_path, compare=True)
            
            # 发送双栏对比完成通知
            self.send_notification(
                "PDF双栏对比完成",
                f"✅ 双栏对比版本生成成功: {file_name}",
                "normal"
            )
            
            return jsonify({'status': 'success', 'path': output_path}), 200
        except Exception as e:
            # 发送双栏对比错误通知
            file_name = getattr(locals(), 'file_name', '未知文件')
            self.send_notification(
                "PDF双栏对比失败",
                f"❌ 双栏对比生成失败: {file_name}\n🔍 错误: {str(e)[:50]}{'...' if len(str(e)) > 50 else ''}",
                "critical"
            )
            
            print("[compare error]: ", e)
            return jsonify({'status': 'error', 'message': str(e)}), 500

    def download_file(self, filename):
        file_path = os.path.join(self.translated_dir, filename)
        return send_file(file_path, as_attachment=True) if os.path.exists(file_path) else ('File not found', 404)

    def cleanup_port(self, port):
        """清理占用指定端口的进程"""
        try:
            import subprocess
            print(f"🔍 检查端口 {port} 是否被占用...")
            
            # 查找占用端口的进程
            result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                  capture_output=True, text=True)
            
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                print(f"⚠️  发现 {len(pids)} 个进程占用端口 {port}")
                
                for pid in pids:
                    try:
                        # 获取进程信息
                        proc_info = subprocess.run(['ps', '-p', pid, '-o', 'comm='], 
                                                 capture_output=True, text=True)
                        proc_name = proc_info.stdout.strip()
                        
                        print(f"🔄 正在停止进程: PID {pid} ({proc_name})")
                        subprocess.run(['kill', '-9', pid], check=True)
                        print(f"✅ 已停止进程 PID: {pid}")
                        
                    except subprocess.CalledProcessError:
                        print(f"⚠️  无法停止进程 PID: {pid}")
                
                # 等待一下确保端口释放
                import time
                time.sleep(1)
                
                # 再次检查端口
                result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                      capture_output=True, text=True)
                if result.stdout.strip():
                    return False
                else:
                    print(f"✅ 端口 {port} 已成功释放")
                    return True
            else:
                print(f"✅ 端口 {port} 未被占用")
                return True
                
        except Exception as e:
            print(f"❌ 清理端口时出错: {e}")
            return False

    def run(self):
        port = int(sys.argv[1]) if len(sys.argv) > 1 else self.DEFAULT_CONFIG['port']
        
        # 检查并清理端口
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
            print(f"✅ 端口 {port} 可用")
        except OSError:
            print(f"⚠️  端口 {port} 被占用，尝试清理...")
            
            if self.cleanup_port(port):
                print(f"🔄 端口清理成功，继续启动服务...")
            else:
                print(f"❌ 无法清理端口 {port}")
                print(f"🔧 请手动执行以下命令清理端口：")
                print(f"   lsof -ti :{port} | xargs kill -9")
                print(f"   或者重启系统")
                return
        
        print(f"🚀 PDF翻译服务启动，监听端口: {port}")
        try:
            self.app.run(host='0.0.0.0', port=port)
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"❌ 端口 {port} 仍然被占用，启动失败")
                print("🔧 建议手动清理或重启系统")
            else:
                raise e

if __name__ == '__main__':
    translator = PDFTranslator()
    translator.run()
