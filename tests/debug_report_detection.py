#!/usr/bin/env python3
"""
调试脚本：检查报告检测逻辑
"""
import os
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from slais import config

def debug_report_detection():
    """调试报告检测逻辑"""
    print("=== 调试报告检测逻辑 ===")
    
    # 测试用例：已知存在的报告
    pdf_stem = "tmpdzvlzhrm"
    
    print(f"PDF stem: {pdf_stem}")
    print(f"config.settings.OUTPUT_BASE_DIR: {config.settings.OUTPUT_BASE_DIR}")
    
    # 构建输出目录路径 - 完全模拟 Web UI 的逻辑
    output_dir = Path(config.settings.OUTPUT_BASE_DIR) / pdf_stem
    print(f"output_dir: {output_dir}")
    print(f"output_dir exists: {output_dir.exists()}")
    print(f"output_dir is_dir: {output_dir.is_dir()}")
    
    if output_dir.exists():
        print(f"Directory contents:")
        for item in output_dir.iterdir():
            print(f"  - {item.name} ({'dir' if item.is_dir() else 'file'})")
    
    # 测试 glob 模式 - 完全模拟 Web UI 的逻辑
    glob_pattern = f"{pdf_stem}_analysis_report_*.md"
    print(f"\nGlob pattern: {glob_pattern}")
    
    # 使用完全相同的逻辑
    md_files = sorted(output_dir.glob(glob_pattern), key=os.path.getmtime, reverse=True)
    print(f"Found files: {len(md_files)}")
    for f in md_files:
        print(f"  - {f}")
        print(f"    exists: {f.exists()}")
        print(f"    mtime: {os.path.getmtime(f)}")
    
    # 模拟 Web UI 中的判断逻辑
    print(f"\n=== 模拟 Web UI 判断逻辑 ===")
    if md_files:
        print("✅ md_files 列表不为空，应该显示报告预览")
        try:
            with open(md_files[0], "r", encoding="utf-8") as f:
                content = f.read()
            print(f"✅ 成功读取报告文件，长度: {len(content)} 字符")
            print(f"✅ 下载按钮文件名应该是: {md_files[-1].name}")
        except Exception as e:
            print(f"❌ 读取报告文件失败: {e}")
    else:
        print("❌ md_files 列表为空，会显示'未找到生成的Markdown报告'")
    
    # 测试绝对路径
    print(f"\n=== 路径信息 ===")
    print(f"Current working directory: {os.getcwd()}")
    print(f"output_dir absolute: {output_dir.absolute()}")
    
    # 手动列出所有 .md 文件
    print(f"\nAll .md files in directory:")
    if output_dir.exists():
        for f in output_dir.glob("*.md"):
            print(f"  - {f.name}")

def debug_web_ui_simulation():
    """完全模拟 Web UI 中的处理逻辑"""
    print("\n" + "="*50)
    print("=== 完全模拟 Web UI 处理逻辑 ===")
    print("="*50)
    
    # 模拟 Web UI 中的变量设置
    pdf_stem = "tmpdzvlzhrm"  # 这应该来自用户上传的文件名或默认文件名
    
    print(f"模拟 Web UI 变量:")
    print(f"  pdf_stem = '{pdf_stem}'")
    print(f"  config.settings.OUTPUT_BASE_DIR = '{config.settings.OUTPUT_BASE_DIR}'")
    
    # 完全复制 Web UI 中的代码逻辑
    output_dir = Path(config.settings.OUTPUT_BASE_DIR) / pdf_stem
    md_files = sorted(output_dir.glob(f"{pdf_stem}_analysis_report_*.md"), key=os.path.getmtime, reverse=True)
    
    print(f"\n执行结果:")
    print(f"  output_dir = {output_dir}")
    print(f"  glob pattern = '{pdf_stem}_analysis_report_*.md'")
    print(f"  md_files length = {len(md_files)}")
    
    if md_files:
        print("✅ 条件判断: md_files 为真，应该显示报告")
        print(f"  最新文件: {md_files[0]}")
        print(f"  下载文件名: {md_files[-1].name}")  # 注意这里的 bug
    else:
        print("❌ 条件判断: md_files 为假，显示'未找到生成的Markdown报告'")
        
        # 进一步诊断
        print(f"\n进一步诊断:")
        print(f"  输出目录是否存在: {output_dir.exists()}")
        if output_dir.exists():
            all_files = list(output_dir.iterdir())
            print(f"  目录中所有文件: {[f.name for f in all_files]}")
            md_files_manual = [f for f in all_files if f.name.endswith('.md') and 'analysis_report' in f.name]
            print(f"  手动筛选的 md 文件: {[f.name for f in md_files_manual]}")
            
            # 检查 glob 模式是否有问题
            pattern = f"{pdf_stem}_analysis_report_*.md"
            manual_glob = list(output_dir.glob(pattern))
            print(f"  glob('{pattern}') 结果: {[f.name for f in manual_glob]}")
        else:
            print(f"  输出目录不存在!")

if __name__ == "__main__":
    debug_report_detection()
    debug_web_ui_simulation()
