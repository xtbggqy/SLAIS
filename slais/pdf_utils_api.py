"""PDF处理工具 - API版本

使用MinerU API进行PDF解析处理
"""

import os
import tempfile
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import fitz  # PyMuPDF

from slais.config import (
    MINERU_API_KEY,
    MINERU_API_BASE_URL,
    MINERU_MAX_WAIT_TIME,
    MINERU_CHECK_INTERVAL,
    MINERU_MAX_RETRIES,
    MINERU_RETRY_DELAY
)
from slais.mineru_api_client import MinerUAPIClient
from slais.utils.logging_utils import logger

def convert_pdf_with_mineru_api(pdf_path: str, output_dir: str, **kwargs) -> str:
    """
    使用MinerU API将PDF转换为Markdown
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        **kwargs: 其他参数
        
    Returns:
        生成的Markdown文件路径
    """
    if not MINERU_API_KEY:
        raise ValueError("MinerU API密钥未配置，请设置MINERU_API_KEY环境变量")
    
    logger.info(f"使用MinerU API处理PDF文件: {pdf_path}")
    
    # 初始化客户端
    client = MinerUAPIClient(
        api_key=MINERU_API_KEY,
        api_base=MINERU_API_BASE_URL
    )
    
    # 设置超时和重试参数
    kwargs.setdefault('max_wait_time', MINERU_MAX_WAIT_TIME)
    kwargs.setdefault('max_retries', MINERU_MAX_RETRIES)
    kwargs.setdefault('retry_delay', MINERU_RETRY_DELAY)
    
    try:
        # 执行转换
        markdown_path = client.upload_file_and_extract(
            pdf_path=pdf_path,
            output_dir=output_dir,
            **kwargs
        )
        
        logger.info(f"PDF转换完成: {markdown_path}")
        return markdown_path
        
    except Exception as e:
        logger.error(f"PDF转换失败: {e}")
        raise

def extract_doi_from_pdf(pdf_path: str) -> Optional[str]:
    """
    从PDF中提取DOI信息
    
    Args:
        pdf_path: PDF文件路径
        
    Returns:
        DOI字符串，如果未找到则返回None
    """
    try:
        doc = fitz.open(pdf_path)
        
        # 搜索前几页的DOI信息
        for page_num in range(min(3, len(doc))):
            page = doc.load_page(page_num)
            text = page.get_text()
            
            # 搜索DOI模式
            import re
            doi_patterns = [
                r'DOI[:\s]*([0-9]{2}\.[0-9]{4,}/[^\s]+)',
                r'doi[:\s]*([0-9]{2}\.[0-9]{4,}/[^\s]+)',
                r'https?://doi\.org/([0-9]{2}\.[0-9]{4,}/[^\s]+)',
                r'https?://dx\.doi\.org/([0-9]{2}\.[0-9]{4,}/[^\s]+)'
            ]
            
            for pattern in doi_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    doi = match.group(1)
                    logger.info(f"从PDF中提取到DOI: {doi}")
                    doc.close()
                    return doi
        
        doc.close()
        logger.info(f"未在PDF中找到DOI信息: {pdf_path}")
        return None
        
    except Exception as e:
        logger.warning(f"提取DOI时出错: {e}")
        return None

def process_pdf(pdf_path: str, output_dir: str, **kwargs) -> Dict[str, Any]:
    """
    处理PDF文件的主函数（保持原有接口兼容性）
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        **kwargs: 其他参数
        
    Returns:
        处理结果字典，包含markdown_path、doi等信息
    """
    result = {}
    
    try:
        # 转换为Markdown
        markdown_path = convert_pdf_with_mineru_api(pdf_path, output_dir, **kwargs)
        result['markdown_path'] = markdown_path
        result['success'] = True
        
        # 提取DOI
        doi = extract_doi_from_pdf(pdf_path)
        if doi:
            result['doi'] = doi
            
        # 检查是否有图片文件夹
        output_path = Path(output_dir)
        images_dir = output_path / 'images'
        if images_dir.exists():
            image_files = list(images_dir.glob('*'))
            result['image_count'] = len(image_files)
            result['images_dir'] = str(images_dir)
        
        logger.info(f"PDF处理完成: {pdf_path}")
        return result
        
    except Exception as e:
        logger.error(f"PDF处理失败: {e}")
        result['success'] = False
        result['error'] = str(e)
        return result

def extract_images(pdf_path: str, output_dir: str):
    """
    从PDF中提取图像（保留原有函数以备兼容）
    注意：API模式下，图片已经在API处理过程中提取
    """
    logger.info("使用API模式，图片已在服务端提取")
    return []

def extract_tables(pdf_path: str):
    """
    从PDF中提取表格（保留原有函数以备兼容）
    注意：API模式下，表格已经在API处理过程中提取
    """
    logger.info("使用API模式，表格已在服务端提取")
    return []

def convert_pdf_to_markdown(pdf_path: str, output_dir: Optional[str] = None) -> str:
    """
    PDF转Markdown的统一入口函数
    使用MinerU API进行处理
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        
    Returns:
        生成的Markdown文件路径
    """
    logger.info("使用MinerU API进行PDF处理")
    if output_dir is None:
        # 如果没有指定输出目录，创建一个默认的
        pdf_name = Path(pdf_path).stem
        output_dir = f"output/{pdf_name}"
    return convert_pdf_with_mineru_api(pdf_path, output_dir) 