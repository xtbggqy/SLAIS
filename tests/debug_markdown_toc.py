"""
调试markdown库的toc扩展生成的HTML结构
"""
import markdown
from pathlib import Path
import os
import sys

# 将项目根目录添加到sys.path，以便导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slais import config

def debug_toc_html():
    output_base_dir = Path(config.settings.OUTPUT_BASE_DIR)
    test_md_file = output_base_dir / "test_analysis_report.md"
    
    # 创建一个包含足够标题的测试Markdown文件以触发目录生成
    with open(test_md_file, "w", encoding="utf-8") as f:
        f.write("# 测试报告\n\n## 内容部分\n\n这是测试内容。\n\n## 另一部分\n\n更多内容。\n\n### 子部分\n\n子内容。\n\n## 参考文献\n\n- 文献1\n- 文献2\n\n## 相关文献\n\n- 相关文献1\n- 相关文献2")
    
    # 读取Markdown内容
    with open(test_md_file, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    # 转换为HTML，启用toc扩展
    html_content = markdown.markdown(md_content, extensions=['extra', 'toc'])
    
    # 输出生成的HTML内容
    print("生成的HTML内容:")
    print(html_content)
    
    # 清理测试文件
    if test_md_file.exists():
        os.remove(test_md_file)

if __name__ == "__main__":
    debug_toc_html()
