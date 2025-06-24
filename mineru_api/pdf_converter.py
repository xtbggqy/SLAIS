"""PDF转Markdown转换工具

整合版本：包含配置管理、API客户端和主程序功能
从.env配置的目录读取PDF文件，使用MinerU API转换为Markdown格式
"""

import os
import sys
import requests
import time
import zipfile
import io
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# 加载.env文件
load_dotenv(override=True)

class Config:
    """配置管理类"""
    
    # MinerU API配置
    MINERU_API_TOKEN: str = os.getenv('MINERU_API_TOKEN', '')
    MINERU_BASE_URL: str = os.getenv('MINERU_BASE_URL', 'https://mineru.net/api/v4')
    
    # 文件路径配置
    PDF_SOURCE_PATH: str = os.getenv('PDF_SOURCE_PATH', './input')
    MARKDOWN_OUTPUT_PATH: str = os.getenv('MARKDOWN_OUTPUT_PATH', './output')
    
    # API配置
    MAX_FILE_SIZE: int = int(os.getenv('MAX_FILE_SIZE', '200'))  # MB
    MAX_PAGES: int = int(os.getenv('MAX_PAGES', '600'))
    REQUEST_TIMEOUT: int = int(os.getenv('REQUEST_TIMEOUT', '30'))  # 秒
    MAX_RETRIES: int = int(os.getenv('MAX_RETRIES', '3'))
    
    @classmethod
    def validate_config(cls) -> bool:
        """验证配置是否完整
        
        Returns:
            bool: 配置是否有效
        """
        if not cls.MINERU_API_TOKEN:
            print("错误: 未设置 MINERU_API_TOKEN")
            return False
            
        # 创建必要的目录
        Path(cls.PDF_SOURCE_PATH).mkdir(parents=True, exist_ok=True)
        Path(cls.MARKDOWN_OUTPUT_PATH).mkdir(parents=True, exist_ok=True)
        
        return True
    
    @classmethod
    def get_pdf_files(cls) -> List[Path]:
        """获取源目录中的所有PDF文件
        
        Returns:
            List[Path]: PDF文件路径列表
        """
        source_path = Path(cls.PDF_SOURCE_PATH)
        if not source_path.exists():
            return []
            
        return list(source_path.glob('*.pdf'))
    
    @classmethod
    def get_output_path(cls, filename: str) -> Path:
        """获取输出文件路径
        
        Args:
            filename: 原始文件名
            
        Returns:
            Path: 输出文件路径
        """
        output_dir = Path(cls.MARKDOWN_OUTPUT_PATH)
        # 为每个PDF创建独立的文件夹
        pdf_name = Path(filename).stem
        pdf_output_dir = output_dir / pdf_name
        pdf_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 将PDF扩展名替换为md
        md_filename = pdf_name + '.md'
        return pdf_output_dir / md_filename

class MinerUClient:
    """MinerU API客户端类"""
    
    def __init__(self):
        """初始化客户端"""
        self.base_url = Config.MINERU_BASE_URL
        self.token = Config.MINERU_API_TOKEN
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        
    def upload_local_file(self, file_path: Path, **kwargs) -> Optional[str]:
        """上传本地文件进行解析
        
        Args:
            file_path: 本地文件路径
            **kwargs: 其他参数
            
        Returns:
            Optional[str]: 批次ID，失败返回None
        """
        # 首先申请上传链接
        upload_url = self._get_upload_url(file_path.name, **kwargs)
        if not upload_url:
            return None
            
        # 上传文件
        if not self._upload_file_to_url(file_path, upload_url['file_url']):
            return None
            
        return upload_url['batch_id']
    
    def _get_upload_url(self, filename: str, **kwargs) -> Optional[Dict[str, Any]]:
        """获取文件上传链接
        
        Args:
            filename: 文件名
            **kwargs: 其他参数
            
        Returns:
            Optional[Dict]: 包含上传链接和batch_id的字典
        """
        url = f"{self.base_url}/file-urls/batch"
        
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
        
        try:
            response = requests.post(url, headers=self.headers, json=data,
                                   timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') == 0:
                batch_id = result['data']['batch_id']
                file_url = result['data']['file_urls'][0]
                print(f"获取上传链接成功，批次ID: {batch_id}")
                return {'batch_id': batch_id, 'file_url': file_url}
            else:
                print(f"获取上传链接失败: {result.get('msg', '未知错误')}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"网络请求失败: {e}")
            return None
        except Exception as e:
            print(f"获取上传链接时发生错误: {e}")
            return None
    
    def _upload_file_to_url(self, file_path: Path, upload_url: str) -> bool:
        """将文件上传到指定URL
        
        Args:
            file_path: 文件路径
            upload_url: 上传URL
            
        Returns:
            bool: 上传是否成功
        """
        try:
            with open(file_path, 'rb') as f:
                response = requests.put(upload_url, data=f, 
                                      timeout=Config.REQUEST_TIMEOUT)
                response.raise_for_status()
                print(f"文件 {file_path.name} 上传成功")
                return True
                
        except requests.exceptions.RequestException as e:
            print(f"文件上传失败: {e}")
            return False
        except Exception as e:
            print(f"上传文件时发生错误: {e}")
            return False
    
    def get_batch_result(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """获取批量任务结果
        
        Args:
            batch_id: 批次ID
            
        Returns:
            Optional[Dict]: 批量任务结果，失败返回None
        """
        url = f"{self.base_url}/extract-results/batch/{batch_id}"
        
        try:
            response = requests.get(url, headers=self.headers,
                                  timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') == 0:
                return result['data']
            else:
                print(f"获取批量结果失败: {result.get('msg', '未知错误')}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"网络请求失败: {e}")
            return None
        except Exception as e:
            print(f"获取批量结果时发生错误: {e}")
            return None
    
    def wait_for_completion(self, batch_id: str, max_wait_time: int = 600) -> Optional[str]:
        """等待批量任务完成并返回结果URL
        
        Args:
            batch_id: 批次ID
            max_wait_time: 最大等待时间(秒)
            
        Returns:
            Optional[str]: 结果下载URL，失败返回None
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            result = self.get_batch_result(batch_id)
            if result and result.get('extract_result'):
                extract_result = result['extract_result'][0]
                state = extract_result.get('state')
                
                if state == 'done':
                    print("批量任务完成")
                    return extract_result.get('full_zip_url')
                elif state == 'failed':
                    print(f"批量任务失败: {extract_result.get('err_msg', '未知错误')}")
                    return None
                else:
                    print(f"批量任务状态: {state}")
            
            time.sleep(10)  # 等待10秒后再次检查
        
        print(f"任务超时，等待时间超过 {max_wait_time} 秒")
        return None
    
    def download_result(self, download_url: str, output_path: Path) -> bool:
        """下载解析结果
        
        Args:
            download_url: 下载URL
            output_path: 输出文件路径
            
        Returns:
            bool: 下载是否成功
        """
        try:
            response = requests.get(download_url, timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # 解压ZIP文件并提取所有内容
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                # 获取输出目录（PDF专用文件夹）
                output_dir = output_path.parent
                
                # 查找markdown文件
                md_files = [f for f in zip_file.namelist() if f.endswith('.md')]
                
                if md_files:
                    # 提取第一个markdown文件
                    md_content = zip_file.read(md_files[0]).decode('utf-8')
                    
                    # 保存到指定路径
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(md_content)
                    
                    print(f"Markdown文件已保存到: {output_path}")
                    
                    # 提取images文件夹到PDF专用文件夹中（如果存在）
                    image_files = [f for f in zip_file.namelist() if f.startswith('images/') and not f.endswith('/')]
                    
                    if image_files:
                        # 在PDF专用文件夹中创建images目录
                        images_dir = output_dir / 'images'
                        images_dir.mkdir(exist_ok=True)
                        
                        for image_file in image_files:
                            # 提取图片文件
                            image_content = zip_file.read(image_file)
                            image_name = Path(image_file).name
                            image_path = images_dir / image_name
                            
                            with open(image_path, 'wb') as f:
                                f.write(image_content)
                        
                        print(f"已提取 {len(image_files)} 个图片文件到: {images_dir}")
                    else:
                        print("ZIP文件中未找到图片文件")
                    
                    return True
                else:
                    print("ZIP文件中未找到Markdown文件")
                    return False
                    
        except requests.exceptions.RequestException as e:
            print(f"下载失败: {e}")
            return False
        except zipfile.BadZipFile:
            print("下载的文件不是有效的ZIP格式")
            return False
        except Exception as e:
            print(f"下载和处理结果时发生错误: {e}")
            return False

def validate_environment() -> bool:
    """验证运行环境和配置
    
    Returns:
        bool: 环境是否有效
    """
    print("正在验证环境配置...")
    
    # 验证配置
    if not Config.validate_config():
        print("配置验证失败，请检查.env文件")
        return False
    
    # 检查源目录
    source_path = Path(Config.PDF_SOURCE_PATH)
    if not source_path.exists():
        print(f"源目录不存在: {source_path}")
        print(f"请创建目录并放入PDF文件: {source_path}")
        return False
    
    # 检查PDF文件
    pdf_files = Config.get_pdf_files()
    if not pdf_files:
        print(f"在源目录中未找到PDF文件: {source_path}")
        print("请在源目录中放入需要转换的PDF文件")
        return False
    
    print(f"找到 {len(pdf_files)} 个PDF文件待处理")
    for pdf_file in pdf_files:
        print(f"  - {pdf_file.name}")
    
    return True

def process_single_pdf(client: MinerUClient, pdf_path: Path) -> bool:
    """处理单个PDF文件
    
    Args:
        client: MinerU客户端
        pdf_path: PDF文件路径
        
    Returns:
        bool: 处理是否成功
    """
    print(f"\n开始处理文件: {pdf_path.name}")
    
    # 检查文件大小
    file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
    if file_size_mb > Config.MAX_FILE_SIZE:
        print(f"文件过大 ({file_size_mb:.1f}MB)，超过限制 ({Config.MAX_FILE_SIZE}MB)")
        return False
    
    # 上传文件并创建任务
    print("正在上传文件...")
    batch_id = client.upload_local_file(
        pdf_path,
        is_ocr=True,
        enable_formula=False,
        enable_table=True,
        language='ch'
    )
    
    if not batch_id:
        print("文件上传失败")
        return False
    
    # 等待处理完成
    print("正在等待处理完成...")
    download_url = client.wait_for_completion(batch_id)
    
    if not download_url:
        print("处理失败或超时")
        return False
    
    # 下载结果
    output_path = Config.get_output_path(pdf_path.name)
    print(f"正在下载结果到: {output_path}")
    
    if client.download_result(download_url, output_path):
        print(f"✅ {pdf_path.name} 转换成功")
        return True
    else:
        print(f"❌ {pdf_path.name} 下载失败")
        return False

def process_all_pdfs() -> None:
    """处理所有PDF文件"""
    print("=" * 60)
    print("PDF转Markdown转换工具")
    print("=" * 60)
    
    # 验证环境
    if not validate_environment():
        sys.exit(1)
    
    # 初始化客户端
    print("\n正在初始化MinerU客户端...")
    client = MinerUClient()
    
    # 获取所有PDF文件
    pdf_files = Config.get_pdf_files()
    
    # 处理统计
    total_files = len(pdf_files)
    success_count = 0
    failed_files = []
    
    print(f"\n开始批量处理 {total_files} 个文件...")
    
    # 逐个处理文件
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{total_files}] 处理进度")
        
        try:
            if process_single_pdf(client, pdf_path):
                success_count += 1
            else:
                failed_files.append(pdf_path.name)
        except KeyboardInterrupt:
            print("\n用户中断操作")
            break
        except Exception as e:
            print(f"处理 {pdf_path.name} 时发生未知错误: {e}")
            failed_files.append(pdf_path.name)
    
    # 输出处理结果
    print("\n" + "=" * 60)
    print("处理完成")
    print("=" * 60)
    print(f"总文件数: {total_files}")
    print(f"成功转换: {success_count}")
    print(f"失败文件: {len(failed_files)}")
    
    if failed_files:
        print("\n失败的文件:")
        for filename in failed_files:
            print(f"  - {filename}")
    
    if success_count > 0:
        print(f"\n✅ 转换后的Markdown文件保存在: {Config.MARKDOWN_OUTPUT_PATH}")

def main():
    """主函数"""
    try:
        process_all_pdfs()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行时发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()