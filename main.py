import argparse
import asyncio
import json
import os
import datetime
from pathlib import Path
import csv # Import csv module

# 正确设置PYTHONPATH或确保项目结构允许这些导入
# 假设main.py在项目根目录，slais和agents是其子目录（或通过PYTHONPATH可访问）
from slais import config
from slais.utils.logging_utils import logger, setup_logging
from langchain_openai import ChatOpenAI # 直接导入ChatOpenAI
from langchain.prompts import PromptTemplate # 导入PromptTemplate

from agents.pdf_parsing_agent import PDFParsingAgent
from agents.metadata_fetching_agent import MetadataFetchingAgent
from agents.llm_analysis_agent import (
    MethodologyAnalysisAgent,
    InnovationExtractionAgent,
    QAGenerationAgent,
    StorytellingAgent,
    MindMapAgent
)
from agents.callbacks import TokenUsageCallbackHandler # 新增导入
from agents.formatting_utils import generate_enhanced_report # 从新模块导入格式化函数

async def process_article_pipeline(pdf_path: str, article_doi: str, ncbi_email: str):
    """
    完整的文章处理流程。
    """
    logger.info(f"开始处理文章，PDF路径: {pdf_path}, DOI: {article_doi}")

    # 1. 初始化LLM客户端 (直接使用OpenAI)
    llm_params = {
        "model_name": config.settings.OPENAI_API_MODEL,
        "openai_api_key": config.settings.OPENAI_API_KEY,
        "temperature": config.settings.OPENAI_TEMPERATURE
    }
    if config.settings.OPENAI_API_BASE_URL: # 兼容可能存在的自定义OpenAI基础URL或兼容API
        llm_params["openai_api_base"] = config.settings.OPENAI_API_BASE_URL
    
    try:
        llm = ChatOpenAI(**llm_params) # 直接实例化ChatOpenAI
        logger.info(f"OpenAI LLM客户端初始化完成。模型: {config.settings.OPENAI_API_MODEL}")
    except Exception as e:
        logger.error(f"初始化OpenAI LLM客户端失败: {e}")
        logger.error(f"使用的参数: {llm_params}")
        import traceback
        logger.debug(f"错误详情: {traceback.format_exc()}")
        return None

    # 实例化 TokenUsageCallbackHandler
    token_callback_handler = TokenUsageCallbackHandler(model_name=config.settings.OPENAI_API_MODEL)
    callbacks_list = [token_callback_handler] # 创建回调列表

    # 2. 初始化智能体
    pdf_parser = PDFParsingAgent()
    metadata_fetcher = MetadataFetchingAgent()
    methodology_analyzer = MethodologyAnalysisAgent(llm)
    innovation_extractor = InnovationExtractionAgent(llm)
    qa_generator = QAGenerationAgent(llm)
    storytelling_agent = StorytellingAgent(llm)
    mindmap_agent = MindMapAgent(llm)

    # 3. 执行流程
    analysis_results = {}

    # 3.1 PDF解析
    logger.info("步骤 1: 解析PDF内容...")
    markdown_content = await pdf_parser.extract_content(pdf_path)
    if not markdown_content:
        logger.error("PDF内容提取失败，流程中止。")
        return None
    analysis_results["pdf_markdown_content_length"] = len(markdown_content)
    logger.info(f"PDF内容提取完成，Markdown长度: {len(markdown_content)}")

    # 3.2 元数据获取
    logger.info("步骤 2: 获取元数据...")
    metadata = await metadata_fetcher.fetch_metadata(doi=article_doi, email=ncbi_email)
    analysis_results["metadata"] = metadata
    logger.info("元数据获取完成。")
    
    s2_info = metadata.get("s2_info")
    pubmed_info = metadata.get("pubmed_info")

    # 3.3 方法学分析
    logger.info("步骤 3: 分析方法学...")
    methodology_analysis = await methodology_analyzer.analyze_methodology(
        markdown_content, 
        callbacks=callbacks_list # 传递回调
    )
    analysis_results["methodology_analysis"] = methodology_analysis
    logger.info("方法学分析完成。")

    # 3.4 创新点提取
    logger.info("步骤 4: 提取创新点...")
    innovation_extraction = await innovation_extractor.extract_innovations(
        markdown_content, 
        callbacks=callbacks_list # 传递回调
    )
    analysis_results["innovation_extraction"] = innovation_extraction
    logger.info("创新点提取完成。")

    # 3.5 问答生成 - 先生成问题
    logger.info("步骤 5a: 生成问题...")
    questions = await qa_generator.generate_questions(
        markdown_content, 
        callbacks=callbacks_list # 传递回调
    )
    logger.info(f"生成了 {len(questions)} 个问题。")
    analysis_results["questions"] = questions

    # 3.5 问答生成 - 再为每个问题生成答案
    logger.info("步骤 5b: 为每个问题生成答案...")
    if questions:
        qa_pairs = await qa_generator.generate_answers_batch(
            questions,
            markdown_content,
            callbacks=callbacks_list  # 传递回调
        )
    else:
        qa_pairs = []

    analysis_results["qa_pairs"] = qa_pairs

    # 3.6 (可选) 获取参考文献和相关文章 - 示例
    if s2_info and s2_info.get("paperId"):
        logger.info("步骤 6: 获取参考文献...")
        references_data = await metadata_fetcher.fetch_references(s2_info["paperId"], ncbi_email)
        analysis_results["references_data"] = references_data
        logger.info(f"获取了 {len(references_data.get('reference_dois', []))} 条参考文献的DOI。")
    else:
        logger.info(f"步骤 6: 跳过获取参考文献，因为主要文章的 Semantic Scholar paperId 未找到或无效 (s2_info: {s2_info is not None}, paperId present: {s2_info.get('paperId') if s2_info else 'N/A'})。")
        # 确保 analysis_results["references_data"] 有一个默认结构，以便后续保存步骤不会出错
        analysis_results["references_data"] = {
            "source_paper_id": s2_info.get("paperId") if s2_info else "N/A",
            "reference_dois": [],
            "full_references_details": [],
            "error": "Skipped fetching references due to missing or invalid S2 paperId for the main article."
        }

    if pubmed_info and pubmed_info.get("pmid"):
        logger.info("步骤 7: 获取相关文章 (PubMed)...")
        related_articles_pubmed = await metadata_fetcher.fetch_related_articles(pubmed_info["pmid"], ncbi_email)
        analysis_results["related_articles_pubmed"] = related_articles_pubmed
        logger.info(f"获取了 {len(related_articles_pubmed)} 篇PubMed相关文章。")

    # 3.7 故事讲述
    logger.info("步骤 8: 以讲故事的方式讲述文献...")
    story = await storytelling_agent.tell_story(
        markdown_content,
        callbacks=callbacks_list  # 传递回调
    )
    analysis_results["story"] = story
    logger.info("故事讲述完成。")

    # 3.8 生成脑图
    logger.info("步骤 9: 生成 Mermaid 脑图...")
    mindmap = await mindmap_agent.generate_mindmap(
        markdown_content,
        callbacks=callbacks_list  # 传递回调
    )
    analysis_results["mindmap"] = mindmap
    logger.info("Mermaid 脑图生成完成。")

    logger.info("所有处理步骤完成。")
    token_callback_handler.log_total_usage()  # 在流程结束时记录总用量
    return analysis_results

def save_csv_report(data: list, filepath: Path, fieldnames: list):
    """Saves data to a CSV file."""
    try:
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f: # utf-8-sig for Excel compatibility
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
        logger.info(f"CSV报告已保存到: {filepath}")
    except Exception as e:
        logger.error(f"保存CSV报告 {filepath} 失败: {e}")

def save_report(results: dict, pdf_path: str):
    """
    将分析结果保存为Markdown和相关的CSV报告。
    """
    if not results:
        logger.warning("没有结果可保存。")
        return

    pdf_filename_stem = Path(pdf_path).stem
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    output_subdir = Path(config.settings.OUTPUT_BASE_DIR) / pdf_filename_stem
    output_subdir.mkdir(parents=True, exist_ok=True)
    
    # 定义统一的CSV列名，确保信息全面且一致
    unified_fieldnames = [
        'doi', 'title', 'authors_str', 'pub_date', 'journal', 'abstract', 
        'pmid', 'pmid_link', 'pmcid', 'pmcid_link', 'citation_count', 's2_paper_id'
    ]
    
    # 1. 生成并保存增强版Markdown报告
    md_report_content = generate_enhanced_report(results, pdf_filename_stem)
    md_report_filename = f"{pdf_filename_stem}_analysis_report_{timestamp}.md"
    md_report_filepath = output_subdir / md_report_filename
    try:
        with open(md_report_filepath, 'w', encoding='utf-8') as f:
            f.write(md_report_content)
        logger.info(f"增强版Markdown分析报告已保存到: {md_report_filepath}")
    except Exception as e:
        logger.error(f"保存Markdown报告失败: {e}")

    # 3. 保存参考文献CSV
    references_data_list = results.get("references_data", {}).get("full_references_details")
    if references_data_list and isinstance(references_data_list, list):
        references_csv_filepath = output_subdir / f"{pdf_filename_stem}_references_{timestamp}.csv"
        # 使用统一的字段名
        save_csv_report(references_data_list, references_csv_filepath, unified_fieldnames)
    else:
        logger.info("没有参考文献详细信息可保存为CSV。")

    # 4. 保存相关文献CSV (PubMed)
    related_articles_pubmed = results.get("related_articles_pubmed")
    if related_articles_pubmed and isinstance(related_articles_pubmed, list):
        related_pubmed_csv_filepath = output_subdir / f"{pdf_filename_stem}_related_pubmed_{timestamp}.csv"
        # 使用统一的字段名
        processed_related_pubmed = []
        for article in related_articles_pubmed:
            new_article = article.copy()
            # 确保 'authors' (list) is converted to 'authors_str'
            if 'authors' in new_article and isinstance(new_article['authors'], list):
                new_article['authors_str'] = "; ".join(new_article['authors'])
            elif 'authors' in new_article and isinstance(new_article['authors'], str): # 如果已经是字符串
                new_article['authors_str'] = new_article['authors']
            elif 'authors_str' not in new_article: # 如果 'authors_str' 也不存在
                new_article['authors_str'] = ""
            
            # 移除旧的 'authors' 键（如果是列表），避免与 unified_fieldnames 中的 'authors_str' 冲突或混淆
            if 'authors' in new_article and isinstance(new_article['authors'], list):
                del new_article['authors']

            processed_related_pubmed.append(new_article)
        save_csv_report(processed_related_pubmed, related_pubmed_csv_filepath, unified_fieldnames)
    else:
        logger.info("没有PubMed相关文献信息可保存为CSV。")

async def main_async():
    """
    异步主函数，协调整个流程。
    """
    setup_logging() # 初始化日志系统

    parser = argparse.ArgumentParser(description="PDF文献智能分析与洞察系统 (SLAIS)")
    parser.add_argument("--pdf", type=str, help="要分析的PDF文件路径。")
    args = parser.parse_args()

    pdf_to_process = args.pdf if args.pdf else config.settings.DEFAULT_PDF_PATH
    article_doi_to_process = config.settings.ARTICLE_DOI
    ncbi_email_for_requests = config.settings.NCBI_EMAIL

    if not Path(pdf_to_process).exists():
        logger.error(f"指定的PDF文件不存在: {pdf_to_process}")
        return

    if not article_doi_to_process:
        logger.error("ARTICLE_DOI 未在配置中设置。请在 .env 文件中配置。")
        return
        
    if not ncbi_email_for_requests or ncbi_email_for_requests == "your@gmail.com":
        logger.warning("NCBI_EMAIL 未在配置中正确设置或仍为默认值。PubMed API请求可能会受限或失败。")
        # 可以选择在这里中止，或者允许继续但带有警告

    final_results = await process_article_pipeline(
        pdf_path=pdf_to_process,
        article_doi=article_doi_to_process,
        ncbi_email=ncbi_email_for_requests
    )

    if final_results:
        save_report(final_results, pdf_to_process)
    else:
        logger.error("文章处理流程未能生成有效结果。")

def main():
    # 设置uvloop作为事件循环策略（如果已安装且在非Windows环境）
    # try:
    #     import uvloop
    #     asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    #     logger.info("使用uvloop事件循环策略。")
    # except ImportError:
    #     logger.info("uvloop未安装，使用默认事件循环策略。")
    #     pass
    
    # 对于Windows，asyncio.run() 默认使用 ProactorEventLoop，通常是合适的。
    # 对于其他平台，SelectorEventLoop是默认的。
    asyncio.run(main_async())

if __name__ == "__main__":
    # 为了使此脚本可以直接从根目录运行，并且能够找到slais和agents模块，
    # 你可能需要确保项目根目录在PYTHONPATH中，或者在IDE中正确配置了项目结构。
    # 一个简单的处理方式是在脚本开头临时将项目根目录添加到sys.path：
    # import sys
    # sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    # 但更好的做法是正确安装项目（例如，使用 `pip install -e .` 如果有setup.py）
    # 或依赖PYTHONPATH的设置。

    main()
