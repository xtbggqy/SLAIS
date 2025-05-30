#!/usr/bin/env python3
"""
超简单导入测试：仅测试模块导入，不执行任何函数
"""

import sys
from pathlib import Path

# 确保项目路径在 sys.path 中  
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_basic_imports():
    """测试基本模块导入"""
    
    print("=== 基本导入测试 ===")
    
    tests = [
        ("slais.utils.logging_utils", "import slais.utils.logging_utils"),
        ("slais config", "import slais.config"),
        ("app module", "import app"),
        ("web.web_app", "import web.web_app"),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, import_stmt in tests:
        try:
            exec(import_stmt)
            print(f"✓ {test_name}: 成功")
            passed += 1
        except Exception as e:
            print(f"✗ {test_name}: 失败 - {e}")
    
    print(f"\n=== 测试结果 ===")
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("🎉 所有基本导入测试通过！")
        print("✅ 测试文件组织完成，导入路径修复成功！")
        return True
    else:
        print("❌ 部分导入仍有问题。")
        return False

if __name__ == "__main__":
    success = test_basic_imports()
    sys.exit(0 if success else 1)
