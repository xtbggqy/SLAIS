#!/usr/bin/env python3
"""
配置一致性检查脚本
检查项目中的环境变量配置是否一致，发现硬编码和重复配置
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Set

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_env_var_usage():
    """检查环境变量使用情况"""
    print("🔍 1. 检查环境变量使用情况\n")
    
    # 从config.py中提取所有环境变量
    config_vars = set()
    try:
        from slais import config
        for attr_name in dir(config.settings):
            if not attr_name.startswith('_') and attr_name.isupper():
                config_vars.add(attr_name)
        print(f"✅ 在config.py中定义的环境变量: {len(config_vars)} 个")
        print(f"   {sorted(config_vars)}\n")
    except Exception as e:
        print(f"❌ 无法读取config.py: {e}\n")
        config_vars = set()
    
    # 检查项目中直接使用os.getenv的地方
    project_root = Path(__file__).parent.parent
    python_files = list(project_root.rglob("*.py"))
    
    direct_env_usage = {}
    hardcoded_values = []
    
    print("🔍 检查直接使用os.getenv的文件:")
    for py_file in python_files:
        if ".git" in str(py_file) or "__pycache__" in str(py_file):
            continue
            
        try:
            content = py_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                # 检查os.getenv使用
                if "os.getenv(" in line:
                    # 提取变量名
                    start = line.find("os.getenv(") + len("os.getenv(")
                    if start < len("os.getenv("):
                        continue
                    var_part = line[start:].split(')')[0]
                    if '"' in var_part:
                        var_name = var_part.split('"')[1]
                    elif "'" in var_part:
                        var_name = var_part.split("'")[1]
                    else:
                        continue
                    
                    file_key = str(py_file.relative_to(project_root))
                    if file_key not in direct_env_usage:
                        direct_env_usage[file_key] = []
                    direct_env_usage[file_key].append((line_num, var_name, line.strip()))
                
                # 检查硬编码的API密钥或URL
                if any(pattern in line for pattern in ["sk-", "https://api.", "https://dashscope"]):
                    if not line.strip().startswith('#') and 'print(' not in line and 'logger' not in line:
                        hardcoded_values.append((str(py_file.relative_to(project_root)), line_num, line.strip()))
                        
        except Exception as e:
            print(f"   ⚠️ 无法读取文件 {py_file}: {e}")
    
    if direct_env_usage:
        print(f"\n📋 发现 {len(direct_env_usage)} 个文件直接使用 os.getenv:")
        for file_path, usages in direct_env_usage.items():
            print(f"\n   📄 {file_path}:")
            for line_num, var_name, line in usages:
                in_config = var_name in config_vars
                status = "✅" if in_config else "❌"
                print(f"      {status} 第{line_num}行: {var_name}")
                if not in_config:
                    print(f"         ⚠️ 变量 {var_name} 未在config.py中定义")
                if len(line) < 100:
                    print(f"         💡 代码: {line}")
    else:
        print("✅ 未发现直接使用os.getenv的情况")
    
    return direct_env_usage, hardcoded_values

def check_config_inconsistencies():
    """检查配置不一致的地方"""
    print("\n🔍 2. 检查配置不一致的地方\n")
    
    # 检查mineru_api/pdf_converter.py中的配置
    mineru_config_file = Path(__file__).parent.parent / "mineru_api" / "pdf_converter.py"
    
    issues = []
    
    if mineru_config_file.exists():
        print("📄 检查 mineru_api/pdf_converter.py:")
        content = mineru_config_file.read_text(encoding='utf-8')
        
        # 检查是否使用了不同的环境变量名
        if "MINERU_API_TOKEN" in content:
            issues.append("❌ mineru_api/pdf_converter.py 使用 MINERU_API_TOKEN，但主配置使用 MINERU_API_KEY")
        
        if "MINERU_BASE_URL" in content:
            issues.append("❌ mineru_api/pdf_converter.py 使用 MINERU_BASE_URL，但主配置使用 MINERU_API_BASE_URL")
            
        if not issues:
            print("   ✅ 变量名称一致")
        else:
            for issue in issues:
                print(f"   {issue}")
    
    return issues

def check_env_var_format():
    """检查当前环境变量格式"""
    print("\n🔍 3. 检查当前环境变量格式\n")
    
    important_vars = [
        "OPENAI_API_KEY",
        "OPENAI_API_BASE_URL", 
        "OPENAI_API_MODEL",
        "DASHSCOPE_API_KEY",
        "MINERU_API_KEY",
        "IMAGE_LLM_API_KEY"
    ]
    
    format_issues = []
    
    for var_name in important_vars:
        value = os.getenv(var_name)
        if value:
            print(f"📋 {var_name}:")
            print(f"   原始值: {repr(value)}")
            print(f"   长度: {len(value)}")
            
            # 检查格式问题
            if "#" in value:
                format_issues.append(f"{var_name} 包含注释符号")
                cleaned = value.split('#')[0].strip().strip('"\'')
                print(f"   ❌ 包含注释，建议清理为: {repr(cleaned)}")
            elif value.startswith('"') and not value.endswith('"'):
                format_issues.append(f"{var_name} 引号不匹配")
                print(f"   ❌ 引号不匹配")
            elif any(char in value for char in ['\n', '\r', '\t']):
                format_issues.append(f"{var_name} 包含不可见字符")
                print(f"   ❌ 包含不可见字符")
            else:
                print(f"   ✅ 格式正常")
        else:
            print(f"📋 {var_name}: 未设置")
        print()
    
    return format_issues

def suggest_fixes(direct_usage, inconsistencies, format_issues):
    """提供修复建议"""
    print("💡 修复建议:\n")
    
    if format_issues:
        print("🔧 1. 环境变量格式问题:")
        print("   立即修复环境变量格式，运行:")
        print("   python tests/debug_env_vars.py")
        print()
    
    if inconsistencies:
        print("🔧 2. 配置不一致问题:")
        print("   修复mineru_api模块中的变量名:")
        print("   - 将 MINERU_API_TOKEN 改为 MINERU_API_KEY")
        print("   - 将 MINERU_BASE_URL 改为 MINERU_API_BASE_URL")
        print("   - 或者统一使用 slais.config 模块")
        print()
    
    if direct_usage:
        print("🔧 3. 直接使用os.getenv的问题:")
        print("   建议统一使用 slais.config 模块获取配置:")
        print("   - 替换 os.getenv() 为 config.settings.XXX")
        print("   - 确保所有环境变量都在config.py中定义")
        print()
    
    print("🎯 优先修复顺序:")
    print("   1. 环境变量格式问题 (最紧急)")
    print("   2. 配置不一致问题")
    print("   3. 统一配置管理")

def create_fix_script():
    """创建修复脚本"""
    fix_script = """#!/usr/bin/env python3
# 快速修复环境变量格式问题的脚本

import os

# 清理环境变量中的注释
def clean_env_var(var_name):
    value = os.getenv(var_name)
    if value and '#' in value:
        cleaned = value.split('#')[0].strip().strip('\"\'')
        print(f"清理 {var_name}: {repr(value)} -> {repr(cleaned)}")
        os.environ[var_name] = cleaned
    return value

# 清理主要的环境变量
vars_to_clean = [
    "OPENAI_API_KEY",
    "OPENAI_API_BASE_URL", 
    "OPENAI_API_MODEL",
    "DASHSCOPE_API_KEY",
    "MINERU_API_KEY"
]

for var in vars_to_clean:
    clean_env_var(var)

print("环境变量清理完成，请重新运行测试")
"""
    
    script_path = Path(__file__).parent / "fix_env_vars.py"
    script_path.write_text(fix_script)
    print(f"\n✅ 已创建修复脚本: {script_path}")
    print("   运行: python tests/fix_env_vars.py")

def main():
    """主函数"""
    print("🚀 开始配置一致性检查...\n")
    
    # 运行所有检查
    direct_usage, hardcoded = check_env_var_usage()
    inconsistencies = check_config_inconsistencies()
    format_issues = check_env_var_format()
    
    # 汇总结果
    print("📊 检查结果汇总:")
    print(f"   - 直接使用os.getenv的文件: {len(direct_usage)}")
    print(f"   - 配置不一致问题: {len(inconsistencies)}")
    print(f"   - 环境变量格式问题: {len(format_issues)}")
    print(f"   - 发现硬编码值: {len(hardcoded)}")
    print()
    
    # 提供修复建议
    suggest_fixes(direct_usage, inconsistencies, format_issues)
    
    # 创建修复脚本
    if format_issues:
        create_fix_script()

if __name__ == "__main__":
    main() 