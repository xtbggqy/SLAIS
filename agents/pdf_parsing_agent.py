import os
from pathlib import Path
from slais.utils.logging_utils import logger
from slais.pdf_utils import convert_pdf_to_markdown, extract_images
from slais import config

class PDFParsingAgent:
    def __init__(self):
        pass

    async def extract_content(self, pdf_path: str) -> str:
        """提取PDF内容
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            PDF内容的Markdown格式
        """
        logger.info(f"开始解析PDF文件: {pdf_path}")
        
        # 获取PDF文件名（不含扩展名）
        pdf_filename = os.path.basename(pdf_path)
        pdf_name_without_ext = os.path.splitext(pdf_filename)[0]
        
        # 构建预期的Markdown文件输出路径
        output_dir = Path(config.OUTPUT_BASE_DIR) / pdf_name_without_ext
        markdown_dir = output_dir / f"{pdf_name_without_ext}_markdown"
        expected_md_filepath = markdown_dir / f"{pdf_name_without_ext}.md"

        # 检查是否已存在Markdown文件
        if expected_md_filepath.exists() and expected_md_filepath.is_file():
            logger.info(f"找到已存在的Markdown文件: {expected_md_filepath}。将直接读取此文件。")
            try:
                with open(expected_md_filepath, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
                logger.info(f"成功读取已存在的Markdown文件内容，长度: {len(markdown_content)}。")
                return markdown_content
            except Exception as e:
                logger.error(f"读取已存在的Markdown文件 {expected_md_filepath} 失败: {e}。将尝试重新转换PDF。")
        else:
            logger.info(f"未找到预期的Markdown文件 {expected_md_filepath} 或它不是一个文件。将执行PDF转换。")

        # 创建最终输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        try:
            # 调用转换功能，直接指定最终输出目录
            md_file_path = await convert_pdf_to_markdown(pdf_path, output_dir=output_dir)
            
            if md_file_path and Path(md_file_path).exists():
                with open(md_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"PDF内容成功转换为Markdown，并已读取。路径: {md_file_path}, 长度: {len(content)}")
                return content
            else:
                logger.error(f"PDF转换为Markdown失败或未返回有效路径: {md_file_path}")
                return ""
        except Exception as e:
            logger.error(f"从PDF '{pdf_path}' 提取内容时发生错误: {e}")
            import traceback
            logger.debug(f"错误详情: {traceback.format_exc()}")
            return ""

    async def extract_images(self, pdf_path: str, output_dir: str) -> list:
        """
        提取PDF中的图片到指定目录。
        Args:
            pdf_path: PDF文件路径
            output_dir: 图片输出目录
        Returns:
            图片文件路径列表
        """
        # extract_images 是同步函数，这里直接调用即可
        return extract_images(pdf_path, output_dir)
