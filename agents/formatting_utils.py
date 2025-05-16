"""
格式化工具模块 - 用于美化和规范化不同类型的输出
"""

import re
import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

from slais.utils.logging_utils import logger


def _unwrap_markdown_block(text: str) -> str:
    """
    Helper function to remove "```markdown" and "```" wrappers from a string.
    """
    text = text.strip()
    if text.startswith("```markdown") and text.endswith("```"):
        # Remove the first line (```markdown)
        # and the last line (```) 
        lines = text.splitlines()
        if len(lines) > 1:
            # Handle potential empty lines after ```markdown or before ```
            start_index = 0
            if lines[start_index].strip().startswith("```markdown"):
                start_index += 1
            
            end_index = len(lines) - 1
            if lines[end_index].strip() == "```":
                end_index -= 1
            
            # Ensure valid range and join
            if end_index >= start_index:
                return "\n".join(lines[start_index : end_index+1]).strip()
            else: # Only fences were present or became empty after stripping
                return "" 
    return text


def format_mermaid_code(mermaid_text: str) -> str:
    """
    格式化Mermaid代码，确保它有正确的包装和语法。
    
    Args:
        mermaid_text: 可能包含Mermaid代码的文本
        
    Returns:
        格式化好的Mermaid代码块
    """
    # 首先检查输入是否已经是格式良好的Mermaid代码块
    if "```mermaid" in mermaid_text and "```" in mermaid_text[mermaid_text.find("```mermaid")+10:]:
        # 已经是格式良好的代码块，但可能需要清理
        return clean_mermaid_code(mermaid_text)
    
    # 尝试提取可能是Mermaid代码但格式不正确的内容
    graph_match = re.search(r'graph\s+(TD|LR|RL|BT|TB)[\s\S]+?(\n\n|\Z)', mermaid_text, re.MULTILINE)
    
    if graph_match:
        # 找到了graph开头的代码，提取并包装
        code = graph_match.group(0).strip()
        return f"```mermaid\n{code}\n```"
    
    # 检查是否包含节点和连接符号但没有正确的图类型声明
    if "-->" in mermaid_text and ("[" in mermaid_text or "(" in mermaid_text):
        # 似乎是Mermaid代码但缺少图类型声明，添加默认的TD
        cleaned_code = re.sub(r'^\s*```.*?\n', '', mermaid_text, flags=re.MULTILINE)
        cleaned_code = re.sub(r'\n\s*```\s*$', '', cleaned_code)
        cleaned_code = cleaned_code.strip()
        
        if not cleaned_code.startswith("graph"):
            cleaned_code = "graph TD\n" + cleaned_code
        
        return f"```mermaid\n{cleaned_code}\n```"
    
    # 如果不能确定内容格式，返回默认的错误脑图
    return generate_default_mindmap("无法识别或格式化Mermaid代码")


def clean_mermaid_code(mermaid_text: str) -> str:
    """清理并修复可能存在问题的Mermaid代码。"""
    # 提取Mermaid代码块内容
    code_match = re.search(r'```mermaid\s*([\s\S]+?)\s*```', mermaid_text)
    
    if not code_match:
        return mermaid_text  # 没有找到代码块，返回原文
    
    code = code_match.group(1).strip()
    
    # 检查并修复常见问题
    
    # 1. 确保有图类型声明
    if not re.search(r'^graph\s+(TD|LR|RL|BT|TB)', code, re.MULTILINE):
        code = "graph TD\n" + code
    
    # 2. 修复缺少节点定义的边
    lines = code.split("\n")
    fixed_lines = []
    
    for line in lines:
        if "-->" in line and not re.search(r'\w+\s*(\[.*?\]|\(.*?\)|\{.*?\}|\[.*?\])', line):
            # 这是一个没有正确定义节点的边，尝试修复
            parts = line.split("-->")
            if len(parts) >= 2:
                source = parts[0].strip()
                target = parts[1].strip()
                if source and target:
                    # 为未定义的节点添加默认方括号
                    if not re.search(r'\[|\(|\{', source):
                        source = f"{source}[{source}]"
                    if not re.search(r'\[|\(|\{', target):
                        target = f"{target}[{target}]"
                    line = f"    {source} --> {target}"
        
        fixed_lines.append(line)
    
    code = "\n".join(fixed_lines)
    
    # 返回修复后的代码
    return f"```mermaid\n{code}\n```"


def generate_default_mindmap(error_message: str) -> str:
    """生成一个默认的脑图，显示错误信息。"""
    return f"""```mermaid
graph TD
    A[文献分析] --> B[生成失败]
    B --> C["{error_message}"]
    C --> D1[可能原因1: 输入文本过长]
    C --> D2[可能原因2: 格式解析错误]
    C --> D3[可能原因3: LLM响应不规范]
```
"""


def format_qa_pairs_for_markdown(qa_pairs: List[Dict[str, str]]) -> str:
    """
    将问答对格式化为美观的Markdown内容。
    Args:
        qa_pairs: 问答对列表，每个元素是包含'question'和'answer'键的字典
    Returns:
        格式化的Markdown文本
    """
    if not qa_pairs:
        return "未能生成问答对。"

    md_content = []
    for i, pair in enumerate(qa_pairs):
        question = str(pair.get('question', 'N/A')).strip()
        answer = str(pair.get('answer', 'N/A')).strip()
        # 规避HTML嵌套导致的渲染异常，避免多层<details>嵌套
        md_content.append(f"<details>")
        md_content.append(f"<summary><b>问题 {i+1}：</b>{question}</summary>")
        md_content.append("")
        # 用Markdown代码块包裹答案，避免长文本或特殊字符导致的渲染错乱
        md_content.append(f"**回答：**\n\n```\n{answer}\n```")
        md_content.append("</details>")
        md_content.append("")

    return "\n".join(md_content)


def format_methodology_analysis(methodology: Union[str, Dict[str, Any]]) -> str:
    """
    格式化方法学分析内容为美观的Markdown。
    
    Args:
        methodology: 方法学分析结果，字符串或字典
        
    Returns:
        格式化的Markdown文本
    """
    if not methodology:
        return "未进行方法学分析或无结果。"
    
    if isinstance(methodology, str):
        # 如果是字符串，清理可能存在的 "```markdown" 包裹
        return _unwrap_markdown_block(methodology)
    
    # 格式化字典数据
    # 移除原有的 "## 方法学分析" 标题，因为 generate_enhanced_report 会添加主标题
    md_content = [] 
    
    # 添加方法类型
    md_content.append("### 方法类型")
    md_content.append(methodology.get('method_type', 'N/A'))
    md_content.append("")
    
    # 添加关键技术
    md_content.append("### 关键技术")
    key_techniques = methodology.get('key_techniques', [])
    if isinstance(key_techniques, list) and key_techniques:
        for tech in key_techniques:
            md_content.append(f"- {tech}")
    else:
        md_content.append(f"- {key_techniques if key_techniques else 'N/A'}")
    md_content.append("")
    
    # 添加数据来源
    md_content.append("### 数据来源")
    md_content.append(methodology.get('data_source', 'N/A'))
    md_content.append("")
    
    # 添加样本量描述
    md_content.append("### 样本量描述")
    md_content.append(methodology.get('sample_size_description', 'N/A'))
    md_content.append("")
    
    # 添加方法优点
    md_content.append("### 方法优点")
    strengths = methodology.get('method_strengths', [])
    if isinstance(strengths, list) and strengths:
        for strength in strengths:
            md_content.append(f"- {strength}")
    else:
        md_content.append(f"- {strengths if strengths else 'N/A'}")
    md_content.append("")
    
    # 添加方法局限性
    md_content.append("### 方法局限性")
    limitations = methodology.get('method_limitations', [])
    if isinstance(limitations, list) and limitations:
        for limitation in limitations:
            md_content.append(f"- {limitation}")
    else:
        md_content.append(f"- {limitations if limitations else 'N/A'}")
    md_content.append("")
    
    # 添加方法创新点
    md_content.append("### 方法创新点")
    innovations = methodology.get('innovative_aspects_in_method', [])
    if isinstance(innovations, list) and innovations:
        for innovation in innovations:
            md_content.append(f"- {innovation}")
    else:
        md_content.append(f"- {innovations if innovations else 'N/A'}")
    
    return "\n".join(md_content)


def generate_enhanced_report(results: dict, pdf_filename_stem: str) -> str:
    """
    生成一个美观的增强版Markdown报告。
    """
    # 顶部标题和描述
    md_content = [
        f"# 文献分析报告: {pdf_filename_stem}",
        "",
        "<div align='center'><img src='logo.svg' height='120' alt='SLAIS Logo'></div>",
        "",
        "---",
        "",
        "## 目录",
        "<ul>",
        "<li><a href='#1-文献元数据'>1. 文献元数据</a></li>",
        "<li><a href='#1b-图片内容分析'>1b. 图片内容分析</a></li>",
        "<li><a href='#2-方法学分析'>2. 方法学分析</a></li>",
        "<li><a href='#3-创新点提取'>3. 创新点提取</a></li>",
        "<li><a href='#4-问答对'>4. 问答对</a></li>",
        "<li><a href='#5-文献故事'>5. 文献故事</a></li>",
        "<li><a href='#6-文献逻辑脑图'>6. 文献逻辑脑图</a></li>",
        "<li><a href='#7-参考文献信息'>7. 参考文献信息</a></li>",
        "<li><a href='#8-相关文献信息'>8. 相关文献信息</a></li>",
        "</ul>",
        "",
        "---",
        ""
    ]

    # 1. 元数据部分
    metadata = results.get("metadata", {})
    md_content.append("## 1. 文献元数据")
    md_content.append("<details open>")
    md_content.append("<summary>点击展开/折叠</summary>")
    md_content.append("")
    if metadata:
        pubmed_info = metadata.get("pubmed_info", {})
        s2_info = metadata.get("s2_info", {})

        title = pubmed_info.get('title') or s2_info.get('title', 'N/A')
        authors = pubmed_info.get('authors') or ('; '.join([a.get('name', '') for a in s2_info.get('authors', [])]) if s2_info.get('authors') else 'N/A')
        doi = s2_info.get('externalIds', {}).get('DOI') or 'N/A'
        pub_date = pubmed_info.get('publication_date') or str(s2_info.get('year', 'N/A'))
        journal = pubmed_info.get('journal') or s2_info.get('venue', 'N/A')
        
        md_content.append("<table>")
        md_content.append("  <tr><th colspan='2' style='text-align:center;'>文献基本信息</th></tr>")
        md_content.append(f"  <tr><td><b>标题</b></td><td>{title}</td></tr>")
        md_content.append(f"  <tr><td><b>作者</b></td><td>{authors}</td></tr>")
        md_content.append(f"  <tr><td><b>DOI</b></td><td>{doi}</td></tr>")
        md_content.append(f"  <tr><td><b>发表日期</b></td><td>{pub_date}</td></tr>")
        md_content.append(f"  <tr><td><b>期刊/来源</b></td><td>{journal}</td></tr>")
        md_content.append("</table>")
        md_content.append("")
        
        if s2_info:
            s2_abstract = s2_info.get('abstract')
            citation_count = s2_info.get('citationCount', 'N/A')
            
            md_content.append("<details>")
            md_content.append("<summary><b>Semantic Scholar 信息</b></summary>")
            md_content.append("")
            md_content.append("<table>")
            md_content.append(f"  <tr><td><b>Paper ID</b></td><td>{s2_info.get('paperId', 'N/A')}</td></tr>")
            md_content.append(f"  <tr><td><b>被引次数</b></td><td>{citation_count}</td></tr>")
            if s2_abstract:
                md_content.append(f"  <tr><td><b>摘要</b></td><td>{s2_abstract[:300] + '...' if len(s2_abstract) > 300 else s2_abstract}</td></tr>")
            md_content.append("</table>")
            md_content.append("</details>")
            md_content.append("")

        if pubmed_info:
            pubmed_abstract = pubmed_info.get('abstract')
            
            md_content.append("<details>")
            md_content.append("<summary><b>PubMed 信息</b></summary>")
            md_content.append("")
            md_content.append("<table>")
            md_content.append(f"  <tr><td><b>PMID</b></td><td>{pubmed_info.get('pmid', 'N/A')}</td></tr>")
            if pubmed_abstract and pubmed_abstract != '未找到摘要':
                md_content.append(f"  <tr><td><b>摘要</b></td><td>{pubmed_abstract[:300] + '...' if len(pubmed_abstract) > 300 else pubmed_abstract}</td></tr>")
            md_content.append("</table>")
            md_content.append("</details>")
            md_content.append("")
    else:
        md_content.append("<p>未找到元数据信息。</p>")
    
    md_content.append("</details>")
    md_content.append("")
    md_content.append("\n---\n")

    # 新增：图片内容分析部分
    image_analysis = results.get("image_analysis", [])
    image_paths = results.get("image_paths", [])
    md_content.append("## 1b. 图片内容分析")
    md_content.append("<details open>")
    md_content.append("<summary>点击展开/折叠</summary>")
    md_content.append("")
    if image_analysis and isinstance(image_analysis, list):
        for idx, img in enumerate(image_analysis):
            img_path = img.get("image_path", "")
            desc = img.get("description", "")
            rel_img_path = img_path
            if image_paths:
                # 统一路径分隔符为正斜杠，兼容Markdown和Web
                rel_img_path = img_path.replace("\\", "/")
                for p in image_paths:
                    # 也将 image_paths 中的路径分隔符统一
                    p_norm = p.replace("\\", "/")
                    if p_norm in rel_img_path or Path(rel_img_path).name == Path(p_norm).name:
                        rel_img_path = p_norm
                        break
            # 统一图片路径为正斜杠
            rel_img_path = rel_img_path.replace("\\", "/")
            md_content.append(f"<details>")
            md_content.append(f"<summary><b>图片 {idx+1}</b>: <code>{rel_img_path}</code></summary>")
            md_content.append("")
            md_content.append(f"![图片{idx+1}]({rel_img_path})")
            md_content.append("")
            md_content.append(f"**结构化描述：**\n{desc}")
            md_content.append("</details>")
            md_content.append("")
    else:
        md_content.append("<p>未检测到图片或图片内容分析结果。</p>")
    md_content.append("</details>")
    md_content.append("")
    md_content.append("\n---\n")

    # 2. 方法学分析
    methodology = results.get("methodology_analysis", "")
    md_content.append("## 2. 方法学分析")
    md_content.append("<details open>")
    md_content.append("<summary>点击展开/折叠</summary>")
    md_content.append("")
    if methodology:
        md_content.append(_unwrap_markdown_block(str(methodology)))
    else:
        md_content.append("<p>未进行方法学分析或无结果。</p>")
    md_content.append("</details>")
    md_content.append("")
    md_content.append("\n---\n")

    # 3. 创新点提取
    innovations = results.get("innovation_extraction", "")
    md_content.append("## 3. 创新点提取")
    md_content.append("<details open>")
    md_content.append("<summary>点击展开/折叠</summary>")
    md_content.append("")
    if innovations:
        if isinstance(innovations, str):
            md_content.append(_unwrap_markdown_block(innovations))
        else:
            md_content.append("### 核心创新点")
            core_innovations = innovations.get('core_innovations', [])
            if core_innovations:
                if isinstance(core_innovations, list):
                    for inn in core_innovations:
                        md_content.append(f"- {inn}")
                else:
                    md_content.append(f"- {core_innovations}")
            else:
                md_content.append("- 未提取到核心创新点")
            md_content.append("")
            md_content.append("### 解决的问题")
            problem = innovations.get('problem_solved', 'N/A')
            md_content.append(f"{problem}")
            md_content.append("")
            md_content.append("### 与现有工作相比的新颖性")
            novelty = innovations.get('novelty_compared_to_existing_work', 'N/A')
            md_content.append(f"{novelty}")
            md_content.append("")
            md_content.append("### 潜在应用")
            potential_apps = innovations.get('potential_applications', [])
            if potential_apps:
                if isinstance(potential_apps, list):
                    for app in potential_apps:
                        md_content.append(f"- {app}")
                else:
                    md_content.append(f"- {potential_apps}")
            else:
                md_content.append("- 未提取到潜在应用")
            md_content.append("")
            md_content.append("### 未来研究方向")
            future_dirs = innovations.get('future_research_directions_suggested', [])
            if future_dirs:
                if isinstance(future_dirs, list):
                    for fut_dir in future_dirs:
                        md_content.append(f"- {fut_dir}")
                else:
                    md_content.append(f"- {future_dirs}")
            else:
                md_content.append("- 未提取到未来研究方向")
    else:
        md_content.append("<p>未进行创新点提取或无结果。</p>")
    md_content.append("</details>")
    md_content.append("")
    md_content.append("\n---\n")

    # 4. 问答对
    qa_pairs = results.get("qa_pairs", [])
    md_content.append("## 4. 问答对")
    md_content.append("<details open>")
    md_content.append("<summary>点击展开/折叠</summary>")
    md_content.append("")
    if qa_pairs and isinstance(qa_pairs, list):
        md_content.append(format_qa_pairs_for_markdown(qa_pairs))
    else:
        md_content.append("<p>未能生成问答对。</p>")
    md_content.append("</details>")
    md_content.append("")
    md_content.append("\n---\n")

    # 5. 故事讲述
    story = results.get("story", "")
    md_content.append("## 5. 文献故事")
    md_content.append("<details open>")
    md_content.append("<summary>点击展开/折叠</summary>")
    md_content.append("")
    if story:
        md_content.append(_unwrap_markdown_block(story))
    else:
        md_content.append("<p>未能生成文献故事。</p>")
    md_content.append("</details>")
    md_content.append("")
    md_content.append("\n---\n")

    # 6. 脑图
    mindmap = results.get("mindmap", "")
    md_content.append("## 6. 文献逻辑脑图")
    md_content.append("<details open>")
    md_content.append("<summary>点击展开/折叠</summary>")
    md_content.append("")
    if mindmap:
        formatted_mindmap = format_mermaid_code(mindmap)
        md_content.append(formatted_mindmap)
    else:
        md_content.append(generate_default_mindmap("未能生成脑图"))
    md_content.append("</details>")
    md_content.append("")

    # 7. 参考文献信息
    references = results.get("references_data", {}).get("full_references_details", [])
    md_content.append("## 7. 参考文献信息")
    md_content.append("<details open>")
    md_content.append("<summary>点击展开/折叠</summary>")
    md_content.append("")
    if references and isinstance(references, list):
        # 使用HTML表格，设置深色/浅色主题自适应样式，保证可读性
        md_content.append("""
<style>
.slais-table th, .slais-table td {
  padding: 10px 8px;
  border: 1px solid #444;
  font-size: 15px;
  text-align: left;
  min-width: 80px;
}
.slais-table th {
  background: #222;
  color: #fff;
  font-weight: bold;
}
.slais-table td {
  background: #181818;
  color: #eee;
}
@media (prefers-color-scheme: light) {
  .slais-table th { background: #f5f5f5; color: #222; }
  .slais-table td { background: #fff; color: #222; }
}
</style>
<table class="slais-table">
  <thead>
    <tr>
      <th>DOI</th>
      <th>标题</th>
      <th>作者</th>
      <th>期刊</th>
      <th>发表日期</th>
      <th>PMID</th>
    </tr>
  </thead>
  <tbody>
""")
        for ref in references:
            # 兼容 authors_str 为空但 authors 为列表的情况
            authors_str = ref.get('authors_str')
            if not authors_str and isinstance(ref.get('authors'), list):
                authors_str = "; ".join(ref.get('authors'))
            pub_date = ref.get('pub_date') or ref.get('publication_date') or ""
            md_content.append(
                f"<tr>"
                f"<td>{ref.get('doi','')}</td>"
                f"<td>{ref.get('title','')}</td>"
                f"<td>{authors_str or ''}</td>"
                f"<td>{ref.get('journal','')}</td>"
                f"<td>{pub_date}</td>"
                f"<td>{ref.get('pmid','')}</td>"
                f"</tr>"
            )
        md_content.append("</tbody></table>")
    else:
        md_content.append("无参考文献信息。")
    md_content.append("</details>")
    md_content.append("")
    md_content.append("\n---\n")

    # 8. 相关文献信息
    related_articles = results.get("related_articles_pubmed", [])
    md_content.append("## 8. 相关文献信息")
    md_content.append("<details open>")
    md_content.append("<summary>点击展开/折叠</summary>")
    md_content.append("")
    if related_articles and isinstance(related_articles, list):
        md_content.append("""
<style>
.slais-table th, .slais-table td {
  padding: 10px 8px;
  border: 1px solid #444;
  font-size: 15px;
  text-align: left;
  min-width: 80px;
}
.slais-table th {
  background: #222;
  color: #fff;
  font-weight: bold;
}
.slais-table td {
  background: #181818;
  color: #eee;
}
@media (prefers-color-scheme: light) {
  .slais-table th { background: #f5f5f5; color: #222; }
  .slais-table td { background: #fff; color: #222; }
}
</style>
<table class="slais-table">
  <thead>
    <tr>
      <th>PMID</th>
      <th>标题</th>
      <th>作者</th>
      <th>期刊</th>
      <th>发表日期</th>
      <th>DOI</th>
    </tr>
  </thead>
  <tbody>
""")
        for art in related_articles:
            authors_str = art.get('authors_str')
            if not authors_str and isinstance(art.get('authors'), list):
                authors_str = "; ".join(art.get('authors'))
            pub_date = art.get('pub_date') or art.get('publication_date') or ""
            md_content.append(
                f"<tr>"
                f"<td>{art.get('pmid','')}</td>"
                f"<td>{art.get('title','')}</td>"
                f"<td>{authors_str or ''}</td>"
                f"<td>{art.get('journal','')}</td>"
                f"<td>{pub_date}</td>"
                f"<td>{art.get('doi','')}</td>"
                f"</tr>"
            )
        md_content.append("</tbody></table>")
    else:
        md_content.append("无相关文献信息。")
    md_content.append("</details>")
    md_content.append("")
    md_content.append("\n---\n")

    # 页脚与自定义CSS
    md_content.append("<hr>")
    md_content.append("<footer>")
    md_content.append(f"<p><b>报告生成时间:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
    md_content.append("<p><i>此报告由 SLAIS (Scientific Literature AI Insight System) 自动生成</i></p>")
    md_content.append("""
<style>
  body { 
    font-family: Arial, sans-serif; 
    line-height: 1.6;
    color: #333;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
  }
  h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
  h2 { color: #2980b9; margin-top: 30px; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }
  h3 { color: #3498db; }
  details { margin-bottom: 20px; padding: 10px; border: 1px solid #e0e0e0; border-radius: 5px; }
  summary { cursor: pointer; font-weight: bold; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
  th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e0e0e0; }
  th { background-color: #f5f5f5; }
  .qa-container details { background-color: #f9f9f9; margin-bottom: 10px; }
  .qa-container summary { background-color: #f1f1f1; padding: 10px; }
  code { background-color: #f5f5f5; padding: 2px 5px; border-radius: 3px; }
  pre { background-color: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; }
  hr { border: 0; border-top: 1px solid #e0e0e0; margin: 30px 0; }
  footer { text-align: center; margin-top: 50px; font-size: 0.9em; color: #7f8c8d; }
  img { transition: box-shadow 0.2s; }
  img:hover { box-shadow: 0 0 8px #2980b9; }
</style>
""")
    md_content.append("</footer>")

    return "\n".join(md_content)
