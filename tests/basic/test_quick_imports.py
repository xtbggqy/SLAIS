#!/usr/bin/env python3
"""
快速验证测试：检查所有测试文件的导入是否正常
"""

import sys
from pathlib import Path

# 确保项目路径在 sys.path 中  
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_imports():
    """测试关键模块导入"""
    
    print("=== 快速导入测试 ===")
    
    tests = [
        ("logger 导入", "from slais.utils.logging_utils import logger"),
        ("app 模块导入", "import app"),
        ("web_app 模块导入", "from web import web_app"),
        ("config 导入", "from slais import config"),
        ("process_article_pipeline 函数", "from app import process_article_pipeline"),
        ("save_report 函数", "from app import save_report"),
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
        print("🎉 所有导入测试通过！测试组织完成。")
        return True
    else:
        print("❌ 部分导入仍有问题。")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
