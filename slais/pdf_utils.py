import os
import json
import re
import fitz  # PyMuPDF
import logging
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod
from .utils.logging_utils import logger

def convert_pdf_to_markdown(pdf_path, output_dir=None):
    """
    将PDF文件转换为Markdown格式。
    
    参数:
        pdf_path (str): 输入PDF文件的路径
        output_dir (str, optional): 输出目录，默认为None。如果未提供，将根据PDF文件名创建输出目录。
    返回:
        str: 生成的Markdown文件路径
    """
    # 获取PDF文件名（不含扩展名）
    pdf_file_name = os.path.basename(pdf_path)
    name_without_suff = pdf_file_name.split(".")[0]
    
    logger.info(f"开始转换PDF文件：{pdf_file_name}")
    
    # 准备输出目录
    if output_dir is None:
        output_dir = os.path.join("output", name_without_suff)
    
    local_image_dir = os.path.join(output_dir, "images")
    local_md_dir = output_dir
    image_dir = os.path.basename(local_image_dir)
    
    os.makedirs(local_image_dir, exist_ok=True)
    logger.info(f"输出目录已准备好：{output_dir}")
    
    # 保存原始日志级别并临时设置为ERROR
    original_log_levels = {}
    for logger_name in ['magic_pdf', 'transformers', 'PIL', 'httpx', 'matplotlib', 
                       'huggingface_hub', 'torch', 'tensorboard']:
        logger_obj = logging.getLogger(logger_name)
        original_log_levels[logger_name] = logger_obj.level
        logger_obj.setLevel(logging.ERROR)  # 只显示错误及以上级别的日志
    
    # 临时禁用根日志处理器
    root_logger = logging.getLogger()
    root_handlers = root_logger.handlers.copy()
    root_level = root_logger.level
    for handler in root_handlers:
        root_logger.removeHandler(handler)
    root_logger.setLevel(logging.ERROR)
    
    try:
        # 初始化写入器
        image_writer = FileBasedDataWriter(local_image_dir)
        md_writer = FileBasedDataWriter(local_md_dir)
        
        # 读取PDF内容
        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(pdf_path)
        logger.info("PDF内容已读取")
        
        # 创建数据集实例
        ds = PymuDocDataset(pdf_bytes)
        
        # 推断处理模式
        if ds.classify() == SupportedPdfParseMethod.OCR:
            logger.info("使用OCR模式处理PDF")
            infer_result = ds.apply(doc_analyze, ocr=True)
            pipe_result = infer_result.pipe_ocr_mode(image_writer)
        else:
            logger.info("使用文本模式处理PDF")
            infer_result = ds.apply(doc_analyze, ocr=False)
            pipe_result = infer_result.pipe_txt_mode(image_writer)
        
        logger.info("PDF处理完成")
        
        # 绘制模型结果
        infer_result.draw_model(os.path.join(local_md_dir, f"{name_without_suff}_model.pdf"))
        logger.info("模型结果已绘制")
        
        # 获取模型推断结果
        model_inference_result = infer_result.get_infer_res()
        
        # 绘制布局结果
        pipe_result.draw_layout(os.path.join(local_md_dir, f"{name_without_suff}_layout.pdf"))
        logger.info("布局结果已绘制")
        
        # 绘制跨度结果
        pipe_result.draw_span(os.path.join(local_md_dir, f"{name_without_suff}_spans.pdf"))
        logger.info("跨度结果已绘制")
        
        # 获取原始Markdown内容和内容列表
        md_content_original = pipe_result.get_markdown(image_dir)
        content_list = pipe_result.get_content_list(image_dir)
        
        # --- Begin Diagnostic Logging for content_list ---
        # 减少诊断日志输出量，仅保留最核心信息
        logger.info(f"内容列表分析: 共 {len(content_list) if content_list else 0} 个内容块")
        image_blocks = [block for block in content_list if block.get('type') == 'image']
        logger.info(f"找到 {len(image_blocks)} 个图像块")
        
        # --- End Diagnostic Logging for content_list ---
        
        updated_md_content = md_content_original
        image_counter = 0 # Initialize image_counter here
        
        logger.info("开始重命名图片并更新Markdown内容中的图片链接...")
        
        # 基于 content_list 方法未能找到图片，我们改为直接在输出目录中查找图片文件
        if os.path.exists(local_image_dir) and os.path.isdir(local_image_dir):
            image_files = [f for f in os.listdir(local_image_dir) 
                          if os.path.isfile(os.path.join(local_image_dir, f)) 
                          and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
            
            logger.info(f"在图像目录 '{local_image_dir}' 中找到 {len(image_files)} 个图像文件")
            
            image_files.sort()
            
            for idx, img_filename in enumerate(image_files):
                original_image_path = os.path.join(local_image_dir, img_filename)
                _, ext = os.path.splitext(img_filename)
                new_image_filename = f"image_{idx:03d}{ext}"
                new_image_path = os.path.join(local_image_dir, new_image_filename)
                
                if image_dir:
                    original_md_image_path = f"{image_dir}/{img_filename}"
                    new_md_image_path = f"{image_dir}/{new_image_filename}"
                else:
                    original_md_image_path = img_filename
                    new_md_image_path = new_image_filename
                
                try:
                    os.rename(original_image_path, new_image_path)
                    logger.info(f"图片已重命名: '{img_filename}' -> '{new_image_filename}'")
                    
                    if original_md_image_path in updated_md_content:
                        updated_md_content = updated_md_content.replace(original_md_image_path, new_md_image_path)
                        logger.info(f"Markdown中的图片链接已更新: '{original_md_image_path}' -> '{new_md_image_path}'")
                        image_counter += 1
                    else:
                        alt_original_path = original_md_image_path.replace('\\', '/')
                        alt_new_path = new_md_image_path.replace('\\', '/')
                        if alt_original_path in updated_md_content:
                            updated_md_content = updated_md_content.replace(alt_original_path, alt_new_path)
                            logger.info(f"Markdown中的图片链接已更新(替代路径格式): '{alt_original_path}' -> '{alt_new_path}'")
                            image_counter += 1
                        else:
                            logger.warning(f"在Markdown内容中找不到图片路径引用: '{original_md_image_path}' 或 '{alt_original_path}'")
                
                except OSError as e:
                    logger.error(f"重命名图片失败 '{original_image_path}' 到 '{new_image_path}': {e}")
        else:
            logger.warning(f"图像目录不存在或不是有效目录: '{local_image_dir}'")

        logger.info(f"图片重命名和Markdown链接更新完成。共处理 {image_counter} 张图片。")
        
        md_file_path = os.path.join(local_md_dir, f"{name_without_suff}.md")
        try:
            with open(md_file_path, "w", encoding="utf-8") as f:
                f.write(updated_md_content)
            logger.info(f"更新后的Markdown文件已保存：{md_file_path}")
        except IOError as e:
            logger.error(f"保存更新后的Markdown文件失败 '{md_file_path}': {e}")
        
        content_list_content = pipe_result.get_content_list(image_dir)
        pipe_result.dump_content_list(md_writer, f"{name_without_suff}_content_list.json", image_dir)
        logger.info("内容列表已保存")
        
        middle_json_content = pipe_result.get_middle_json()
        pipe_result.dump_middle_json(md_writer, f"{name_without_suff}_middle.json")
        logger.info("中间JSON文件已保存")
        
        return md_file_path
    finally:
        # 恢复原始日志级别
        for logger_name, level in original_log_levels.items():
            logger_obj = logging.getLogger(logger_name)
            logger_obj.setLevel(level)
        
        # 恢复根日志处理器
        root_logger.setLevel(root_level)
        for handler in root_handlers:
            root_logger.addHandler(handler)

def extract_images(pdf_path, output_dir):
    """
    从PDF文件中提取图像。

    参数:
        pdf_path (str): 输入PDF文件的路径
        output_dir (str): 图像输出目录
    返回:
        list: 提取到的图像文件路径列表
    """
    logger.info(f"开始从PDF文件 {os.path.basename(pdf_path)} 提取图像到 {output_dir}")
    image_paths = []
    try:
        os.makedirs(output_dir, exist_ok=True)
        image_writer = FileBasedDataWriter(output_dir)

        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(pdf_path)
        ds = PymuDocDataset(pdf_bytes)

        infer_result = ds.apply(doc_analyze, ocr=ds.classify() == SupportedPdfParseMethod.OCR)
        pipe_result = infer_result.pipe_txt_mode(image_writer) if ds.classify() != SupportedPdfParseMethod.OCR else infer_result.pipe_ocr_mode(image_writer)

        saved_files = os.listdir(output_dir)
        image_paths = [os.path.join(output_dir, f) for f in saved_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]

        logger.info(f"从PDF文件 {os.path.basename(pdf_path)} 提取图像完成，共找到 {len(image_paths)} 张图像。")

    except Exception as e:
        logger.error(f"提取图像时发生错误：{str(e)}")
        image_paths = [] 
    return image_paths

def extract_tables(pdf_path):
    """
    从PDF文件中提取表格并转换为Markdown格式。

    参数:
        pdf_path (str): 输入PDF文件的路径
    返回:
        list: 提取到的表格的Markdown字符串列表
    """
    logger.info(f"开始从PDF文件 {os.path.basename(pdf_path)} 提取表格")
    tables_markdown = []
    try:
        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(pdf_path)
        ds = PymuDocDataset(pdf_bytes)

        infer_result = ds.apply(doc_analyze, ocr=ds.classify() == SupportedPdfParseMethod.OCR)

        if hasattr(infer_result, 'get_tables'):
             tables = infer_result.get_tables()
             for table in tables:
                 if hasattr(table, 'to_markdown'):
                     tables_markdown.append(table.to_markdown())
                     logger.info("提取并转换了一个表格")
                 else:
                     logger.warning("检测到表格对象，但不支持转换为Markdown")
        else:
            logger.warning("magic_pdf infer_result 不支持直接获取表格")
            pass 

        logger.info(f"从PDF文件 {os.path.basename(pdf_path)} 提取表格完成，共找到 {len(tables_markdown)} 个表格。")

    except Exception as e:
        logger.error(f"提取表格时发生错误：{str(e)}")
        tables_markdown = [] 
    return tables_markdown
