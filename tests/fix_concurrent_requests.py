#!/usr/bin/env python3
"""
修复并发请求连接问题的解决方案
"""

import os
import sys
import time
import asyncio
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_sequential_vs_concurrent():
    """测试顺序 vs 并发请求"""
    print("🔍 测试顺序请求 vs 并发请求...")
    
    try:
        from langchain_openai import ChatOpenAI
        from slais import config
        
        # 初始化LLM客户端
        llm_params = {
            "model_name": config.settings.OPENAI_API_MODEL,
            "openai_api_key": config.settings.OPENAI_API_KEY,
            "temperature": 0.1
        }
        if config.settings.OPENAI_API_BASE_URL:
            llm_params["openai_api_base"] = config.settings.OPENAI_API_BASE_URL
            
        llm = ChatOpenAI(**llm_params)
        print(f"✅ LLM客户端初始化成功: {config.settings.OPENAI_API_MODEL}")
        
        # 准备测试提示
        test_prompts = [
            "请简单回答：什么是机器学习？",
            "请简单回答：什么是深度学习？", 
            "请简单回答：什么是人工智能？",
            "请简单回答：什么是神经网络？",
            "请简单回答：什么是算法？"
        ]
        
        # 1. 测试顺序请求
        print("\n1. 测试顺序请求:")
        start_time = time.time()
        sequential_results = []
        
        for i, prompt in enumerate(test_prompts):
            try:
                print(f"   📡 发送顺序请求 {i+1}/5...")
                response = await llm.ainvoke([{"role": "user", "content": prompt}])
                sequential_results.append(f"请求{i+1}: 成功")
                print(f"   ✅ 请求 {i+1} 成功")
                
                # 添加小延迟
                await asyncio.sleep(0.5)
                
            except Exception as e:
                sequential_results.append(f"请求{i+1}: 失败 - {e}")
                print(f"   ❌ 请求 {i+1} 失败: {e}")
        
        sequential_time = time.time() - start_time
        print(f"   ⏱️ 顺序请求总耗时: {sequential_time:.2f}秒")
        
        # 2. 测试并发请求
        print("\n2. 测试并发请求:")
        start_time = time.time()
        
        async def single_request(prompt, request_id):
            try:
                response = await llm.ainvoke([{"role": "user", "content": prompt}])
                return f"请求{request_id}: 成功"
            except Exception as e:
                return f"请求{request_id}: 失败 - {e}"
        
        # 创建并发任务
        concurrent_tasks = [
            single_request(prompt, i+1) 
            for i, prompt in enumerate(test_prompts)
        ]
        
        try:
            concurrent_results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
            concurrent_time = time.time() - start_time
            
            print(f"   ⏱️ 并发请求总耗时: {sequential_time:.2f}秒")
            
            # 分析结果
            sequential_success = sum(1 for r in sequential_results if "成功" in r)
            concurrent_success = sum(1 for r in concurrent_results if isinstance(r, str) and "成功" in r)
            
            print(f"\n📊 结果对比:")
            print(f"   顺序请求: {sequential_success}/5 成功, 耗时 {sequential_time:.2f}秒")
            print(f"   并发请求: {concurrent_success}/5 成功, 耗时 {concurrent_time:.2f}秒")
            
            if concurrent_success < sequential_success:
                print("❌ 并发请求成功率较低，建议使用顺序请求或增加延迟")
                return "建议使用顺序请求"
            else:
                print("✅ 并发请求工作正常")
                return "并发请求正常"
                
        except Exception as e:
            print(f"❌ 并发请求测试失败: {e}")
            return "并发请求失败"
            
    except Exception as e:
        print(f"❌ 测试初始化失败: {e}")
        return "测试失败"

async def test_with_delays():
    """测试带延迟的并发请求"""
    print("\n🔍 测试带延迟的并发请求...")
    
    try:
        from langchain_openai import ChatOpenAI
        from slais import config
        
        llm_params = {
            "model_name": config.settings.OPENAI_API_MODEL,
            "openai_api_key": config.settings.OPENAI_API_KEY,
            "temperature": 0.1
        }
        if config.settings.OPENAI_API_BASE_URL:
            llm_params["openai_api_base"] = config.settings.OPENAI_API_BASE_URL
            
        llm = ChatOpenAI(**llm_params)
        
        test_prompts = [
            "测试延迟请求1：请回答OK",
            "测试延迟请求2：请回答OK", 
            "测试延迟请求3：请回答OK",
            "测试延迟请求4：请回答OK",
            "测试延迟请求5：请回答OK"
        ]
        
        # 测试不同延迟间隔
        delays = [0, 0.5, 1.0, 2.0]
        
        for delay in delays:
            print(f"\n   测试延迟 {delay}秒:")
            start_time = time.time()
            
            async def delayed_request(prompt, request_id, delay_time):
                await asyncio.sleep(delay_time * request_id)  # 递增延迟
                try:
                    response = await llm.ainvoke([{"role": "user", "content": prompt}])
                    return f"成功"
                except Exception as e:
                    return f"失败: {e}"
            
            tasks = [
                delayed_request(prompt, i, delay) 
                for i, prompt in enumerate(test_prompts)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            success_count = sum(1 for r in results if isinstance(r, str) and "成功" in r)
            print(f"     结果: {success_count}/5 成功, 耗时 {end_time - start_time:.2f}秒")
            
            if success_count == 5:
                print(f"✅ 建议使用 {delay}秒 延迟间隔")
                return delay
        
        return 1.0  # 默认建议1秒延迟
        
    except Exception as e:
        print(f"❌ 延迟测试失败: {e}")
        return 1.0

def suggest_fixes():
    """提供修复建议"""
    print("\n💡 基于测试结果的修复建议:")
    print("\n1. 降低并发数:")
    print("   - 在 app.py 中分批执行LLM任务，而不是同时发起5个")
    print("   - 例如：先执行3个任务，再执行2个任务")
    
    print("\n2. 增加请求间隔:")
    print("   - 在每个LLM调用之间添加延迟")
    print("   - 建议在 base_agent.py 的 _invoke_llm_analysis 方法中添加延迟")
    
    print("\n3. 添加重试机制:")
    print("   - 对Connection error实施指数退避重试")
    print("   - 最多重试3次，每次间隔递增")
    
    print("\n4. 检查API配额:")
    print("   - 登录阿里云DashScope控制台检查API调用限制")
    print("   - 确认每分钟/每秒请求数限制")
    
    print("\n5. 使用连接池:")
    print("   - 配置HTTP连接池参数")
    print("   - 设置适当的超时时间")

async def main():
    """主函数"""
    print("🚀 开始连接问题诊断和修复测试...\n")
    
    # 运行测试
    result1 = await test_sequential_vs_concurrent()
    optimal_delay = await test_with_delays()
    
    # 提供修复建议
    suggest_fixes()
    
    print(f"\n🎯 推荐配置:")
    print(f"   - 建议延迟间隔: {optimal_delay}秒")
    print(f"   - 测试结果: {result1}")
    print("\n📝 下一步:")
    print("1. 先运行 python tests/test_quick_connection.py 确认基本连接")
    print("2. 如果基本连接正常，则实施上述并发优化建议")
    print("3. 修改代码后重新测试")

if __name__ == "__main__":
    asyncio.run(main()) 