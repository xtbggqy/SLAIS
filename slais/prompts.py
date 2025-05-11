"""
提示词模板集合

本模块包含所有用于与LLM交互的提示词模板。
将提示词与代理逻辑分离有助于更好地管理和优化提示词。
"""

# 方法学分析提示词
METHODOLOGY_ANALYSIS_PROMPT = """分析以下研究方法：
{content}

按JSON格式返回：
- 方法类型 (实验/模拟/理论)
- 关键技术
- 创新方法"""

# 创新点提取提示词
INNOVATION_EXTRACTION_PROMPT = """提取以下文献的创新点：
{content}

按JSON格式返回：
- 核心创新
- 潜在应用"""

# 问答生成提示词
QA_GENERATION_PROMPT = """基于以下内容生成30个问题和答案：
{content}

按JSON格式返回：
- 问题1
- 答案1
- 问题2
- 答案2
- 问题3
- 答案3"""
