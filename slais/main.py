import asyncio
import os
import argparse
import sys
import json
import datetime
import shutil # 用于复制目录
from pathlib import Path

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import csv # 导入 csv 模块
# 现在导入项目模块
from slais.pdf_utils import convert_pdf_to_markdown
from slais.pubmed_client import PubMedClient, ArticleDetails # 从新的 pubmed_client 模块导入
from slais.semantic_scholar_client import SemanticScholarClient # 从新的 semantic_scholar_client 模块导入
from slais import config
from slais.utils.logging_utils import logger, setup_logging # 导入logger和setup_logging
from slais.agents import PDFParsingAgent, MetadataFetchingAgent, MethodologyAnalysisAgent, InnovationExtractionAgent, QAGenerationAgent


# 导入配置
try:
    from slais.config import DEFAULT_PDF_PATH, OUTPUT_BASE_DIR, ARTICLE_DOI, NCBI_EMAIL  # 导入 NCBI_EMAIL
except ImportError:
    # 如果config.py不存在，使用默认值
    DEFAULT_PDF_PATH = "pdfs/example.pdf"
    OUTPUT_BASE_DIR = "output"
    ARTICLE_DOI = None
    NCBI_EMAIL = None  # 默认邮箱为 None
    print("警告: 无法导入配置文件，使用默认配置")

async def main(pdf_path=None):
    # 使用默认PDF路径或命令行参数提供的路径
    if pdf_path is None:
        pdf_path = config.DEFAULT_PDF_PATH  # 直接使用config中已处理的值

    # 处理PDF路径
    clean_pdf_path = pdf_path  # config中的值已经被清理，不需要再次处理
    logger.info(f"正在处理PDF文件: {clean_pdf_path}")

    # Step 1: 直接使用config中已清理的值
    doi = config.ARTICLE_DOI  # 已在config.py中清理
    email = config.NCBI_EMAIL  # 已在config.py中清理

    if doi is None:
        logger.warning("未在配置中找到DOI (ARTICLE_DOI 环境变量未设置)。")
        pdf_filename_no_ext = os.path.splitext(os.path.basename(clean_pdf_path))[0]
        logger.info(f"将使用PDF文件名 '{pdf_filename_no_ext}' 作为部分输出标识符，但PubMed查询将失败。")

    if not email:
        logger.warning("警告: 未在配置中找到 NCBI 邮箱 (NCBI_EMAIL 环境变量未设置)。PubMed 查询可能受限或失败。")

    # --- 初始化智能体 ---
    pdf_parsing_agent = PDFParsingAgent()
    metadata_fetching_agent = MetadataFetchingAgent()
    from langchain_community.chat_models import ChatOpenAI # 导入 ChatOpenAI
    
    # 针对DashScope API进行特殊处理
    if "dashscope" in config.OPENAI_API_BASE_URL.lower():
        # 直接从环境变量再次读取模型名以确保最新值
        model_name = os.environ.get("OPENAI_API_MODEL", config.OPENAI_API_MODEL)
        model_name = model_name.split('#')[0].strip().strip('"').strip("'")
        
        logger.info(f"使用DashScope兼容模式和模型: {model_name}")
        
        # DashScope兼容模式下特殊处理
        headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
        
        # DashScope兼容模式配置
        llm = ChatOpenAI(
            api_key=config.OPENAI_API_KEY,
            model_name=model_name,  # 使用直接从环境变量读取的值
            base_url=config.OPENAI_API_BASE_URL,
            temperature=config.OPENAI_TEMPERATURE,
            streaming=False,
            default_headers=headers,
            verbose=True,
        )
    else:
        # 标准OpenAI API
        logger.info(f"使用标准OpenAI API和模型: {config.OPENAI_API_MODEL}")
        
        llm = ChatOpenAI(
            openai_api_key=config.OPENAI_API_KEY,
            model_name=config.OPENAI_API_MODEL,
            openai_api_base=config.OPENAI_API_BASE_URL,
            temperature=config.OPENAI_TEMPERATURE
        )
    
    methodology_analysis_agent = MethodologyAnalysisAgent(llm=llm)
    innovation_extraction_agent = InnovationExtractionAgent(llm=llm)
    qa_generation_agent = QAGenerationAgent(llm=llm)

    # --- Step 2: PDF解析 ---
    md_content = await pdf_parsing_agent.extract_content(clean_pdf_path)
    
    # --- 新增: 保存PDF转换后的Markdown内容到输出目录 ---
    # 获取PDF文件名（不含扩展名）
    pdf_filename_no_ext = os.path.splitext(os.path.basename(clean_pdf_path))[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 创建输出目录
    output_dir = os.path.join(config.OUTPUT_BASE_DIR, pdf_filename_no_ext)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 保存Markdown内容
    md_file_path = os.path.join(output_dir, f"{pdf_filename_no_ext}_markdown_{timestamp}.md")
    with open(md_file_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    logger.info(f"已将PDF转换为Markdown并保存到: {md_file_path}")

    # --- Step 3: 获取元数据 ---
    metadata = await metadata_fetching_agent.fetch_metadata(doi, email)
    original_s2_info = metadata["s2_info"]
    original_pubmed_info = metadata["pubmed_info"]
    
    # --- 新增: Step 3.5: 获取相关文献信息 ---
    related_articles = []
    reference_articles = []
    
    # 获取PubMed相关文献
    if original_pubmed_info and original_pubmed_info.get('pmid'):
        pmid = original_pubmed_info.get('pmid')
        logger.info(f"开始获取PMID {pmid}的相关文献...")
        try:
            related_articles = await metadata_fetching_agent.pubmed_client.get_related_articles(pmid, email)
            logger.info(f"成功获取到 {len(related_articles)} 篇相关文献")
        except Exception as e:
            logger.error(f"获取相关文献时出错: {e}")
    else:
        logger.warning("未获取到原文PMID，无法获取PubMed相关文献")
    
    # 获取Semantic Scholar参考文献
    if original_s2_info and original_s2_info.get('paperId'):
        paper_id = original_s2_info.get('paperId')
        logger.info(f"开始获取Semantic Scholar论文ID {paper_id}的参考文献...")
        try:
            # 使用新的批量获取方法
            reference_articles = await metadata_fetching_agent.s2_client.batch_get_references_by_papers(paper_id, limit=100)
            
            logger.info(f"成功获取 {len(reference_articles)} 篇参考文献")
            
            # 提取PMID以便获取更多信息
            pmids = []
            for ref in reference_articles:
                if (isinstance(ref, dict) and ref.get('externalIds') 
                    and isinstance(ref.get('externalIds'), dict) 
                    and ref['externalIds'].get('PubMed')):
                    pmids.append(ref['externalIds'].get('PubMed'))
            
            # 如果找到PMID，获取额外的PubMed信息
            if pmids:
                logger.info(f"发现 {len(pmids)} 个参考文献PMID，获取PubMed补充信息...")
                pubmed_details = await metadata_fetching_agent.pubmed_client.batch_get_article_details_by_pmids(pmids, email)
                logger.info(f"成功获取 {len(pubmed_details)} 个PubMed补充信息")
                
                # TODO: 可以选择将PubMed信息合并到参考文献中
        except Exception as e:
            logger.error(f"获取参考文献时出错: {e}")
            import traceback
            logger.debug(f"错误详情: {traceback.format_exc()}")
    else:
        logger.warning("未获取到原文的Semantic Scholar ID，无法获取参考文献")
            
    # 统计信息
    logger.info(f"数据收集完成: 原始文章信息已获取，找到 {len(related_articles)} 篇相关文献和 {len(reference_articles)} 篇参考文献")

    # --- Step 4: 方法分析 ---
    try:
        logger.info("开始分析文献方法...")
        methodology = await methodology_analysis_agent.analyze_methodology(md_content)
        logger.info(f"方法分析结果: {methodology}")
    except Exception as e:
        logger.error(f"方法分析失败: {e}")
        methodology = {"error": str(e), "方法类型": "未知", "关键技术": "未知", "创新方法": "未知"}

    # --- Step 5: 创新点提取 ---
    try:
        logger.info("开始提取创新点...")
        innovations = await innovation_extraction_agent.extract_innovations(md_content)
        logger.info(f"创新点提取结果: {innovations}")
    except Exception as e:
        logger.error(f"创新点提取失败: {e}")
        innovations = {"error": str(e), "核心创新": "未知", "潜在应用": "未知"}

    # --- Step 6: 问答生成 ---
    try:
        logger.info("开始生成问答...")
        qa = await qa_generation_agent.generate_qa(md_content)
        logger.info(f"问答生成结果: {qa}")
    except Exception as e:
        logger.error(f"问答生成失败: {e}")
        qa = {"error": str(e), "问题1": "未能生成问题", "答案1": "", 
              "问题2": "", "答案2": "", "问题3": "", "答案3": ""}

    # --- Step 7: 输出 ---
    logger.info("处理完成！")
    
    # 添加: 将结果保存到文件
    await save_results_to_files(
        pdf_path=clean_pdf_path,
        doi=doi,
        original_s2_info=original_s2_info,
        original_pubmed_info=original_pubmed_info,
        related_articles=related_articles,
        reference_articles=reference_articles,
        methodology=methodology,
        innovations=innovations,
        qa=qa
    )

async def save_results_to_files(
    pdf_path, doi, original_s2_info, original_pubmed_info, 
    related_articles, reference_articles, methodology, innovations, qa
):
    """将分析结果保存到文件"""
    # 获取PDF文件名（不含扩展名）作为输出目录名
    pdf_filename = os.path.basename(pdf_path)
    pdf_name_without_ext = os.path.splitext(pdf_filename)[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 创建输出目录 - 这是主输出文件夹
    output_dir = os.path.join(config.OUTPUT_BASE_DIR, pdf_name_without_ext)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 1. 保存JSON格式的原始数据
    json_data = {
        "metadata": {
            "pdf_file": pdf_path,
            "doi": doi,
            "timestamp": timestamp
        },
        "original_article": {
            "s2_info": original_s2_info,
            "pubmed_info": original_pubmed_info
        },
        "related_articles_count": len(related_articles) if related_articles else 0,
        "reference_articles_count": len(reference_articles) if reference_articles else 0,
        "analysis_results": {
            "methodology": methodology,
            "innovations": innovations,
            "qa_pairs": qa
        }
    }
    
    json_output_path = os.path.join(output_dir, f"{pdf_name_without_ext}_analysis_{timestamp}.json")
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    logger.info(f"已将分析结果保存到JSON文件: {json_output_path}")
    
    # 2. 生成Markdown格式的人类可读报告
    md_content = generate_markdown_report(
        pdf_name_without_ext, doi, original_s2_info, 
        original_pubmed_info, methodology, innovations, qa,
        related_count=len(related_articles) if related_articles else 0,
        reference_count=len(reference_articles) if reference_articles else 0
    )
    
    md_output_path = os.path.join(output_dir, f"{pdf_name_without_ext}_report_{timestamp}.md")
    with open(md_output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    logger.info(f"已将分析报告保存到Markdown文件: {md_output_path}")
    
    # 3. 【新增】保存相关文献和参考文献到CSV文件
    # 保存相关文献CSV
    if related_articles:
        related_csv_path = os.path.join(output_dir, f"{pdf_name_without_ext}_related_articles_{timestamp}.csv")
        export_articles_to_csv(related_articles, related_csv_path, is_pubmed=True)
        logger.info(f"已将 {len(related_articles)} 篇相关文献保存到CSV文件: {related_csv_path}")
    
    # 保存参考文献CSV
    if reference_articles:
        reference_csv_path = os.path.join(output_dir, f"{pdf_name_without_ext}_reference_articles_{timestamp}.csv")
        export_articles_to_csv(reference_articles, reference_csv_path, is_pubmed=False)
        logger.info(f"已将 {len(reference_articles)} 篇参考文献保存到CSV文件: {reference_csv_path}")
    
    return json_output_path, md_output_path

def export_articles_to_csv(articles, csv_path, is_pubmed=True):
    """将文章列表导出为CSV文件"""
    if not articles:
        logger.warning(f"没有文章数据可导出到 {csv_path}")
        return
        
    # 统一字段名格式，确保参考文献和相关文献使用相同的字段名
    standard_fields = [
        "pmid", "title", "authors", "journal", "pub_date", "abstract", "doi",
        "pmid_link", "pmcid", "pmcid_link"
    ]
    
    # 确保所有文章记录都有所有字段（如果缺少则设为空字符串）
    for article in articles:
        for field in standard_fields:
            if field not in article:
                article[field] = ""
        
        # 特别处理链接字段，只有在有对应ID时才设置链接
        # 处理 pmid_link
        if article.get("pmid"):
            if not article.get("pmid_link"):
                article["pmid_link"] = f"https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/"
        else:
            article["pmid_link"] = ""
            
        # 处理 pmcid_link
        if article.get("pmcid"):
            if not article.get("pmcid_link"):
                article["pmcid_link"] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{article['pmcid']}/"
        else:
            article["pmcid_link"] = ""
    
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=standard_fields)
            writer.writeheader()
            for article in articles:
                # 只写入标准字段
                row = {field: article.get(field, "") for field in standard_fields}
                writer.writerow(row)
        logger.info(f"已将 {len(articles)} 篇文章导出到 {csv_path}")
    except Exception as e:
        logger.error(f"导出CSV时出错: {e}")

def generate_markdown_report(
    pdf_name, doi, s2_info, pubmed_info, methodology, 
    innovations, qa_pairs, related_count=0, reference_count=0
):
    """生成Markdown格式的分析报告"""
    title = s2_info.get("title") if s2_info and "title" in s2_info else pdf_name
    
    # 准备作者列表
    authors = []
    if s2_info and "authors" in s2_info:
        authors = [author.get("name", "") for author in s2_info["authors"] if author.get("name")]
    
    # 生成Markdown内容
    md = []
    md.append(f"# {title}")
    md.append("")
    
    # 文献元数据
    md.append("## 文献信息")
    md.append("")
    md.append(f"- **DOI**: {doi}")
    if authors:
        md.append(f"- **作者**: {', '.join(authors)}")
    if s2_info:
        md.append(f"- **发表年份**: {s2_info.get('year', '未知')}")
        md.append(f"- **期刊/会议**: {s2_info.get('venue', '未知')}")
        if "fieldsOfStudy" in s2_info:
            fields = s2_info.get("fieldsOfStudy", [])
            if fields:
                md.append(f"- **研究领域**: {', '.join(fields)}")
    
    # 相关文献与参考文献统计
    md.append(f"- **相关文献数量**: {related_count}")
    md.append(f"- **参考文献数量**: {reference_count}")
    md.append("")
    
    # 摘要
    if s2_info and "abstract" in s2_info and s2_info["abstract"]:
        md.append("## 摘要")
        md.append("")
        md.append(s2_info["abstract"] or "未提供摘要")
        md.append("")
    elif pubmed_info and "abstract" in pubmed_info and pubmed_info["abstract"]:
        md.append("## 摘要")
        md.append("")
        md.append(pubmed_info["abstract"] or "未提供摘要")
        md.append("")
    
    # 方法学分析
    md.append("## 方法分析")
    md.append("")
    if methodology:
        if "方法类型" in methodology:
            md.append(f"### 方法类型")
            md.append(f"{methodology['方法类型'] or '未知'}")
            md.append("")
        
        if "关键技术" in methodology:
            md.append("### 关键技术")
            tech_list = methodology["关键技术"]
            if isinstance(tech_list, list) and tech_list:
                for tech in tech_list:
                    if tech: # 确保技术项不为None
                        md.append(f"- {tech}")
                md.append("")
            else:
                md.append("- 未提供关键技术信息")
                md.append("")
        
        if "创新方法" in methodology:
            md.append("### 创新方法")
            method_list = methodology["创新方法"]
            if isinstance(method_list, list) and method_list:
                for method in method_list:
                    if method: # 确保方法项不为None
                        md.append(f"- {method}")
                md.append("")
            else:
                md.append("- 未提供创新方法信息")
                md.append("")
    else:
        md.append("*未能获取方法分析结果*")
        md.append("")
    
    # 创新点分析
    md.append("## 创新点分析")
    md.append("")
    if innovations:
        if "核心创新" in innovations:
            md.append("### 核心创新")
            innovation_list = innovations["核心创新"]
            if isinstance(innovation_list, list) and innovation_list:
                for innovation in innovation_list:
                    if innovation: # 确保创新项不为None
                        md.append(f"- {innovation}")
                md.append("")
            else:
                md.append("- 未提供核心创新信息")
                md.append("")
        
        if "潜在应用" in innovations:
            md.append("### 潜在应用")
            application_list = innovations["潜在应用"]
            if isinstance(application_list, list) and application_list:
                for application in application_list:
                    if application: # 确保应用项不为None
                        md.append(f"- {application}")
                md.append("")
            else:
                md.append("- 未提供潜在应用信息")
                md.append("")
    else:
        md.append("*未能获取创新点分析结果*")
        md.append("")
    
    # 问答内容
    md.append("## 问答内容")
    md.append("")
    if qa_pairs:
        qnum = 1
        while f"问题{qnum}" in qa_pairs and f"答案{qnum}" in qa_pairs:
            question = qa_pairs[f"问题{qnum}"] or f"问题{qnum}"
            answer = qa_pairs[f"答案{qnum}"] or "未提供答案"
            md.append(f"### Q{qnum}: {question}")
            md.append(f"{answer}")
            md.append("")
            qnum += 1
    else:
        md.append("*未能获取问答内容*")
        md.append("")
    
    # 过滤掉可能的None值
    md = [item for item in md if item is not None]
    
    return "\n".join(md)

if __name__ == "__main__":
    # 命令行参数解析
    parser = argparse.ArgumentParser(description="PDF文献智能分析与洞察系统")
    parser.add_argument("-p", "--pdf", help="PDF文件路径", default=None)
    args = parser.parse_args()

    # 在参数解析后，实际运行主逻辑前设置日志
    setup_logging() 
    logger.info("SLAIS应用程序启动")
    
    # 运行主函数
    asyncio.run(main(args.pdf))
