import os
import sys
import subprocess
import shutil
from pathlib import Path
import time


def send_notification(title, message):
    """
    使用更稳定的 win10toast-py 库发送跨平台的系统通知。
    这是为了解决原 win10toast 库的 'classAtom' AttributeError Bug。
    """
    try:
        if sys.platform == 'win32':
            # 使用修复版的、更稳定的 win10toast-py 库
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
        elif sys.platform == 'darwin':
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(['osascript', '-e', script], check=False)
        else:
            # 其他系统（如Linux）的回退方案
            print(f"[通知] {title}: {message}")
    except Exception as e:
        # 如果任何通知库缺失或失败，就直接打印到控制台，确保程序不崩溃
        print(f"通知发送失败: {e}")


def main():
    """
    脚本的主入口：直接调用 pdf2zh_next 并实时显示进度。
    """
    # 1. 解析从 .cmd 脚本传递过来的参数
    if len(sys.argv) < 2:
        print("错误: 未提供 PDF 文件路径。")
        sys.exit(1)

    pdf_file_path = Path(sys.argv[1])
    additional_options = sys.argv[2:]

    if not pdf_file_path.exists():
        error_msg = f"文件不存在: {pdf_file_path}"
        print(f"错误: {error_msg}")
        send_notification("PDF 翻译失败", f"❌ {error_msg}")
        sys.exit(1)

    # 2. 智能定位 pdf2zh_next 可执行文件
    python_executable_path = Path(sys.executable)
    scripts_dir = python_executable_path.parent
    pdf2zh_executable = scripts_dir / 'pdf2zh_next.exe' if sys.platform == 'win32' else scripts_dir / 'pdf2zh_next'

    if not pdf2zh_executable.exists():
        error_msg = f"在 {scripts_dir} 中找不到 pdf2zh_next 命令。"
        print(f"错误: {error_msg}")
        send_notification("PDF 翻译失败", f"❌ {error_msg}")
        sys.exit(1)

    # 3. 构建最终的命令行指令
    project_path = Path(__file__).parent
    translated_dir = project_path / 'translated'
    translated_dir.mkdir(exist_ok=True)  # 确保输出目录存在

    command = [
        str(pdf2zh_executable),
        str(pdf_file_path),
        '--output', str(translated_dir)
    ]
    command.extend(additional_options)

    # 4. 执行翻译命令
    try:
        send_notification("PDF 翻译任务", f"🚀 正在开始翻译: {pdf_file_path.name}")
        process = subprocess.run(command)

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)

        # 6. 翻译成功后，复制 dual 和 mono 文件到源目录
        print("\n--- 翻译命令执行完毕，正在检查并复制文件... ---")

        base_name = pdf_file_path.stem
        source_dir = translated_dir
        destination_dir = pdf_file_path.parent  # 目标是原始 PDF 所在文件夹

        # ---------- 6.1 旧版命名规则 ----------
        legacy_files = {
            'dual': f"{base_name}-dual.pdf",
            'mono': f"{base_name}-mono.pdf"
        }

        copied_files = []

        for key, fname in legacy_files.items():
            src = source_dir / fname
            if src.exists():
                shutil.copy2(src, destination_dir / fname)
                print(f"[成功] 已复制文件: {fname}")
                copied_files.append(fname)

        # ---------- 6.2 新版 no_watermark 命名规则 ▲新增 ----------
        if len(copied_files) < 2:      # 仍有缺少的情况下才继续探测
            # 可能的多语言后缀，例如 zh-CN / zh / en ……
            dual_candidates = list(source_dir.glob(f"{base_name}.no_watermark.*.dual.pdf"))
            if dual_candidates:
                dual_src = dual_candidates[0]
                # 提取语言代码（最后第二段）
                lang_code = dual_src.stem.split('.')[-2]
                mono_src = source_dir / f"{base_name}.no_watermark.{lang_code}.mono.pdf"

                dual_dst = destination_dir / legacy_files['dual']
                mono_dst = destination_dir / legacy_files['mono']

                try:
                    if dual_src.exists():
                        shutil.copy2(dual_src, dual_dst)
                        print(f"[成功] 已复制文件: {dual_dst.name}")
                        copied_files.append(dual_dst.name)
                    if mono_src.exists():
                        shutil.copy2(mono_src, mono_dst)
                        print(f"[成功] 已复制文件: {mono_dst.name}")
                        copied_files.append(mono_dst.name)
                except Exception as copy_error:
                    print(f"[错误] 复制 no_watermark 文件时失败: {copy_error}")

        # ---------- 6.3 结果判断 ----------
        if copied_files:
            generated_files_str = ", ".join(copied_files)
            success_msg = f"成功生成: {generated_files_str}"
            print(f"\n{success_msg}")
            send_notification("PDF 翻译完成", f"✅ {success_msg}")
            sys.exit(0)
        else:
            raise FileNotFoundError(
                "翻译命令执行成功，但在输出目录未找到任何可复制的翻译文件。"
            )

        # 7. 根据最终复制结果发送通知
        if copied_files:
            generated_files_str = ", ".join(copied_files)
            success_msg = f"成功生成: {generated_files_str}"
            print(f"\n{success_msg}")
            send_notification("PDF 翻译完成", f"✅ {success_msg}")
            sys.exit(0)
        else:
            raise FileNotFoundError("翻译命令执行成功，但未在输出目录找到任何可复制的翻译文件。")

    except subprocess.CalledProcessError as e:
        error_msg = f"翻译过程出错 (退出代码: {e.returncode})。请检查上方日志。"
        print(f"\n错误: {error_msg}")
        send_notification("PDF 翻译失败", f"❌ {error_msg}")
        sys.exit(1)
    except KeyboardInterrupt:
        error_msg = "用户手动中断了翻译任务。"
        print(f"\n操作已取消: {error_msg}")
        send_notification("PDF 翻译取消", f"🟡 {error_msg}")
        sys.exit(1)
    except Exception as e:
        error_msg = f"发生意外错误: {e}"
        print(f"\n错误: {error_msg}")
        send_notification("PDF 翻译失败", f"❌ {error_msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()