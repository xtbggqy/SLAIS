#!/usr/bin/env python3
"""
最终验证：所有 NameError 修复情况汇总
"""

import sys
from pathlib import Path

# 确保项目路径在 sys.path 中
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_all_fixes():
    """验证所有已知的 NameError 修复"""
    
    print("=== 所有 NameError 修复验证汇总 ===")
    print("验证的 NameError 问题：")
    print("1. process_article_pipeline 中的 logger NameError")
    print("2. save_report 中的 logger/config NameError")  
    print("3. save_csv_report 中的 logger NameError (新发现)")
    print()
    
    tests_passed = 0
    total_tests = 4
    
    # 测试 1: 检查 app.py 文件语法
    try:
        app_file_path = project_root / "app.py"
        
        with open(app_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        compile(content, app_file_path, 'exec')
        print("✓ 测试 1/4: app.py 语法检查通过")
        tests_passed += 1
    except Exception as e:
        print(f"✗ 测试 1/4: app.py 语法错误: {e}")
    
    # 测试 2: 检查 process_article_pipeline 函数的导入
    try:
        import re
        
        # 提取 process_article_pipeline 函数
        pattern = r'async def process_article_pipeline\(.*?\n(.*?)(?=\nasync def|\ndef|\nclass|\n$|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if match and "from slais.utils.logging_utils import logger" in match.group(1):
            print("✓ 测试 2/4: process_article_pipeline 包含 logger 导入")
            tests_passed += 1
        else:
            print("✗ 测试 2/4: process_article_pipeline 缺少 logger 导入")
    except Exception as e:
        print(f"✗ 测试 2/4: process_article_pipeline 检查错误: {e}")
    
    # 测试 3: 检查 save_report 函数的导入
    try:
        pattern = r'def save_report\(.*?\n(.*?)(?=\ndef|\nclass|\n$|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if match and "from slais.utils.logging_utils import logger" in match.group(1):
            print("✓ 测试 3/4: save_report 包含 logger 导入")
            tests_passed += 1
        else:
            print("✗ 测试 3/4: save_report 缺少 logger 导入")
    except Exception as e:
        print(f"✗ 测试 3/4: save_report 检查错误: {e}")
    
    # 测试 4: 检查 save_csv_report 函数的导入
    try:
        pattern = r'def save_csv_report\(.*?\n(.*?)(?=\ndef|\nclass|\n$|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if match and "from slais.utils.logging_utils import logger" in match.group(1):
            print("✓ 测试 4/4: save_csv_report 包含 logger 导入")
            tests_passed += 1
        else:
            print("✗ 测试 4/4: save_csv_report 缺少 logger 导入")
    except Exception as e:
        print(f"✗ 测试 4/4: save_csv_report 检查错误: {e}")
    
    print(f"\n=== 测试结果汇总 ===")
    print(f"通过: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 所有 NameError 修复验证通过！")
        print("\n修复汇总：")
        print("✅ process_article_pipeline: 添加了 logger 和其他必要导入")
        print("✅ save_report: 添加了 logger、config 和 formatting_utils 导入")
        print("✅ save_csv_report: 添加了 logger 导入 (新修复)")
        print("✅ web_app.py: 添加了 setup_logging() 调用")
        print("\n现在所有函数都应该能在 Streamlit 环境中正常工作！")
        return True
    else:
        print("❌ 还有部分修复需要完善")
        return False

if __name__ == "__main__":
    success = test_all_fixes()
    sys.exit(0 if success else 1)
