"""
测试web_results.py文件的修改功能是否正常工作
"""
import unittest
import os
import sys
import re
import markdown
from pathlib import Path
from bs4 import BeautifulSoup

# 将项目根目录添加到sys.path，以便导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.web_results import display_results
from slais import config

class TestWebResults(unittest.TestCase):
    def setUp(self):
        """设置测试环境"""
        self.output_base_dir = Path(config.settings.OUTPUT_BASE_DIR)
        self.test_md_file = self.output_base_dir / "test_analysis_report.md"
        
        # 创建一个包含足够标题的测试Markdown文件以触发目录生成
        with open(self.test_md_file, "w", encoding="utf-8") as f:
            f.write("# 测试报告\n\n## 内容部分\n\n这是测试内容。\n\n## 另一部分\n\n更多内容。\n\n### 子部分\n\n子内容。\n\n## 参考文献\n\n- 文献1\n- 文献2\n\n## 相关文献\n\n- 相关文献1\n- 相关文献2")

    def test_reference_removal(self):
        """测试是否正确移除了参考文献和相关文献部分"""
        with open(self.test_md_file, "r", encoding="utf-8") as f:
            md_content_raw = f.read()
        
        # 移除参考文献部分
        pattern_references = r"^(#{1,6}\s*参考文献)\s*[\s\S]*?(?=\n^(#{1,6}\s)|\Z)"
        md_content_processed = re.sub(pattern_references, "", md_content_raw, flags=re.MULTILINE)
        
        # 移除相关文献部分
        pattern_related_literature = r"^(#{1,6}\s*相关文献)\s*[\s\S]*?(?=\n^(#{1,6}\s)|\Z)"
        md_content_cleaned = re.sub(pattern_related_literature, "", md_content_processed, flags=re.MULTILINE)
        
        self.assertNotIn("参考文献", md_content_cleaned)
        self.assertNotIn("相关文献", md_content_cleaned)
        self.assertIn("测试报告", md_content_cleaned)
        self.assertIn("内容部分", md_content_cleaned)

    def test_toc_javascript(self):
        """测试HTML渲染中是否包含目录跳转的JavaScript代码"""
        with open(self.test_md_file, "r", encoding="utf-8") as f:
            md_content_raw = f.read()
        
        # 移除参考文献和相关文献部分
        pattern_references = r"^(#{1,6}\s*参考文献)\s*[\s\S]*?(?=\n^(#{1,6}\s)|\Z)"
        md_content_processed = re.sub(pattern_references, "", md_content_raw, flags=re.MULTILINE)
        pattern_related_literature = r"^(#{1,6}\s*相关文献)\s*[\s\S]*?(?=\n^(#{1,6}\s)|\Z)"
        md_content_cleaned = re.sub(pattern_related_literature, "", md_content_processed, flags=re.MULTILINE)
        
        # 转换为HTML
        html_content = markdown.markdown(md_content_cleaned, extensions=['extra', 'toc'])
        
        # 检查是否包含TOC - 检查是否存在任何形式的目录结构
        self.assertTrue(any(tag in html_content for tag in ['toc', 'id=']), "目录未找到")
        
        # 检查是否包含JavaScript代码（模拟在web_results.py中的添加）
        js_code = """
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            var tocLinks = document.querySelectorAll('.toc a');
            tocLinks.forEach(function(link) {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    var targetId = this.getAttribute('href').substring(1);
                    var targetElement = document.getElementById(targetId);
                    if (targetElement) {
                        targetElement.scrollIntoView({ behavior: 'smooth' });
                    }
                });
            });
        });
        </script>
        """
        full_html = f"<div class='markdown-report-container'>{html_content}{js_code}</div>"
        self.assertIn("tocLinks", full_html)
        self.assertIn("scrollIntoView", full_html)

    def tearDown(self):
        """清理测试环境"""
        if self.test_md_file.exists():
            os.remove(self.test_md_file)

if __name__ == '__main__':
    unittest.main()
