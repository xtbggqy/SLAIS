# LLM Prompt Templates

METHODOLOGY_ANALYSIS_PROMPT = """
请分析以下文献内容，并以JSON格式返回对研究方法的详细评估。
JSON应包含以下键：
- "method_type": (例如, "实验研究", "计算模拟", "综述", "理论分析", "混合方法"等)
- "key_techniques": (列出使用的关键技术、算法或实验手段的列表)
- "data_source": (描述数据来源，例如 "公共数据集", "自行采集", "模拟生成"等)
- "sample_size_description": (如果适用，描述样本量或数据集规模)
- "method_strengths": (分析该研究方法的优点)
- "method_limitations": (分析该研究方法的潜在局限性)
- "innovative_aspects_in_method": (研究方法中的创新点)

文献内容：
{content}

请确保输出是严格的JSON格式。
"""

INNOVATION_EXTRACTION_PROMPT = """
请仔细阅读以下文献内容，并以JSON格式提取其核心创新点和潜在应用。
JSON应包含以下键：
- "core_innovations": (一个字符串列表，列出文献的主要创新贡献)
- "problem_solved": (描述文献试图解决的核心问题)
- "novelty_compared_to_existing_work": (与现有工作相比的新颖之处)
- "potential_applications": (一个字符串列表，列出这些创新的潜在应用领域或场景)
- "future_research_directions_suggested": (文献中暗示或明确提出的未来研究方向)

文献内容：
{content}

请确保输出是严格的JSON格式。
"""

QA_GENERATION_PROMPT = """
请根据以下文献内容，生成10个高质量的问答对，涵盖文献的核心概念、关键发现和重要结论。
请以JSON格式返回结果，格式如下：
{{  // 转义的左花括号
  "qa_pairs": [
    {{  // 转义的左花括号
      "question": "问题1文本",
      "answer": "答案1文本"
    }}, // 转义的右花括号
    {{  // 转义的左花括号
      "question": "问题2文本",
      "answer": "答案2文本"
    }}  // 转义的右花括号
    // ... 更多问答对
  ]
}}  // 转义的右花括号

文献内容：
{content}

请确保输出是严格的JSON格式，并且每个问题都有对应的答案。
"""
