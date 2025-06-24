#!/usr/bin/env python3
"""
快速LLM连接测试
简单快速的API连接测试
"""

import os
import sys
import time
import requests
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_basic_connection():
    """基本连接测试"""
    print("🔍 快速连接测试开始...")
    
    # 1. 检查环境变量
    print("\n1. 检查环境变量:")
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    api_model = os.getenv("OPENAI_API_MODEL", "qwen-turbo")
    
    if api_key:
        print(f"✅ API密钥: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else '*'}")
    else:
        print("❌ API密钥未设置")
        return
        
    print(f"✅ API端点: {api_base}")
    print(f"✅ 模型: {api_model}")
    
    # 2. 测试网络连接
    print("\n2. 测试网络连接:")
    try:
        response = requests.get("https://dashscope.aliyuncs.com", timeout=10)
        print(f"✅ 阿里云DashScope可访问 - 状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 网络连接失败: {e}")
        return
    
    # 3. 测试API调用
    print("\n3. 测试API调用:")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": api_model,
        "messages": [
            {"role": "user", "content": "请回答：测试"}
        ],
        "temperature": 0.1,
        "max_tokens": 50
    }
    
    try:
        print("📡 发送测试请求...")
        start_time = time.time()
        
        response = requests.post(
            f"{api_base}/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        end_time = time.time()
        
        print(f"⏱️ 响应时间: {end_time - start_time:.2f}秒")
        print(f"📊 状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                print(f"✅ API调用成功!")
                print(f"📝 响应内容: {content}")
            else:
                print(f"❌ 响应格式异常: {result}")
        else:
            print(f"❌ API调用失败")
            print(f"🔍 响应内容: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接错误: {e}")
    except Exception as e:
        print(f"❌ 其他错误: {e}")

if __name__ == "__main__":
    test_basic_connection()
    print("\n💡 如果测试失败，请检查:")
    print("1. 网络连接是否正常")
    print("2. .env文件中的OPENAI_API_KEY是否正确")
    print("3. 是否有代理或防火墙限制")
    print("4. API账户是否有足够配额")