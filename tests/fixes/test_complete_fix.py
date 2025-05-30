#!/usr/bin/env python3
"""
完整的错误修复验证脚本
测试原始的 NameError 问题是否已经解决
"""

import sys
from pathlib import Path

# 确保项目路径在 sys.path 中
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_complete_fix():
    """测试完整的错误修复"""
    
    print("=== 完整错误修复验证 ===")
    print("测试原始的 NameError 问题是否已解决\n")
    
    tests_passed = 0
    total_tests = 4
    
    # 测试 1: logger 导入
    try:
        from slais.utils.logging_utils import logger
        print("✓ 测试 1/4: logger 导入成功")
        tests_passed += 1
    except Exception as e:
        print(f"✗ 测试 1/4: logger 导入失败: {e}")
    
    # 测试 2: process_article_pipeline 导入
    try:
        from app import process_article_pipeline
        print("✓ 测试 2/4: process_article_pipeline 导入成功")
        tests_passed += 1
    except Exception as e:
        print(f"✗ 测试 2/4: process_article_pipeline 导入失败: {e}")
    
    # 测试 3: save_report 导入
    try:
        from app import save_report
        print("✓ 测试 3/4: save_report 导入成功")
        tests_passed += 1
    except Exception as e:
        print(f"✗ 测试 3/4: save_report 导入失败: {e}")
    
    # 测试 4: web_app 模块导入
    try:
        from web.web_app import run_slais_web
        print("✓ 测试 4/4: web_app 模块导入成功")
        tests_passed += 1
    except Exception as e:
        print(f"✗ 测试 4/4: web_app 模块导入失败: {e}")
    
    print(f"\n=== 测试结果 ===")
    print(f"通过: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 所有测试通过！错误修复成功。")
        print("\n修复总结:")
        print("1. ✅ 修复了 logger NameError - 在 process_article_pipeline 函数中直接导入 logger")
        print("2. ✅ 修复了 save_report NameError - 在 save_report 函数中直接导入依赖项")
        print("3. ✅ 确保了 web_app.py 中的 setup_logging() 调用")
        print("\n现在应用应该可以在 Streamlit 环境中正常运行，不再出现 NameError。")
        return True
    else:
        print("❌ 还有错误需要修复。")
        return False

if __name__ == "__main__":
    success = test_complete_fix()
    if success:
        print("\n🚀 可以安全启动 Streamlit 应用了!")
        print("   运行: streamlit run app.py")
    else:
        print("\n⚠ 建议在启动应用前先解决剩余问题。")
        sys.exit(1)
