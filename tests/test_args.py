#!/usr/bin/env python3
"""
简单的测试脚本，用于验证app.py的命令行参数处理是否正常工作
"""
import sys
import subprocess
import os

def test_help():
    """测试--help参数"""
    print("测试 --help 参数...")
    result = subprocess.run([sys.executable, "app.py", "--help"], 
                          capture_output=True, text=True, cwd=os.getcwd())
    print("返回码:", result.returncode)
    print("输出长度:", len(result.stdout))
    print("是否包含'usage':", "usage:" in result.stdout)
    print("是否包含DEBUG信息:", "DEBUG:" in result.stdout or "DEBUG:" in result.stderr)
    print("=" * 50)

def test_short_help():
    """测试-h参数"""
    print("测试 -h 参数...")
    result = subprocess.run([sys.executable, "app.py", "-h"], 
                          capture_output=True, text=True, cwd=os.getcwd())
    print("返回码:", result.returncode)
    print("输出长度:", len(result.stdout))
    print("是否包含'usage':", "usage:" in result.stdout)
    print("是否包含DEBUG信息:", "DEBUG:" in result.stdout or "DEBUG:" in result.stderr)
    print("=" * 50)

def test_invalid_arg():
    """测试无效参数"""
    print("测试无效参数 --invalid...")
    result = subprocess.run([sys.executable, "app.py", "--invalid"], 
                          capture_output=True, text=True, cwd=os.getcwd())
    print("返回码:", result.returncode)
    print("是否报错:", result.returncode != 0)
    print("错误信息包含'unrecognized':", "unrecognized" in result.stderr)
    print("=" * 50)

if __name__ == "__main__":
    print("开始测试 app.py 的命令行参数处理...")
    test_help()
    test_short_help()
    test_invalid_arg()
    print("测试完成！")
