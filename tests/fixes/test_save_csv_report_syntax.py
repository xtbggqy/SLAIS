#!/usr/bin/env python3
"""
简单测试：验证 save_csv_report 的 logger 修复
只检查语法和导入，不执行复杂逻辑
"""

import sys
from pathlib import Path

# 确保项目路径在 sys.path 中
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_save_csv_report_syntax():
    """测试 save_csv_report 函数的语法和导入"""
    
    print("=== 简单语法测试：save_csv_report logger 修复 ===")
    
    try:
        # 读取 app.py 文件并检查 save_csv_report 函数
        app_file_path = project_root / "app.py"
        
        with open(app_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查 save_csv_report 函数是否存在
        if "def save_csv_report(" in content:
            print("✓ save_csv_report 函数定义找到")
        else:
            print("✗ save_csv_report 函数定义未找到")
            return False
        
        # 检查函数内是否有 logger 导入
        import re
        
        # 提取 save_csv_report 函数
        function_pattern = r'def save_csv_report\(.*?\n(.*?)(?=\ndef|\nclass|\n$|\Z)'
        match = re.search(function_pattern, content, re.DOTALL)
        
        if match:
            function_body = match.group(1)
            
            # 检查是否有 logger 导入
            if "from slais.utils.logging_utils import logger" in function_body:
                print("✓ save_csv_report 函数中包含 logger 导入")
            else:
                print("✗ save_csv_report 函数中缺少 logger 导入")
                return False
            
            # 检查是否使用了 logger
            if "logger." in function_body:
                print("✓ save_csv_report 函数中使用了 logger")
            else:
                print("⚠ save_csv_report 函数中未使用 logger")
            
        else:
            print("✗ 无法提取 save_csv_report 函数体")
            return False
        
        # 尝试编译检查语法
        try:
            compile(content, app_file_path, 'exec')
            print("✓ app.py 语法检查通过")
        except SyntaxError as e:
            print(f"✗ app.py 语法错误: {e}")
            return False
        
        print("✓ save_csv_report logger 修复语法验证成功")
        return True
        
    except Exception as e:
        print(f"✗ 测试错误: {e}")
        return False

if __name__ == "__main__":
    success = test_save_csv_report_syntax()
    if success:
        print("\n🎉 save_csv_report logger 修复语法验证成功！")
        print("修复内容：在 save_csv_report 函数开头添加了 logger 导入")
    else:
        print("\n❌ save_csv_report logger 修复语法验证失败。")
        sys.exit(1)
