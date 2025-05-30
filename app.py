import argparse
import asyncio
import json
import os
import datetime
from pathlib import Path
import csv # Import csv module
import sys # Ensure sys is imported for sys.argv and sys.executable

# 确保项目根目录在路径中
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 延迟导入配置和日志相关模块，只有在非帮助模式且参数有效时才导入
def initialize_app_dependencies():
    """延迟初始化应用依赖项（配置、日志等）"""
    global config, logger, setup_logging
    global ChatOpenAI, PromptTemplate
    global PDFParsingAgent, MetadataFetchingAgent
    global MethodologyAnalysisAgent, InnovationExtractionAgent, QAGenerationAgent
    global StorytellingAgent, MindMapAgent, TokenUsageCallbackHandler
    global generate_enhanced_report, ImageAnalysisAgent
    
    # 先加载配置，确保环境变量正确设置
    from slais import config
    from slais.utils.logging_utils import logger, setup_logging
    
    from langchain_openai import ChatOpenAI
    from langchain.prompts import PromptTemplate
    
    from agents.pdf_parsing_agent import PDFParsingAgent
    from agents.metadata_fetching_agent import MetadataFetchingAgent
    from agents.llm_analysis_agent import (
        MethodologyAnalysisAgent,
        InnovationExtractionAgent,
        QAGenerationAgent,
        StorytellingAgent,
        MindMapAgent
    )
    from agents.callbacks import TokenUsageCallbackHandler
    from agents.formatting_utils import generate_enhanced_report
    from agents.image_analysis_agent import ImageAnalysisAgent

# 延迟日志输出，只在非帮助模式下执行
def log_configuration_info():
    """在非帮助模式下输出配置信息"""
    logger.info(f"模块加载时配置检查：")
    logger.info(f"ARTICLE_DOI: {config.settings.ARTICLE_DOI}")
    logger.info(f"SEMANTIC_SCHOLAR_API_BATCH_SIZE: {config.settings.SEMANTIC_SCHOLAR_API_BATCH_SIZE}")
    logger.info(f"MAX_QUESTIONS_TO_GENERATE: {config.settings.MAX_QUESTIONS_TO_GENERATE}")

# Helper function to detect if running in Streamlit
def _get_streamlit_script_run_ctx():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx()
    except ImportError:
        # Fallback for older Streamlit versions or different import paths removed
        # as streamlit.report_thread caused an import error.
        # If this function returns None, we assume not in Streamlit context.
        return None

async def process_article_pipeline(pdf_path: str, article_doi: str, ncbi_email: str, progress_callback=None):
    """
    完整的文章处理流程。
    Args:
        pdf_path (str): PDF文件路径。
        article_doi (str): 文章DOI。
        ncbi_email (str): NCBI邮箱。
        progress_callback (callable, optional): 用于更新进度的回调函数，接收 (percentage, text) 参数。
    """
    # 确保导入必要的依赖项
    from slais.utils.logging_utils import logger
    from slais import config
    from langchain_openai import ChatOpenAI
    from agents.callbacks import TokenUsageCallbackHandler
    from agents.pdf_parsing_agent import PDFParsingAgent
    from agents.metadata_fetching_agent import MetadataFetchingAgent
    from agents.llm_analysis_agent import (
        MethodologyAnalysisAgent,
        InnovationExtractionAgent,
        QAGenerationAgent,
        StorytellingAgent,
        MindMapAgent
    )
    from agents.image_analysis_agent import ImageAnalysisAgent
    
    logger.info(f"开始处理文章，PDF路径: {pdf_path}, DOI: {article_doi}")

    def update_progress(percentage: int, text: str):
        if progress_callback:
            progress_callback(percentage, text)
        logger.info(f"进度更新: {percentage}% - {text}")

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
    # 阶段时间记录
    stage_times = {}
    stage_status = {}
    stage_costs = {}

    def record_stage(stage_name, start_time, end_time):
        now = end_time.strftime("%H:%M:%S")
        duration = (end_time - start_time).total_seconds()
        stage_times[stage_name] = now
        stage_status[stage_name] = "完成"
        stage_costs[stage_name] = duration
        logger.info(f"阶段记录成功: {{'阶段': '{stage_name}', '完成时间': '{now}', '耗时_秒': {duration:.2f}, '状态': '完成'}}")

    # 3.1 PDF解析
    update_progress(10, "步骤 1/6：解析PDF内容...")
    start_time_pdf_parsing = datetime.datetime.now() # 初始化 start_time_pdf_parsing
    markdown_content = await pdf_parser.extract_content(pdf_path)
    
    if not markdown_content:
        logger.error("PDF内容提取失败，流程中止。")
        stage_status["PDF内容解析"] = "失败" # 标记失败状态
        record_stage("PDF内容解析", start_time_pdf_parsing, datetime.datetime.now()) # 记录失败状态的时间
        # 考虑是否应该在这里也记录一个耗时，即使是失败的
        # 如果流程在此处中止，后续阶段将不会被记录
        # return None # 如果提前返回，确保前端能处理部分 stage_times 或无 stage_times 的情况
    else:
        record_stage("PDF内容解析", start_time_pdf_parsing, datetime.datetime.now()) # 记录成功状态的时间

    analysis_results["pdf_markdown_content_length"] = len(markdown_content) if markdown_content else 0
    update_progress(20, "步骤 1/6：PDF内容解析完成。")

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
    start_time_image_analysis = datetime.datetime.now()
    current_stage_name_image = "图片内容分析"
    if image_llm and image_paths: # 仅当image_llm成功初始化且有图片路径时才分析
        update_progress(25, f"步骤 2/6：检测到 {len(image_paths)} 张图片，开始分析图片内容...")
        try:
            image_analysis_results = await image_agent.analyze_images(
                [str(markdown_dir / p) for p in image_paths],
                context=markdown_content,
                callbacks=callbacks_list
            )
            analysis_results["image_analysis"] = image_analysis_results
            record_stage(current_stage_name_image, start_time_image_analysis, datetime.datetime.now())
            update_progress(35, f"步骤 2/6：图片内容分析完成，获得 {len(image_analysis_results)} 条描述。")
        except Exception as e:
            logger.error(f"图片内容分析过程中发生错误: {e}")
            analysis_results["image_analysis"] = []
            stage_status[current_stage_name_image] = "失败"
            record_stage(current_stage_name_image, start_time_image_analysis, datetime.datetime.now())
            update_progress(35, "步骤 2/6：图片内容分析失败。")
    elif not image_llm:
        logger.warning("图片LLM未成功初始化，跳过图片内容分析。")
        analysis_results["image_analysis"] = []
        stage_status[current_stage_name_image] = "跳过 (LLM未初始化)"
        record_stage(current_stage_name_image, start_time_image_analysis, datetime.datetime.now())
        update_progress(35, "步骤 2/6：图片LLM初始化失败，跳过图片分析。")
    else: # image_llm存在，但image_paths为空
        analysis_results["image_analysis"] = []
        stage_status[current_stage_name_image] = "跳过 (无图片)"
        record_stage(current_stage_name_image, start_time_image_analysis, datetime.datetime.now())
        update_progress(35, "步骤 2/6：未检测到可分析的图片。")

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
            lines.append(f"图片{idx+1}: {rel_img_path}\\n结构化描述: {desc}\\n")
        return "\\n".join(lines)
    image_analysis_md = format_image_analysis_md(analysis_results["image_analysis"], analysis_results["image_paths"])

    # 合并文献内容和图片分析内容，供LLM分析
    full_content = markdown_content + "\\n\\n图片内容分析：\\n" + image_analysis_md

    # 3.2 元数据获取
    update_progress(40, "步骤 3/6：获取元数据...")
    start_time_metadata = datetime.datetime.now()
    current_stage_name_metadata = "元数据获取"
    try:
        metadata = await metadata_fetcher.fetch_metadata(doi=article_doi, email=ncbi_email)
        analysis_results["metadata"] = metadata
        record_stage(current_stage_name_metadata, start_time_metadata, datetime.datetime.now())
        update_progress(50, "步骤 3/6：元数据获取完成。")
    except Exception as e:
        logger.error(f"元数据获取失败: {e}")
        analysis_results["metadata"] = {"pubmed_info": None, "s2_info": None, "error": str(e)}
        stage_status[current_stage_name_metadata] = "失败"
        record_stage(current_stage_name_metadata, start_time_metadata, datetime.datetime.now())
        update_progress(50, "步骤 3/6：元数据获取失败。")
        
    s2_info = analysis_results["metadata"].get("s2_info")
    pubmed_info = analysis_results["metadata"].get("pubmed_info")

    # 3.3-3.9 LLM分析并发执行
    update_progress(60, "步骤 4/6：LLM分析中...")
    start_time_llm_analysis = datetime.datetime.now()
    current_stage_name_llm = "LLM综合分析"
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
    try:
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for key, value in zip(tasks.keys(), results):
            if isinstance(value, Exception):
                logger.error(f"{key} 分析任务出错: {value}")
                analysis_results[key] = None # 或者记录错误信息 str(value)
            else:
                analysis_results[key] = value
        record_stage(current_stage_name_llm, start_time_llm_analysis, datetime.datetime.now())
        update_progress(70, "步骤 4/6：LLM分析完成。")
    except Exception as e:
        logger.error(f"LLM综合分析阶段出错: {e}")
        stage_status[current_stage_name_llm] = "失败"
        record_stage(current_stage_name_llm, start_time_llm_analysis, datetime.datetime.now())
        update_progress(70, "步骤 4/6：LLM分析失败。")


    # 3.5 问答生成 - 再为每个问题生成答案（单独并发）
    update_progress(75, "步骤 5/6：为每个问题生成答案...")
    start_time_qa_answers = datetime.datetime.now()
    current_stage_name_qa_answers = "问答对生成"
    questions = analysis_results.get("questions") or []
    if questions:
        try:
            qa_pairs = await qa_generator.generate_answers_batch(
                questions,
                full_content,
                callbacks=callbacks_list
            )
            analysis_results["qa_pairs"] = qa_pairs
            record_stage(current_stage_name_qa_answers, start_time_qa_answers, datetime.datetime.now())
        except Exception as e:
            logger.error(f"批量生成答案失败: {e}")
            analysis_results["qa_pairs"] = [{"question": q, "answer": "生成答案时出错"} for q in questions]
            stage_status[current_stage_name_qa_answers] = "失败"
            record_stage(current_stage_name_qa_answers, start_time_qa_answers, datetime.datetime.now())
    else:
        qa_pairs = []
        analysis_results["qa_pairs"] = qa_pairs
        stage_status[current_stage_name_qa_answers] = "跳过 (无问题)"
        record_stage(current_stage_name_qa_answers, start_time_qa_answers, datetime.datetime.now())
    update_progress(80, "步骤 5/6：问答生成完成。")

    # 3.6 (可选) 获取参考文献和相关文章
    s2_paper_id = s2_info.get("paperId") if s2_info else None
    pubmed_pmid = pubmed_info.get("pmid") if pubmed_info else None

    # 获取参考文献
    update_progress(85, "步骤 6/6：获取参考文献...")
    start_time_references = datetime.datetime.now()
    current_stage_name_references = "参考文献获取"
    references_data = {
        "source_paper_id": "N/A",
        "reference_dois": [],
        "full_references_details": [],
        "error": "未尝试获取参考文献。"
    }
    if s2_paper_id:
        try:
            references_data = await metadata_fetcher.fetch_references(s2_paper_id, ncbi_email)
            analysis_results["references_data"] = references_data
            record_stage(current_stage_name_references, start_time_references, datetime.datetime.now())
            update_progress(90, f"步骤 6/6：获取了 {len(references_data.get('full_references_details', []))} 条参考文献。")
        except Exception as e:
            logger.error(f"获取参考文献失败: {e}")
            references_data["error"] = str(e)
            analysis_results["references_data"] = references_data
            stage_status[current_stage_name_references] = "失败"
            record_stage(current_stage_name_references, start_time_references, datetime.datetime.now())
            update_progress(90, "步骤 6/6：获取参考文献失败。")
    else:
        logger.warning("跳过获取参考文献，因为主要文章的 Semantic Scholar paperId 未找到或无效。")
        references_data["error"] = "主要文章的 Semantic Scholar paperId 未找到或无效。"
        analysis_results["references_data"] = references_data
        stage_status[current_stage_name_references] = "跳过 (无S2PaperID)"
        record_stage(current_stage_name_references, start_time_references, datetime.datetime.now())
        update_progress(90, "步骤 6/6：跳过获取参考文献。")


    # 获取相关文章
    update_progress(95, "步骤 6/6：获取相关文章...")
    start_time_related_articles = datetime.datetime.now()
    current_stage_name_related = "相关文章获取"
    related_articles_pubmed = []
    if pubmed_pmid:
        try:
            related_articles_pubmed = await metadata_fetcher.fetch_related_articles(pubmed_pmid, ncbi_email)
            analysis_results["related_articles_pubmed"] = related_articles_pubmed
            record_stage(current_stage_name_related, start_time_related_articles, datetime.datetime.now())
            update_progress(98, f"步骤 6/6：获取了 {len(related_articles_pubmed)} 篇PubMed相关文章。")
        except Exception as e:
            logger.error(f"获取相关文章失败: {e}")
            analysis_results["related_articles_pubmed"] = []
            stage_status[current_stage_name_related] = "失败"
            record_stage(current_stage_name_related, start_time_related_articles, datetime.datetime.now())
            update_progress(98, "步骤 6/6：获取相关文章失败。")
    else:
        logger.warning("跳过获取相关文章，因为主要文章的 PubMed PMID 未找到或无效。")
        analysis_results["related_articles_pubmed"] = []
        stage_status[current_stage_name_related] = "跳过 (无PMID)"
        record_stage(current_stage_name_related, start_time_related_articles, datetime.datetime.now())
        update_progress(98, "步骤 6/6：跳过获取相关文章。")

    update_progress(100, "所有处理步骤完成。")
    token_callback_handler.log_total_usage()
    
    # 在 process_article_pipeline 函数的末尾，返回之前
    logger.info(f"最终返回的阶段时间信息 (stage_times): {stage_times}")
    logger.info(f"最终返回的阶段状态信息 (stage_status): {stage_status}")
    logger.info(f"最终返回的阶段耗时信息 (stage_costs): {stage_costs}")
    
    # 返回分析结果和阶段时间信息
    return {
        "analysis_results": analysis_results,
        "stage_times": stage_times,
        "stage_status": stage_status,
        "stage_costs": stage_costs,
        "total_token_usage": token_callback_handler.get_total_usage_and_cost()
    }

def save_csv_report(data: list, filepath: Path, fieldnames: list):
    """Saves data to a CSV file with enhanced error handling and data validation."""
    # 确保导入必要的依赖项
    from slais.utils.logging_utils import logger
    
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
    # 确保导入必要的依赖项
    from slais.utils.logging_utils import logger
    from slais import config
    from agents.formatting_utils import generate_enhanced_report
    
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
        import streamlit as st # Import streamlit here if not already at top
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
    parser = argparse.ArgumentParser(description="PDF文献智能分析与洞察系统 (SLAIS)")
    parser.add_argument("--pdf", type=str, help="要分析的PDF文件路径。")
    parser.add_argument("--web", action="store_true", help="以Web界面模式运行（Streamlit）")
    args = parser.parse_args()

    if args.web: # This flag's behavior might be less direct now with the new main()
        logger.info("`--web` flag detected in main_async. Calling run_web_app().")
        run_web_app()
        return

    pdf_to_process = args.pdf if args.pdf else config.settings.DEFAULT_PDF_PATH
    article_doi_to_process = config.settings.ARTICLE_DOI
    ncbi_email_for_requests = config.settings.NCBI_EMAIL

    if not pdf_to_process or not Path(pdf_to_process).exists(): # Added check for pdf_to_process being None/empty
        logger.error(f"指定的PDF文件不存在或未提供: {pdf_to_process}")
        logger.error("请使用 --pdf 参数指定一个有效的PDF文件路径。")
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
    Ensures the Streamlit web application is run.
    If the script is executed directly (e.g., `python app.py`), it launches
    the Streamlit server as a subprocess.
    If the script is already being run by Streamlit, this function calls
    the web app's main UI function.
    """
    ctx = _get_streamlit_script_run_ctx()

    if ctx:
        # Already running in Streamlit context
        logger.info("脚本已在Streamlit环境中运行。调用 run_web_app()。")
        run_web_app()
    else:
        # Not running in Streamlit context, launch Streamlit via subprocess
        logger.info("脚本未在Streamlit环境中运行。尝试通过subprocess启动Streamlit。")
        import subprocess
        # import sys # Already imported at the top
        # import os  # Already imported at the top
        try:
            script_path = os.path.abspath(__file__)
            logger.info(f"执行: {sys.executable} -m streamlit run {script_path}")
            subprocess.run([sys.executable, "-m", "streamlit", "run", script_path], check=True)
        except FileNotFoundError:
            logger.error("未找到streamlit。请确保已安装streamlit: pip install streamlit")
        except subprocess.CalledProcessError as e:
            logger.error(f"运行streamlit失败: {e}")

if __name__ == "__main__":
    # 首先检查是否是帮助请求或者进行参数预验证，避免在错误参数时加载配置和日志
    try:
        # 创建临时解析器用于验证参数和处理帮助
        temp_parser = argparse.ArgumentParser(
            description="PDF文献智能分析与洞察系统 (SLAIS)",
            epilog="""
使用示例:
  python app.py                           # 启动Web界面模式 (Streamlit)
  python app.py --pdf path/to/file.pdf    # CLI模式处理指定PDF文件
  python app.py --web                     # 显式启动Web界面模式
  python app.py --help                    # 显示此帮助信息

注意: CLI模式需要在 .env 文件中配置 ARTICLE_DOI 和 NCBI_EMAIL
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        temp_parser.add_argument("--pdf", type=str, help="要分析的PDF文件路径 (CLI模式)")
        temp_parser.add_argument("--web", action="store_true", help="以Web界面模式运行 (Streamlit)")
        
        # 预解析参数 - 这会处理帮助和捕获无效参数
        args = temp_parser.parse_args()
        
        # 如果到了这里，说明参数是有效的，现在可以安全地初始化应用依赖
        initialize_app_dependencies()
        setup_logging()
        log_configuration_info()
        
    except SystemExit as e:
        # argparse 在帮助或错误时会调用 sys.exit()
        # 如果是帮助 (exit code 0) 或参数错误 (exit code 2)，直接退出而不初始化日志
        sys.exit(e.code)
    
    # 判断运行模式
    if args.pdf:
        # CLI PDF 处理模式
        logger.info("检测到CLI PDF处理模式。")
        asyncio.run(main_async())
    elif args.web:
        # 显式Web模式
        logger.info("显式请求Web界面模式。")
        main()
    else:
        # 默认情况下启动Web界面
        logger.info("默认进入Web UI模式或由Streamlit直接执行。")
        main()
