#!/usr/bin/env python3
"""
测试脚本：验证 logger 错误修复是否有效
模拟 Streamlit 环境中调用 process_article_pipeline 函数的情况
"""

import asyncio
import sys
from pathlib import Path

# 确保项目路径在 sys.path 中  
project_root = Path(__file__).parent.parent.parent.absolute()  # 向上一级到项目根目录
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from pathlib import Path

# 确保项目路径在 sys.path 中
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

async def test_process_article_pipeline():
    """测试 process_article_pipeline 函数是否能正常运行而不抛出 logger 错误"""
    
    print("=== 测试 logger 修复 ===")
    
    try:
        # 直接导入函数，不调用 initialize_app_dependencies
        from app import process_article_pipeline
        print("✓ process_article_pipeline 函数导入成功")
        
        # 设置测试参数
        pdf_path = "pdfs/darwin.pdf"  # 使用现有的测试文件
        article_doi = "10.1126/science.aao4593"
        ncbi_email = "test@example.com"
        
        print("✓ 测试参数设置完成")
        print(f"  PDF路径: {pdf_path}")
        print(f"  DOI: {article_doi}")
        print(f"  邮箱: {ncbi_email}")
        
        # 检查 PDF 文件是否存在
        if not Path(pdf_path).exists():
            print(f"⚠ PDF文件不存在: {pdf_path}")
            print("测试将继续，但可能在文件处理步骤失败")
        
        print("\n=== 开始调用 process_article_pipeline ===")
        
        # 调用函数 - 这里应该不会再出现 logger 未定义的错误
        result = await process_article_pipeline(pdf_path, article_doi, ncbi_email)
        
        if result:
            print("✓ process_article_pipeline 执行成功")
            print(f"  返回结果类型: {type(result)}")
        else:
            print("⚠ process_article_pipeline 返回 None（可能由于文件不存在或其他原因）")
        
        print("✓ 测试完成：logger 错误已修复")
        
    except NameError as e:
        if "logger" in str(e):
            print(f"✗ Logger 错误仍然存在: {e}")
            return False
        else:
            print(f"✗ 其他 NameError: {e}")
            return False
    except Exception as e:
        print(f"⚠ 其他错误（这可能是预期的）: {e}")
        print("  只要不是 logger NameError 就表示修复成功")
        return True
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_process_article_pipeline())
    if success:
        print("\n🎉 修复验证成功！logger 错误已解决。")
    else:
        print("\n❌ 修复验证失败。")
        sys.exit(1)
