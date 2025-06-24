#!/usr/bin/env python3
"""
环境变量诊断脚本
检查环境变量中是否包含注释文本导致连接失败
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def diagnose_env_vars():
    """诊断环境变量"""
    print("🔍 环境变量诊断开始...\n")
    
    # 需要检查的环境变量
    env_vars_to_check = [
        "OPENAI_API_KEY",
        "OPENAI_API_BASE_URL", 
        "OPENAI_API_MODEL",
        "DASHSCOPE_API_KEY"
    ]
    
    print("1. 检查环境变量原始值:")
    problems_found = []
    
    for var_name in env_vars_to_check:
        raw_value = os.getenv(var_name)
        if raw_value:
            print(f"\n{var_name}:")
            print(f"  原始值: {repr(raw_value)}")
            print(f"  长度: {len(raw_value)}")
            
            # 检查是否包含注释符号
            if "#" in raw_value:
                problems_found.append(f"{var_name} 包含注释符号 '#'")
                print(f"  ❌ 问题: 包含注释符号 '#'")
                
                # 尝试清理值
                cleaned_value = raw_value.split('#')[0].strip().strip('"\'')
                print(f"  🔧 建议清理后的值: {repr(cleaned_value)}")
            
            # 检查是否有引号问题
            if raw_value.startswith('"') and not raw_value.endswith('"'):
                problems_found.append(f"{var_name} 引号不匹配")
                print(f"  ❌ 问题: 引号不匹配")
            
            # 检查是否有其他特殊字符
            if any(char in raw_value for char in ['\n', '\r', '\t']):
                problems_found.append(f"{var_name} 包含换行符或制表符")
                print(f"  ❌ 问题: 包含不可见字符")
                
        else:
            print(f"\n{var_name}: 未设置")
    
    print(f"\n2. 问题汇总:")
    if problems_found:
        print("  发现以下问题:")
        for problem in problems_found:
            print(f"  - {problem}")
    else:
        print("  ✅ 未发现格式问题")
    
    return problems_found

def suggest_fix():
    """提供修复建议"""
    print("\n💡 修复建议:")
    
    print("\n选项1: 创建正确的.env文件")
    print("在项目根目录创建 .env 文件，内容如下:")
    print("```")
    print("# API密钥配置")
    print("OPENAI_API_KEY=sk-你的实际API密钥")
    print("OPENAI_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1")
    print("OPENAI_API_MODEL=qwen-turbo")
    print("```")
    
    print("\n选项2: 设置系统环境变量")
    print("在Windows PowerShell中运行:")
    print("```powershell")
    print('$env:OPENAI_API_KEY="sk-你的实际API密钥"')
    print('$env:OPENAI_API_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"')
    print('$env:OPENAI_API_MODEL="qwen-turbo"')
    print("```")
    
    print("\n选项3: 检查当前设置的环境变量")
    print("在PowerShell中运行以下命令查看当前值:")
    print("```powershell")
    print("echo $env:OPENAI_API_KEY")
    print("echo $env:OPENAI_API_BASE_URL")
    print("echo $env:OPENAI_API_MODEL")
    print("```")

def create_correct_env_file():
    """创建正确的.env文件"""
    print("\n🛠️ 是否要创建正确的.env文件模板？")
    
    env_content = """# SLAIS 配置文件
# 请填写你的实际API密钥

# 阿里云DashScope API配置 (推荐)
OPENAI_API_KEY=sk-your-dashscope-api-key-here
OPENAI_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_API_MODEL=qwen-turbo

# 图像模型配置 (使用相同密钥)
IMAGE_LLM_API_KEY=sk-your-dashscope-api-key-here
IMAGE_LLM_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
IMAGE_LLM_API_MODEL=qwen-vl-plus

# 其他配置
NCBI_EMAIL=your-email@example.com
ARTICLE_DOI=10.1126/science.aao4593
MAX_QUESTIONS_TO_GENERATE=25

# 注意事项:
# 1. 不要在值的末尾添加注释
# 2. 不要使用多余的引号
# 3. API密钥通常以 sk- 开头
# 4. 确保没有额外的空格或换行符
"""
    
    project_root = Path(__file__).parent.parent
    env_file_path = project_root / ".env"
    
    try:
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        print(f"✅ 已创建 .env 文件模板: {env_file_path}")
        print("📝 请编辑该文件，填入你的实际API密钥")
        return True
    except Exception as e:
        print(f"❌ 创建 .env 文件失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 开始环境变量诊断...\n")
    
    # 诊断当前环境变量
    problems = diagnose_env_vars()
    
    # 提供修复建议
    suggest_fix()
    
    # 询问是否创建.env文件
    create_env = input("\n是否创建 .env 文件模板？(y/n): ")
    if create_env.lower() in ['y', 'yes', '是']:
        create_correct_env_file()
    
    print("\n📝 下一步:")
    print("1. 检查并修复环境变量设置")
    print("2. 重新运行: python tests/test_quick_connection.py")
    print("3. 确认API连接成功后，再运行主程序")

if __name__ == "__main__":
    main() 