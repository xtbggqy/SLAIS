"""MinerU API客户端

使用MinerU的在线API服务进行PDF解析
"""

import os
import time
import requests
import zipfile
import io
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from slais.utils.logging_utils import logger

class MinerUAPIClient:
    """MinerU API客户端 - 基于requests的同步版本"""
    
    def __init__(self, api_key: str, api_base: str = "https://mineru.net/api/v4"):
        """初始化客户端
        
        Args:
            api_key: API密钥
            api_base: API基础URL
        """
        self.api_key = api_key
        self.api_base = api_base.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {api_key}'
        }
        self.batch_id = None
        self.max_retries = 3
        self.retry_delay = 5
        self.request_timeout = 30
        logger.info(f"MinerU API客户端已初始化，API地址: {api_base}")
    
    def _retry_on_error(self, func, *args, max_retries=None, **kwargs):
        """重试机制包装器"""
        max_retries = max_retries or self.max_retries
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                # 检查是否是可重试的错误
                if "SignatureDoesNotMatch" in str(e) or "Forbidden" in str(e):
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"遇到认证错误，第 {attempt + 1}/{max_retries + 1} 次重试 (等待 {wait_time}s): {e}")
                    if attempt < max_retries:
                        time.sleep(wait_time)
                        continue
                
                # 其他错误也尝试重试
                if attempt < max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"请求失败，第 {attempt + 1}/{max_retries + 1} 次重试 (等待 {wait_time}s): {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"所有重试都失败了: {e}")
                    
        raise last_exception
    
    def _get_upload_url(self, filename: str, **kwargs) -> Dict[str, str]:
        """获取文件上传链接"""
        url = f"{self.api_base}/file-urls/batch"
        
        data = {
            "enable_formula": kwargs.get('enable_formula', False),
            "language": kwargs.get('language', 'ch'),
            "enable_table": kwargs.get('enable_table', True),
            "files": [
                {
                    "name": filename,
                    "is_ocr": kwargs.get('is_ocr', True)
                }
            ]
        }
        
        def _request():
            headers = self.headers.copy()
            headers['Content-Type'] = 'application/json'
            response = requests.post(url, headers=headers, json=data, timeout=self.request_timeout)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') != 0:
                raise Exception(f"API返回错误: {result.get('msg', 'Unknown error')}")
            
            batch_id = result['data']['batch_id']
            file_url = result['data']['file_urls'][0]
            logger.info(f"获取上传链接成功，批次ID: {batch_id}")
            return {'batch_id': batch_id, 'file_url': file_url}
        
        return self._retry_on_error(_request)
    
    def _upload_file_to_url(self, file_path: str, upload_url: str) -> bool:
        """将文件上传到指定URL"""
        
        def _upload():
            with open(file_path, 'rb') as f:
                # 阿里云OSS上传时不需要设置Content-Type，让OSS自动检测
                response = requests.put(upload_url, data=f, timeout=self.request_timeout)
                response.raise_for_status()
                logger.info(f"文件 {Path(file_path).name} 上传成功")
                return True
        
        return self._retry_on_error(_upload)
    
    def get_batch_result(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """获取批量任务结果"""
        url = f"{self.api_base}/extract-results/batch/{batch_id}"
        
        def _request():
            headers = self.headers.copy()
            response = requests.get(url, headers=headers, timeout=self.request_timeout)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') != 0:
                raise Exception(f"获取批量结果失败: {result.get('msg', 'Unknown error')}")
            
            return result['data']
        
        return self._retry_on_error(_request)
    
    def wait_for_completion(self, batch_id: str, max_wait_time: int = 3600) -> Optional[str]:
        """等待批量任务完成并返回结果URL"""
        start_time = time.time()
        check_interval = 10
        last_status_log_time = 0
        
        logger.info(f"开始等待MinerU API处理文件，批次ID: {batch_id}")
        logger.info(f"最大等待时间: {max_wait_time//60} 分钟，检查间隔: {check_interval} 秒")
        
        while time.time() - start_time < max_wait_time:
            try:
                result = self.get_batch_result(batch_id)
                if result and result.get('extract_result'):
                    extract_result = result['extract_result'][0]
                    state = extract_result.get('state')
                    current_time = time.time()
                    
                    if state == 'done':
                        logger.info("🎉 PDF处理完成！")
                        return extract_result.get('full_zip_url')
                    elif state == 'failed':
                        error_msg = extract_result.get('err_msg', 'Unknown error')
                        logger.error(f"❌ PDF处理失败: {error_msg}")
                        raise Exception(f"PDF处理失败: {error_msg}")
                    elif state in ['pending', 'running', 'converting']:
                        # 只在间隔足够长时才记录状态，避免日志过多
                        if current_time - last_status_log_time >= 30:  # 30秒记录一次
                            if 'extract_progress' in extract_result:
                                progress = extract_result['extract_progress']
                                extracted = progress.get('extracted_pages', 0)
                                total = progress.get('total_pages', 0)
                                percentage = (extracted / total * 100) if total > 0 else 0
                                elapsed_time = int(current_time - start_time)
                                logger.info(f"📄 PDF处理中: {extracted}/{total} 页 ({percentage:.1f}%)，已用时: {elapsed_time//60}m{elapsed_time%60}s")
                            else:
                                elapsed_time = int(current_time - start_time)
                                logger.info(f"⏳ PDF处理状态: {state}，已用时: {elapsed_time//60}m{elapsed_time%60}s")
                            last_status_log_time = current_time
                    else:
                        logger.warning(f"⚠️  未知的处理状态: {state}")
                
            except Exception as e:
                if "PDF处理失败" in str(e):
                    # 这些是最终错误，不重试
                    raise
                logger.warning(f"检查处理状态时出错: {e}，将重试...")
            
            time.sleep(check_interval)
        
        elapsed_minutes = int((time.time() - start_time) / 60)
        logger.error(f"❌ PDF处理超时！已等待 {elapsed_minutes} 分钟")
        raise Exception(f"PDF处理超时，已等待 {elapsed_minutes} 分钟")
    
    def download_result(self, download_url: str, output_dir: str) -> str:
        """下载解析结果"""
        
        def _download():
            # 文件下载使用更长的超时时间
            download_timeout = 300  # 5分钟
            response = requests.get(download_url, timeout=download_timeout)
            response.raise_for_status()
            
            # 创建临时目录用于解压
            with tempfile.TemporaryDirectory() as temp_dir:
                # 解压ZIP文件
                with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                    zip_file.extractall(temp_dir)
                    
                    # 查找markdown文件
                    md_files = []
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if file.endswith('.md'):
                                md_files.append(os.path.join(root, file))
                    
                    if not md_files:
                        raise Exception("ZIP文件中未找到Markdown文件")
                    
                    # 创建输出目录
                    output_path = Path(output_dir)
                    output_path.mkdir(parents=True, exist_ok=True)
                    
                    # 复制markdown文件，使用PDF文件名作为输出文件名
                    src_md = md_files[0]
                    pdf_name = Path(self.current_pdf_name).stem if hasattr(self, 'current_pdf_name') else 'converted'
                    dst_md = output_path / f"{pdf_name}.md"
                    
                    with open(src_md, 'r', encoding='utf-8') as f:
                        content = f.read()
                    with open(dst_md, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    logger.info(f"Markdown文件已保存到: {dst_md}")
                    
                    # 复制images文件夹（如果存在）
                    images_src = None
                    for root, dirs, files in os.walk(temp_dir):
                        if 'images' in dirs:
                            images_src = os.path.join(root, 'images')
                            break
                    
                    if images_src and os.path.exists(images_src):
                        images_dst = output_path / 'images'
                        images_dst.mkdir(exist_ok=True)
                        
                        image_count = 0
                        for file in os.listdir(images_src):
                            src_file = os.path.join(images_src, file)
                            dst_file = images_dst / file
                            if os.path.isfile(src_file):
                                with open(src_file, 'rb') as f:
                                    content = f.read()
                                with open(dst_file, 'wb') as f:
                                    f.write(content)
                                image_count += 1
                        
                        if image_count > 0:
                            logger.info(f"已提取 {image_count} 个图片文件到: {images_dst}")
                    
                    return str(dst_md)
        
        return self._retry_on_error(_download)
    
    def upload_file_and_extract(self, pdf_path: str, output_dir: str, **kwargs) -> str:
        """上传文件并进行解析的完整流程"""
        logger.info(f"开始处理PDF文件: {pdf_path}")
        
        # 检查文件
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"文件不存在: {pdf_path}")
        
        # 保存PDF文件名以便在下载时使用
        self.current_pdf_name = Path(pdf_path).name
        
        file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        logger.info(f"文件大小: {file_size_mb:.2f} MB")
        
        # 1. 获取上传链接
        logger.info("正在获取上传链接...")
        upload_info = self._get_upload_url(Path(pdf_path).name, **kwargs)
        self.batch_id = upload_info['batch_id']
        upload_url = upload_info['file_url']
        
        # 2. 上传文件
        logger.info("正在上传文件...")
        self._upload_file_to_url(pdf_path, upload_url)
        
        # 3. 等待处理完成
        logger.info("正在等待处理完成...")
        download_url = self.wait_for_completion(self.batch_id, kwargs.get('max_wait_time', 3600))
        
        if not download_url:
            raise Exception("处理失败或超时")
        
        # 4. 下载结果
        logger.info("正在下载结果...")
        result_path = self.download_result(download_url, output_dir)
        
        logger.info(f"✅ PDF处理完成！结果已保存到: {result_path}")
        return result_path

# 保持向后兼容的别名
class MinerUClient(MinerUAPIClient):
    """向后兼容的别名"""
    pass 