#!/usr/bin/env python3
"""
参考文献获取问题诊断脚本
用于测试和调试Semantic Scholar API的参考文献获取功能
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from slais import config
from slais.semantic_scholar_client import SemanticScholarClient
from slais.utils.logging_utils import logger

async def test_references_api():
    """测试参考文献API调用"""
    print("🔍 参考文献获取诊断开始...\n")
    
    # 初始化客户端
    s2_client = SemanticScholarClient()
    
    # 测试的Paper ID (从日志中获取的)
    test_paper_ids = [
        "7fdd3e56f266c3532ada0d01ba0dba9b7cb61de1",  # 当前失败的Paper ID
        "649def34f8be52c8b66281af98ae884c09aef38b",  # 已知有参考文献的Paper ID (可选)
    ]
    
    for paper_id in test_paper_ids:
        print(f"📋 测试Paper ID: {paper_id}")
        
        # 1. 测试基本的参考文献API调用
        print("1. 测试直接API调用...")
        try:
            url = f"{s2_client.base_url}/paper/{paper_id}/references"
            params = {
                "fields": config.S2_REFERENCES_FIELDS,
                "limit": 10  # 限制为10条以便快速测试
            }
            
            response_data = await s2_client._make_request(
                'GET', url, params=params, 
                error_msg_prefix=f"[Debug] PaperID {paper_id}"
            )
            
            print(f"   ✅ API响应状态: 成功")
            print(f"   📊 响应数据类型: {type(response_data)}")
            
            if response_data:
                print(f"   📝 响应键: {list(response_data.keys()) if isinstance(response_data, dict) else 'N/A'}")
                
                data_field = response_data.get("data") if isinstance(response_data, dict) else None
                print(f"   📄 data字段类型: {type(data_field)}")
                print(f"   📊 data字段长度: {len(data_field) if data_field else 0}")
                
                if data_field and len(data_field) > 0:
                    # 分析第一条记录
                    first_ref = data_field[0]
                    print(f"   🔍 第一条参考文献结构:")
                    print(f"      - 类型: {type(first_ref)}")
                    if isinstance(first_ref, dict):
                        print(f"      - 键: {list(first_ref.keys())}")
                        cited_paper = first_ref.get('citedPaper')
                        if cited_paper:
                            print(f"      - citedPaper类型: {type(cited_paper)}")
                            print(f"      - citedPaper键: {list(cited_paper.keys()) if isinstance(cited_paper, dict) else 'N/A'}")
                            external_ids = cited_paper.get('externalIds') if isinstance(cited_paper, dict) else None
                            if external_ids:
                                print(f"      - externalIds: {external_ids}")
                else:
                    print("   ⚠️  data字段为空或无内容")
            else:
                print("   ❌ API响应为空")
                
        except Exception as e:
            print(f"   ❌ API调用失败: {e}")
        
        # 2. 测试客户端方法
        print("2. 测试get_references_by_paper_id方法...")
        try:
            references_dois = await s2_client.get_references_by_paper_id(paper_id, limit=10)
            print(f"   ✅ 方法调用成功")
            print(f"   📊 获取DOI数量: {len(references_dois)}")
            if references_dois:
                print(f"   📝 前3个DOI: {references_dois[:3]}")
            else:
                print("   ⚠️  未获取到任何DOI")
        except Exception as e:
            print(f"   ❌ 方法调用失败: {e}")
        
        # 3. 测试batch方法
        print("3. 测试batch_get_references_by_papers方法...")
        try:
            batch_results = await s2_client.batch_get_references_by_papers(paper_id, limit=10)
            print(f"   ✅ 批处理方法调用成功")
            print(f"   📊 获取详情数量: {len(batch_results)}")
            if batch_results:
                first_result = batch_results[0]
                print(f"   🔍 第一条结果字段: {list(first_result.keys()) if isinstance(first_result, dict) else 'N/A'}")
                if isinstance(first_result, dict):
                    print(f"      - DOI: {first_result.get('doi', 'N/A')}")
                    print(f"      - 标题: {first_result.get('title', 'N/A')[:50]}...")
            else:
                print("   ⚠️  未获取到任何详情")
        except Exception as e:
            print(f"   ❌ 批处理方法调用失败: {e}")
        
        print("-" * 60)
    
    # 4. 测试已知有参考文献的论文
    print("4. 测试已知DOI的参考文献获取...")
    test_doi = "10.1126/science.aao4593"  # 从配置中的测试DOI
    try:
        # 先通过DOI获取paper详情
        paper_details = await s2_client.get_paper_details_by_doi(test_doi)
        if paper_details and paper_details.get("paperId"):
            test_paper_id = paper_details["paperId"]
            print(f"   📋 DOI {test_doi} 对应的Paper ID: {test_paper_id}")
            
            # 测试参考文献获取
            references_dois = await s2_client.get_references_by_paper_id(test_paper_id, limit=5)
            print(f"   📊 该论文的参考文献数量: {len(references_dois)}")
            if references_dois:
                print(f"   ✅ 参考文献获取正常，前3个DOI: {references_dois[:3]}")
            else:
                print("   ⚠️  该论文也没有参考文献或API有问题")
        else:
            print(f"   ❌ 无法通过DOI {test_doi} 获取论文信息")
    except Exception as e:
        print(f"   ❌ 测试已知DOI失败: {e}")

async def test_api_quota_and_limits():
    """测试API配额和限制"""
    print("\n🔒 API配额和限制测试...")
    
    s2_client = SemanticScholarClient()
    
    # 测试API密钥状态
    api_key = s2_client.api_key
    if api_key:
        print(f"   ✅ 使用API密钥: {api_key[:8]}...{api_key[-4:]}")
    else:
        print("   ⚠️  未使用API密钥，可能受到更严格的限流")
    
    # 测试一个简单的API调用
    try:
        test_url = f"{s2_client.base_url}/paper/649def34f8be52c8b66281af98ae884c09aef38b"
        response = await s2_client._make_request('GET', test_url, params={"fields": "title"})
        if response:
            print("   ✅ API基本调用正常")
        else:
            print("   ❌ API基本调用异常")
    except Exception as e:
        print(f"   ❌ API调用出错: {e}")

def main():
    """主函数"""
    asyncio.run(test_references_api())
    asyncio.run(test_api_quota_and_limits())
    
    print("\n💡 诊断建议:")
    print("1. 如果所有测试都返回0结果，可能是API配额问题")
    print("2. 如果部分论文有结果，说明API正常，但当前论文确实无参考文献")
    print("3. 如果API调用异常，检查网络连接和API配置")
    print("4. 建议尝试不同的论文ID进行对比测试")

if __name__ == "__main__":
    main() 