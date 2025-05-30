#!/usr/bin/env python3
"""
测试脚本：验证 save_csv_report 的 logger NameError 修复
"""

import sys
from pathlib import Path

# 确保项目路径在 sys.path 中
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_save_csv_report_fix():
    """测试 save_csv_report 函数的 logger NameError 修复"""
    
    print("=== 测试 save_csv_report logger 修复 ===")
    
    try:
        # 1. 导入 save_csv_report 函数
        print("正在导入 save_csv_report 函数...")
        
        # 直接导入函数而不是整个模块
        import importlib.util
        app_spec = importlib.util.spec_from_file_location("app", project_root / "app.py")
        app_module = importlib.util.module_from_spec(app_spec)
        
        # 设置必要的模块路径
        sys.modules['app'] = app_module
        app_spec.loader.exec_module(app_module)
        
        save_csv_report = app_module.save_csv_report
        print("✓ save_csv_report 函数导入成功")
        
        # 2. 测试函数调用（使用临时文件）
        import tempfile
        import os
        
        print("正在测试函数调用...")
        
        # 创建测试数据
        test_data = [
            {"doi": "10.1234/test1", "title": "Test Paper 1", "authors_str": "Author A"},
            {"doi": "10.1234/test2", "title": "Test Paper 2", "authors_str": "Author B"}
        ]
        
        fieldnames = ["doi", "title", "authors_str", "journal", "pub_date"]
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            tmp_filepath = Path(tmp_file.name)
        
        try:
            # 测试保存 CSV 报告
            save_csv_report(test_data, tmp_filepath, fieldnames)
            print("✓ save_csv_report 函数调用成功，无 logger NameError")
            
            # 验证文件是否创建
            if tmp_filepath.exists():
                print("✓ CSV 文件成功创建")
                
                # 读取并验证内容
                with open(tmp_filepath, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                    if "Test Paper 1" in content and "Test Paper 2" in content:
                        print("✓ CSV 内容验证成功")
                    else:
                        print("⚠ CSV 内容可能不完整")
            else:
                print("⚠ CSV 文件未创建")
                
        finally:
            # 清理临时文件
            if tmp_filepath.exists():
                os.unlink(tmp_filepath)
        
        print("✓ save_csv_report logger 修复验证成功")
        return True
        
    except NameError as e:
        if "logger" in str(e):
            print(f"✗ save_csv_report 仍然有 logger NameError: {e}")
            return False
        else:
            print(f"✗ save_csv_report 其他 NameError: {e}")
            return False
    except Exception as e:
        print(f"✗ save_csv_report 测试错误: {e}")
        return False

if __name__ == "__main__":
    success = test_save_csv_report_fix()
    if success:
        print("\n🎉 save_csv_report logger 修复验证成功！")
    else:
        print("\n❌ save_csv_report logger 修复验证失败。")
        sys.exit(1)
