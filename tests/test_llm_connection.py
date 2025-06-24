#!/usr/bin/env python3
"""
LLM连接问题诊断脚本
用于测试阿里云通义千问API的连接和配置问题
"""

import os
import sys
import time
import asyncio
import requests
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from slais import config
from slais.utils.logging_utils import logger

def test_network_connection():
    """测试网络连接"""
    logger.info("🔍 测试1: 网络连接检查")
    
    # 测试基本网络连接
    test_urls = [
        "https://www.baidu.com",
        "https://dashscope.aliyuncs.com",
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ]
    
    for url in test_urls:
        try:
            response = requests.get(url, timeout=10)
            logger.info(f"✅ {url} - 状态码: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ {url} - 连接失败: {e}")

def test_api_config():
    """测试API配置"""
    logger.info("🔍 测试2: API配置检查")
    
    # 检查必要的环境变量
    required_vars = [
        "OPENAI_API_KEY",
        "OPENAI_API_BASE_URL", 
        "OPENAI_API_MODEL"
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # 隐藏API密钥的部分内容
            if "KEY" in var and len(value) > 8:
                display_value = f"{value[:4]}...{value[-4:]}"
            else:
                display_value = value
            logger.info(f"✅ {var}: {display_value}")
        else:
            logger.error(f"❌ {var}: 未设置")

def test_simple_api_request():
    """测试简单的API请求"""
    logger.info("🔍 测试3: 简单API请求")
    
    try:
        from agents.llm_clients import OpenAIClient
        
        client = OpenAIClient()
        logger.info(f"✅ OpenAI客户端初始化成功")
        logger.info(f"   模型: {client.model}")
        logger.info(f"   Base URL: {client.client.base_url}")
        
        # 发送简单请求
        logger.info("📡 发送简单测试请求...")
        
        simple_prompt = "请简单回答：今天天气怎么样？（这是一个API连接测试）"
        
        start_time = time.time()
        response = client.call_llm(simple_prompt)
        end_time = time.time()
        
        if response:
            logger.info(f"✅ API请求成功！")
            logger.info(f"   响应时间: {end_time - start_time:.2f}秒")
            logger.info(f"   响应长度: {len(response)}字符")
            logger.info(f"   响应内容前100字符: {response[:100]}...")
        else:
            logger.error("❌ API请求失败 - 返回空响应")
            
    except Exception as e:
        logger.error(f"❌ API请求失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())

def test_concurrent_requests():
    """测试并发请求"""
    logger.info("🔍 测试4: 并发请求测试")
    
    try:
        from agents.llm_clients import OpenAIClient
        
        client = OpenAIClient()
        
        async def single_request(request_id):
            """单个异步请求"""
            try:
                prompt = f"测试请求 {request_id}: 请回答数字 {request_id}"
                start_time = time.time()
                
                # 这里我们模拟同步调用，因为当前的client可能不支持异步
                response = client.call_llm(prompt)
                
                end_time = time.time()
                
                if response:
                    logger.info(f"✅ 请求 {request_id} 成功 - 用时: {end_time - start_time:.2f}秒")
                    return True
                else:
                    logger.error(f"❌ 请求 {request_id} 失败 - 空响应")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ 请求 {request_id} 失败: {e}")
                return False
        
        # 测试不同数量的并发请求
        for concurrent_count in [1, 2, 3, 5]:
            logger.info(f"🔄 测试 {concurrent_count} 个并发请求...")
            
            start_time = time.time()
            success_count = 0
            
            for i in range(concurrent_count):
                if single_request(i + 1):
                    success_count += 1
                # 添加小延迟避免过快的请求
                time.sleep(0.5)
            
            end_time = time.time()
            
            logger.info(f"📊 并发数 {concurrent_count}: {success_count}/{concurrent_count} 成功, 总用时: {end_time - start_time:.2f}秒")
            
            # 给API一些休息时间
            time.sleep(2)
            
    except Exception as e:
        logger.error(f"❌ 并发测试失败: {e}")

def test_rate_limiting():
    """测试速率限制"""
    logger.info("🔍 测试5: 速率限制测试")
    
    try:
        from agents.llm_clients import OpenAIClient
        
        client = OpenAIClient()
        
        logger.info("🔄 快速连续发送请求以测试速率限制...")
        
        for i in range(10):
            try:
                start_time = time.time()
                response = client.call_llm(f"快速测试 {i+1}: 请回答OK")
                end_time = time.time()
                
                if response:
                    logger.info(f"✅ 快速请求 {i+1} 成功 - 用时: {end_time - start_time:.2f}秒")
                else:
                    logger.error(f"❌ 快速请求 {i+1} 失败")
                    
            except Exception as e:
                logger.error(f"❌ 快速请求 {i+1} 异常: {e}")
                
            # 很短的延迟
            time.sleep(0.1)
            
    except Exception as e:
        logger.error(f"❌ 速率限制测试失败: {e}")

def main():
    """主测试函数"""
    logger.info("🚀 开始LLM连接诊断...")
    logger.info("=" * 60)
    
    # 运行所有测试
    test_network_connection()
    print()
    
    test_api_config()
    print()
    
    test_simple_api_request()
    print()
    
    test_concurrent_requests()
    print()
    
    test_rate_limiting()
    print()
    
    logger.info("=" * 60)
    logger.info("🏁 诊断完成！")
    
    # 提供建议
    logger.info("💡 建议:")
    logger.info("1. 如果网络连接失败，请检查网络和代理设置")
    logger.info("2. 如果API配置问题，请检查.env文件中的OPENAI_API_KEY")
    logger.info("3. 如果单个请求失败，可能是API密钥或权限问题")
    logger.info("4. 如果并发请求失败，考虑降低并发数或增加延迟")
    logger.info("5. 如果速率限制问题，请在代码中增加请求间隔")

if __name__ == "__main__":
    main() 