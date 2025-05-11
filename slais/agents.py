import asyncio
from abc import ABC, abstractmethod
import logging  # 添加logging模块导入
from typing import List, Optional, Dict, Any
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from slais import config
from slais.pdf_utils import convert_pdf_to_markdown
from slais.pubmed_client import PubMedClient, ArticleDetails
from slais.semantic_scholar_client import SemanticScholarClient
from slais.utils.logging_utils import logger
from slais.prompts import (
    METHODOLOGY_ANALYSIS_PROMPT,
    INNOVATION_EXTRACTION_PROMPT,
    QA_GENERATION_PROMPT
)
import json
import re
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class ResearchAgent(ABC):
    def __init__(self, llm):
        self.chain = self._build_chain(llm)

    @abstractmethod
    def _build_chain(self, llm):
        pass

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
        from slais.utils.logging_utils import logger
        import os
        from pathlib import Path
        
        logger.info(f"开始解析PDF文件: {pdf_path}")
        
        # 获取PDF文件名（不含扩展名）
        pdf_filename = os.path.basename(pdf_path)
        pdf_name_without_ext = os.path.splitext(pdf_filename)[0]
        
        # 创建最终输出目录
        output_dir = os.path.join(config.OUTPUT_BASE_DIR, pdf_name_without_ext)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 调用转换功能，直接指定最终输出目录
        md_file_path = await convert_pdf_to_markdown(pdf_path, output_dir=output_dir)
        
        # 如果返回的是文件路径，读取文件内容
        if md_file_path and os.path.isfile(md_file_path):
            try:
                with open(md_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                logger.info(f"PDF解析完成，内容长度: {len(content)} 字符")
                return content
            except Exception as e:
                logger.error(f"读取Markdown文件失败: {e}")
                return ""
        else:
            # 如果convert_pdf_to_markdown直接返回了内容字符串而不是路径
            if isinstance(md_file_path, str) and len(md_file_path) > 100:  # 假设内容长度>100是文本内容
                logger.info(f"PDF解析完成，内容长度: {len(md_file_path)} 字符")
                return md_file_path
            else:
                logger.warning("PDF转换未返回有效的Markdown文件内容或路径")
                return ""

class MetadataFetchingAgent:
    def __init__(self):
        self.pubmed_client = PubMedClient()
        self.s2_client = SemanticScholarClient()

    async def fetch_metadata(self, doi: str, email: str) -> Dict[str, Any]:
        original_s2_info: Optional[Dict[str, Any]] = None
        original_pubmed_info: Optional[ArticleDetails] = None

        logger.info(f"从配置中获取的DOI: {doi}")
        logger.info(f"从配置中获取的邮箱: {email}")

        logger.info(f"正在从 Semantic Scholar 获取原始文章 (DOI: {doi}) 的信息...")
        original_s2_info = await self.s2_client.get_paper_details_by_doi(doi)

        if original_s2_info and original_s2_info.get('paperId'):
            logger.info(f"成功从S2获取原始文章信息 (S2 PaperID: {original_s2_info['paperId']})")
            s2_paper_id_original = original_s2_info['paperId']

            s2_external_ids = original_s2_info.get('externalIds', {})
            pmid_from_s2 = s2_external_ids.get('PubMed') if isinstance(s2_external_ids, dict) else None

            if pmid_from_s2:
                logger.info(f"S2提供了PMID: {pmid_from_s2}。正在从PubMed获取/核实...")
                original_pubmed_info = await self.pubmed_client.get_article_details_by_pmid(pmid_from_s2, email)
                if original_pubmed_info:
                    logger.info(f"成功从PubMed获取PMID {pmid_from_s2} 的信息。")
                else:
                    logger.warning(f"未能从PubMed获取PMID {pmid_from_s2} 的信息，将主要依赖S2数据。")
            else:
                logger.info(f"S2未提供PMID。尝试用DOI从PubMed获取原始文章信息...")
                original_pubmed_info = await self.pubmed_client.get_article_details(doi, email)
                if original_pubmed_info:
                    logger.info(f"成功从PubMed获取DOI {doi} 的信息 (PMID: {original_pubmed_info.get('pmid')})。")
                else:
                    logger.warning(f"也未能从PubMed通过DOI获取原始文章信息。")
        else:
            logger.warning(f"未能从S2获取原始文章信息。尝试直接从PubMed获取...")
            original_pubmed_info = await self.pubmed_client.get_article_details(doi, email)
            if original_pubmed_info:
                logger.info(f"成功从PubMed获取DOI {doi} 的信息 (PMID: {original_pubmed_info.get('pmid')})。")
            else:
                logger.error(f"也未能从PubMed通过DOI获取原始文章信息。处理可能无法继续。")

        metadata = {
            "s2_info": original_s2_info,
            "pubmed_info": original_pubmed_info
        }
        return metadata
        
    async def fetch_related_articles(self, pmid: str, email: str) -> List[ArticleDetails]:
        """
        获取PubMed中与特定PMID相关的文章列表
        
        Args:
            pmid: PubMed文章ID
            email: NCBI E-utils请求的邮箱地址
            
        Returns:
            相关文章列表
        """
        logger.info(f"正在从PubMed获取PMID:{pmid}的相关文章...")
        related_articles = []
        try:
            related_articles = await self.pubmed_client.get_related_articles(pmid, email)
            logger.info(f"成功获取 {len(related_articles)} 篇PubMed相关文章")
        except Exception as e:
            logger.error(f"获取PubMed相关文章时出错: {e}")
        return related_articles
    
    async def fetch_references(self, paper_id: str, email: str) -> Dict[str, Any]:
        """
        获取Semantic Scholar中特定论文的参考文献，并补充PubMed信息
        
        Args:
            paper_id: Semantic Scholar论文ID
            email: NCBI E-utils请求的邮箱地址
            
        Returns:
            包含参考文献信息的字典
        """
        result = {
            "reference_dois": [],
            "s2_details": [],
            "pubmed_details": []
        }
        
        logger.info(f"正在从Semantic Scholar获取论文ID:{paper_id}的参考文献...")
        try:
            # 1. 获取参考文献DOI列表
            result["reference_dois"] = await self.s2_client.get_references_by_paper_id(paper_id)
            
            if result["reference_dois"]:
                # 2. 批量获取参考文献的S2详情
                raw_details = await self.s2_client.batch_get_paper_details_by_dois(result["reference_dois"])
                # 确保只保留有效的字典对象
                result["s2_details"] = [ref for ref in raw_details if isinstance(ref, dict)]
                
                # 3. 提取PMID并获取PubMed信息
                pmids = []
                for ref in result["s2_details"]:
                    if ref.get('externalIds') and isinstance(ref['externalIds'], dict) and ref['externalIds'].get('PubMed'):
                        pmids.append(ref['externalIds'].get('PubMed'))
                
                if pmids:
                    result["pubmed_details"] = await self.pubmed_client.batch_get_article_details_by_pmids(pmids, email)
                    
        except Exception as e:
            logger.error(f"获取参考文献时出错: {e}")
            import traceback
            logger.debug(f"错误详情: {traceback.format_exc()}")
            
        return result

class MethodologyAnalysisAgent(ResearchAgent):
    def __init__(self, llm, api_base_url=None): # api_base_url 参数保留但不再使用，以保持接口一致性
        super().__init__(llm)

    def _build_chain(self, llm):
        return LLMChain(
            llm=llm,
            prompt=PromptTemplate(
                template=METHODOLOGY_ANALYSIS_PROMPT,  # 使用导入的提示词
                input_variables=["content"]
            )
        )

    async def analyze_methodology(self, content: str) -> Dict[str, Any]:
        try:
            # 截取内容防止过长
            truncated_content = content[:15000] if len(content) > 15000 else content
            logger.info(f"分析文献方法，内容长度: {len(truncated_content)} 字符")
            
            # 使用ainvoke并明确指定参数
            result = await self.chain.ainvoke({"content": truncated_content})
            response_text = result.get("text", "")
            
            # 记录原始响应用于调试
            logger.debug(f"方法分析原始响应: {response_text[:200]}...")
            
            # 尝试解析JSON响应，处理可能的格式问题
            try:
                # 首先尝试直接解析
                return json.loads(response_text)
            except json.JSONDecodeError:
                # 如果失败，尝试清理JSON格式后再解析
                try:
                    # 提取可能的JSON部分
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        cleaned_json = json_match.group(0)
                        return json.loads(cleaned_json)
                    else:
                        raise ValueError("无法提取JSON格式内容")
                except Exception as inner_e:
                    logger.error(f"JSON清理后仍无法解析: {inner_e}. 原始响应: {response_text[:200]}...")
                    return {"error": f"无法解析响应: {str(inner_e)}", "方法类型": "未知", "关键技术": "未知", "创新方法": "未知"}
        except Exception as e:
            logger.error(f"方法分析时发生错误: {str(e)}")
            return {"error": str(e), "方法类型": "未知", "关键技术": "未知", "创新方法": "未知"}

class InnovationExtractionAgent(ResearchAgent):
    def __init__(self, llm, api_base_url=None): # api_base_url 参数保留但不再使用
        super().__init__(llm)

    def _build_chain(self, llm):
        return LLMChain(
            llm=llm,
            prompt=PromptTemplate(
                template=INNOVATION_EXTRACTION_PROMPT,  # 使用导入的提示词
                input_variables=["content"]
            )
        )

    async def extract_innovations(self, content: str) -> Dict[str, Any]:
        try:
            truncated_content = content[:15000] if len(content) > 15000 else content
            logger.info(f"提取创新点，内容长度: {len(truncated_content)} 字符")
            
            result = await self.chain.ainvoke({"content": truncated_content})
            response_text = result.get("text", "")
            
            logger.debug(f"创新点提取原始响应: {response_text[:200]}...")
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                try:
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        cleaned_json = json_match.group(0)
                        return json.loads(cleaned_json)
                    else:
                        raise ValueError("无法提取JSON格式内容")
                except Exception as inner_e:
                    logger.error(f"JSON清理后仍无法解析: {inner_e}. 原始响应: {response_text[:200]}...")
                    return {"error": f"无法解析响应: {str(inner_e)}", "核心创新": "未知", "潜在应用": "未知"}
        except Exception as e:
            logger.error(f"创新点提取时发生错误: {str(e)}")
            return {"error": str(e), "核心创新": "未知", "潜在应用": "未知"}

class QAGenerationAgent(ResearchAgent):
    def __init__(self, llm, api_base_url=None): # api_base_url 参数保留但不再使用
        super().__init__(llm)

    def _build_chain(self, llm):
        return LLMChain(
            llm=llm,
            prompt=PromptTemplate(
                template=QA_GENERATION_PROMPT,  # 使用导入的提示词
                input_variables=["content"]
            )
        )

    async def generate_qa(self, content: str) -> Dict[str, Any]:
        try:
            truncated_content = content[:15000] if len(content) > 15000 else content
            logger.info(f"生成问答，内容长度: {len(truncated_content)} 字符")
            
            result = await self.chain.ainvoke({"content": truncated_content})
            response_text = result.get("text", "")
            
            logger.debug(f"问答生成原始响应: {response_text[:200]}...")
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                try:
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        cleaned_json = json_match.group(0)
                        return json.loads(cleaned_json)
                    else:
                        raise ValueError("无法提取JSON格式内容")
                except Exception as inner_e:
                    logger.error(f"JSON清理后仍无法解析: {inner_e}. 原始响应: {response_text[:200]}...")
                    return {"error": f"无法解析响应: {str(inner_e)}", 
                            "问题1": "未能生成问题", "答案1": "", 
                            "问题2": "", "答案2": "", 
                            "问题3": "", "答案3": ""}
        except Exception as e:
            logger.error(f"问答生成时发生错误: {str(e)}")
            return {"error": str(e), "问题1": "未能生成问题", "答案1": "", 
                    "问题2": "", "答案2": "", "问题3": "", "答案3": ""}
