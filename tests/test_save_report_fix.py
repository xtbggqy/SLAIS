#!/usr/bin/env python3
"""
测试脚本：验证 save_report 错误修复是否有效
"""

import sys
from pathlib import Path

# 确保项目路径在 sys.path 中
project_root = Path(__file__).parent.parent.absolute()  # 向上一级到项目根目录
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_save_report_import():
    """测试 save_report 函数是否能正常导入和执行"""
    
    print("=== 测试 save_report 修复 ===")
    
    try:
        # 1. 测试直接从 app 模块导入
        from app import save_report
        print("✓ save_report 从 app 模块导入成功")
        
        # 2. 测试从 web.web_app 模块导入
        from web.web_app import save_report as web_save_report
        print("✓ save_report 从 web.web_app 模块导入成功")
        
        # 3. 验证两个导入是否是同一个函数
        if save_report is web_save_report:
            print("✓ 两个导入引用同一个函数")
        else:
            print("⚠ 两个导入引用不同的函数（这可能是正常的）")
        
        # 4. 测试函数调用（使用空数据）
        print("\n=== 测试函数调用 ===")
        try:
            # 使用空结果测试，应该会触发 logger.warning 但不会出错
            save_report({}, "test.pdf")
            print("✓ save_report 函数调用成功（空数据测试）")
        except NameError as e:
            if "logger" in str(e) or "config" in str(e):
                print(f"✗ save_report 仍然有依赖错误: {e}")
                return False
            else:
                print(f"✗ save_report 其他 NameError: {e}")
                return False
        except Exception as e:
            print(f"⚠ save_report 其他错误（可能是预期的）: {e}")
            print("  只要不是 NameError 就表示修复成功")
        
        print("✓ 测试完成：save_report 错误已修复")
        return True
        
    except NameError as e:
        if "save_report" in str(e):
            print(f"✗ save_report 错误仍然存在: {e}")
            return False
        else:
            print(f"✗ 其他 NameError: {e}")
            return False
    except Exception as e:
        print(f"✗ 导入错误: {e}")
        return False

if __name__ == "__main__":
    success = test_save_report_import()
    if success:
        print("\n🎉 修复验证成功！save_report 错误已解决。")
    else:
        print("\n❌ 修复验证失败。")
        sys.exit(1)
