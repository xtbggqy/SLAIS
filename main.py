import argparse
import asyncio
import json
import os
import datetime
from pathlib import Path
import csv # Import csv module

# 正确设置PYTHONPATH或确保项目结构允许这些导入
from pathlib import Path
import sys

# 确保项目根目录在路径中
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 先加载配置，确保环境变量正确设置
from slais import config
from slais.utils.logging_utils import logger, setup_logging

# 打印关键配置项，验证是否正确加载
logger.info(f"主程序启动，配置检查：")
logger.info(f"ARTICLE_DOI: {config.settings.ARTICLE_DOI}")
logger.info(f"SEMANTIC_SCHOLAR_API_BATCH_SIZE: {config.settings.SEMANTIC_SCHOLAR_API_BATCH_SIZE}")
logger.info(f"MAX_QUESTIONS_TO_GENERATE: {config.settings.MAX_QUESTIONS_TO_GENERATE}")

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
from agents.image_analysis_agent import ImageAnalysisAgent

async def process_article_pipeline(pdf_path: str, article_doi: str, ncbi_email: str):
    """
    完整的文章处理流程。
    """
    logger.info(f"开始处理文章，PDF路径: {pdf_path}, DOI: {article_doi}")

    # 1. 初始化LLM客户端 (支持.env配置的模型)
    # 文本 LLM
    llm_params = {
        "model_name": config.settings.OPENAI_API_MODEL,  # 从.env读取模型名
        "openai_api_key": config.settings.OPENAI_API_KEY,
        "temperature": config.settings.OPENAI_TEMPERATURE
    }
    if config.settings.OPENAI_API_BASE_URL:
        llm_params["openai_api_base"] = config.settings.OPENAI_API_BASE_URL

    logger.info(
        f"将使用文本模型: {llm_params.get('model_name')} | "
        f"API端点: {llm_params.get('openai_api_base', '官方默认')} | "
        f"温度: {llm_params.get('temperature')}"
        "（均可在.env中配置 OPENAI_API_MODEL、OPENAI_API_BASE_URL、OPENAI_TEMPERATURE）"
    )

    try:
        llm = ChatOpenAI(**llm_params)
        logger.info(f"OpenAI LLM客户端初始化完成。模型: {config.settings.OPENAI_API_MODEL}")
    except Exception as e:
        logger.error(f"初始化OpenAI LLM客户端失败: {e}")
        logger.error(f"使用的参数: {llm_params}")
        import traceback
        logger.debug(f"错误详情: {traceback.format_exc()}")
        return None

    # 图像 LLM
    image_llm_params = {
        "model_name": config.settings.IMAGE_LLM_API_MODEL,
        "openai_api_key": config.settings.IMAGE_LLM_API_KEY,
        "temperature": config.settings.IMAGE_LLM_TEMPERATURE
    }
    if config.settings.IMAGE_LLM_API_BASE_URL:
        image_llm_params["openai_api_base"] = config.settings.IMAGE_LLM_API_BASE_URL

    logger.info(
        f"将使用图片模型: {image_llm_params.get('model_name')} | "
        f"API端点: {image_llm_params.get('openai_api_base', '官方默认')} | "
        f"温度: {image_llm_params.get('temperature')}"
    )

    try:
        image_llm = ChatOpenAI(**image_llm_params)
    except Exception as e:
        logger.error(f"初始化图片 LLM 客户端失败: {e}")
        image_llm = None

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
    image_agent = ImageAnalysisAgent(image_llm)  # 用图片 LLM 初始化

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

    # 新增：提取图片路径列表（图片统一存放在 output/<pdf_stem>/<pdf_stem>_markdown/images 目录，且为相对路径）
    pdf_stem = Path(pdf_path).stem
    # MARKDOWN_SUBDIR 通常未设置，实际输出目录为 <pdf_stem>_markdown
    markdown_dir = Path(config.settings.OUTPUT_BASE_DIR) / pdf_stem / f"{pdf_stem}_markdown"
    image_dir = markdown_dir / "images"
    image_paths = []
    if image_dir.exists():
        # 以 markdown_dir 为基准，获得 images 下所有图片的相对路径
        image_paths = [str((image_dir / p.name).relative_to(markdown_dir)) for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp", ".gif"]]
    elif hasattr(pdf_parser, "extract_images") and callable(getattr(pdf_parser, "extract_images", None)):
        try:
            extracted = await pdf_parser.extract_images(pdf_path, output_dir=image_dir)
            if extracted and isinstance(extracted, list):
                # 以 markdown_dir 为基准，获得 images 下所有图片的相对路径
                image_paths = [str(Path(p).relative_to(markdown_dir)) for p in extracted]
                logger.info(f"自动提取图片，获得 {len(image_paths)} 张图片。")
        except Exception as e:
            logger.warning(f"自动提取图片失败: {e}")
    else:
        logger.info("PDFParsingAgent 不支持 extract_images 方法，跳过图片自动提取。")
    analysis_results["image_paths"] = image_paths

    # 3.1b 图片内容分析（并发）
    if image_paths:
        logger.info(f"检测到 {len(image_paths)} 张图片，开始分析图片内容...")
        image_analysis_results = await image_agent.analyze_images(
            [str(markdown_dir / p) for p in image_paths],
            context=markdown_content,
            callbacks=callbacks_list
        )
        analysis_results["image_analysis"] = image_analysis_results
        logger.info(f"图片内容分析完成，获得 {len(image_analysis_results)} 条描述。")
    else:
        analysis_results["image_analysis"] = []
        logger.info("未检测到可分析的图片。")

    # 新增：将图片内容分析结果格式化为Markdown字符串，供LLM分析用
    def format_image_analysis_md(image_analysis, image_paths):
        if not image_analysis or not isinstance(image_analysis, list):
            return "无图片内容分析结果。"
        lines = []
        for idx, img in enumerate(image_analysis):
            img_path = img.get("image_path", "")
            desc = img.get("description", "")
            rel_img_path = img_path
            if image_paths:
                for p in image_paths:
                    if p in img_path or Path(img_path).name == Path(p).name:
                        rel_img_path = p
                        break
            lines.append(f"图片{idx+1}: {rel_img_path}\n结构化描述: {desc}\n")
        return "\n".join(lines)
    image_analysis_md = format_image_analysis_md(analysis_results["image_analysis"], analysis_results["image_paths"])

    # 合并文献内容和图片分析内容，供LLM分析
    full_content = markdown_content + "\n\n图片内容分析：\n" + image_analysis_md

    # 3.2 元数据获取
    logger.info("步骤 2: 获取元数据...")
    metadata = await metadata_fetcher.fetch_metadata(doi=article_doi, email=ncbi_email)
    analysis_results["metadata"] = metadata
    logger.info("元数据获取完成。")
    s2_info = metadata.get("s2_info")
    pubmed_info = metadata.get("pubmed_info")

    # 3.3-3.9 LLM分析并发执行
    logger.info("步骤 3-9: 并发执行LLM分析任务...")
    tasks = {
        "methodology_analysis": methodology_analyzer.analyze_methodology(
            full_content, callbacks=callbacks_list),
        "innovation_extraction": innovation_extractor.extract_innovations(
            full_content, callbacks=callbacks_list),
        "questions": qa_generator.generate_questions(
            full_content, callbacks=callbacks_list),
        "story": storytelling_agent.tell_story(
            full_content, callbacks=callbacks_list),
        "mindmap": mindmap_agent.generate_mindmap(
            full_content, callbacks=callbacks_list)
    }
    # 并发执行
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for key, value in zip(tasks.keys(), results):
        if isinstance(value, Exception):
            logger.error(f"{key} 分析任务出错: {value}")
            analysis_results[key] = None
        else:
            analysis_results[key] = value

    # 3.5 问答生成 - 再为每个问题生成答案（单独并发）
    logger.info("步骤 5b: 为每个问题生成答案...")
    questions = analysis_results.get("questions") or []
    if questions:
        qa_pairs = await qa_generator.generate_answers_batch(
            questions,
            full_content,
            callbacks=callbacks_list
        )
    else:
        qa_pairs = []
    analysis_results["qa_pairs"] = qa_pairs

    # 3.6 (可选) 获取参考文献和相关文章
    if s2_info and s2_info.get("paperId"):
        logger.info("步骤 6: 获取参考文献...")
        references_data = await metadata_fetcher.fetch_references(s2_info["paperId"], ncbi_email)
        analysis_results["references_data"] = references_data
        logger.info(f"获取了 {len(references_data.get('reference_dois', []))} 条参考文献的DOI。")
    else:
        logger.info(f"步骤 6: 跳过获取参考文献，因为主要文章的 Semantic Scholar paperId 未找到或无效 (s2_info: {s2_info is not None}, paperId present: {s2_info.get('paperId') if s2_info else 'N/A'})。")
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

    logger.info("所有处理步骤完成。")
    token_callback_handler.log_total_usage()
    return analysis_results

def save_csv_report(data: list, filepath: Path, fieldnames: list):
    """Saves data to a CSV file with enhanced error handling and data validation."""
    try:
        # 确保所有记录都有所有需要的字段
        for item in data:
            for field in fieldnames:
                if field not in item:
                    item[field] = ""  # 添加缺失的字段
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:  # utf-8-sig for Excel compatibility
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            # 记录实际写入的数据量
            valid_count = 0
            for item in data:
                try:
                    writer.writerow(item)
                    valid_count += 1
                except Exception as row_error:
                    logger.warning(f"跳过一行数据，原因: {row_error}")
            
            logger.info(f"CSV报告已保存到: {filepath} (成功写入 {valid_count}/{len(data)} 条记录)")
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

def run_web_app():
    """
    启动Streamlit Web界面。
    """
    try:
        import streamlit as st
    except ImportError:
        print("未检测到streamlit库，请先运行: pip install streamlit")
        return
    # 动态导入web/web_app.py并运行
    from web.web_app import run_slais_web
    run_slais_web()

async def main_async():
    """
    异步主函数，协调整个流程。
    """
    setup_logging() # 初始化日志系统

    parser = argparse.ArgumentParser(description="PDF文献智能分析与洞察系统 (SLAIS)")
    parser.add_argument("--pdf", type=str, help="要分析的PDF文件路径。")
    parser.add_argument("--web", action="store_true", help="以Web界面模式运行（Streamlit）")
    args = parser.parse_args()

    if args.web:
        run_web_app()
        return

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
    """
    主入口函数，简化脚本结构，便于管理和调用。
    """
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
