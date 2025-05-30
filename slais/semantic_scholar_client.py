import asyncio
import random
import time
import aiohttp
from typing import List, Optional, Dict, Any, Union, Tuple, Callable
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log, retry_if_exception_type
import logging
from urllib.parse import quote
import json

from .utils.logging_utils import logger
from . import config

# 速率限制控制 - 令牌桶实现
class TokenBucket:
    def __init__(self, rate_per_minute: float, burst_limit: Optional[int] = None):
        self.rate_per_second = rate_per_minute / 60.0
        self.burst_limit = burst_limit if burst_limit is not None else max(10, int(rate_per_minute / 3))
        self.tokens = float(self.burst_limit)
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def get_token(self) -> float:
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            new_tokens = elapsed * self.rate_per_second
            self.tokens = min(float(self.burst_limit), self.tokens + new_tokens)
            self.last_update = now
            
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0
            else:
                wait_time = (1.0 - self.tokens) / self.rate_per_second
                return wait_time
                
    async def wait_for_token(self) -> None:
        wait_time = await self.get_token()
        if wait_time > 0:
            logger.debug(f"[S2 TokenBucket] 等待 {wait_time:.2f} 秒")
            await asyncio.sleep(wait_time)

class SemanticScholarClient:
    """Semantic Scholar API 客户端 - 已优化版本"""
    def __init__(self, 
                api_key: Optional[str] = None, 
                timeout: Optional[float] = None,
                retry_count: Optional[int] = None,
                batch_size: Optional[int] = None):
        """
        初始化 Semantic Scholar API 客户端
        
        Args:
            api_key: Semantic Scholar API 密钥 (可选)
            timeout: 请求超时时间 (秒)
            retry_count: 请求重试次数
            batch_size: 批量请求的大小 (每批DOI数量)
        """
        self.api_key = api_key or config.settings.SEMANTIC_SCHOLAR_API_KEY
        self.base_url = config.settings.SEMANTIC_SCHOLAR_API_BASE_URL
        self.graph_api_base_url = config.settings.SEMANTIC_SCHOLAR_GRAPH_API_BASE_URL
        self.timeout = timeout or config.settings.SEMANTIC_SCHOLAR_TIMEOUT
        self.retry_count = retry_count or config.settings.SEMANTIC_SCHOLAR_RETRY_COUNT
        
        # 使用配置的批处理大小或自定义值
        config_batch_size = getattr(config.settings, 'SEMANTIC_SCHOLAR_API_BATCH_SIZE', 10)
        self.batch_size = batch_size if batch_size is not None else config_batch_size
        
        # 添加环境变量值的调试日志
        logger.debug(f"配置中的S2批处理大小: {config_batch_size}, 最终使用大小: {self.batch_size}")
        
        # 确保批处理大小为正整数
        try:
            self.batch_size = int(self.batch_size)
            if self.batch_size <= 0:
                logger.warning(f"批处理大小 ({self.batch_size}) 必须为正整数，使用默认值 10")
                self.batch_size = 10
        except (ValueError, TypeError):
            logger.warning(f"无效的批处理大小值，使用默认值 10")
            self.batch_size = 10
        
        self.request_delay = config.settings.SEMANTIC_SCHOLAR_REQUEST_DELAY
        
        logger.info(f"SemanticScholarClient 初始化。API_KEY提供: {bool(self.api_key)}, "
                   f"批处理大小: {self.batch_size}, 请求延迟: {self.request_delay}秒")
        
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["x-api-key"] = self.api_key
        
        self.timeout = config.S2_REQUEST_TIMEOUT
        self.retry_count = config.S2_RETRY_COUNT
        self.base_retry_delay = config.S2_BASE_RETRY_DELAY
        self.jitter_factor = config.S2_JITTER_FACTOR
        
        rate_limit_per_minute = config.S2_RATE_LIMIT_WITH_KEY if self.api_key else config.S2_RATE_LIMIT_WITHOUT_KEY
        self.token_bucket = TokenBucket(rate_limit_per_minute * config.S2_RATE_LIMIT_BUFFER_FACTOR)

    def _exponential_backoff(self, attempt: int) -> float:
        """计算指数退避延迟时间，带有抖动"""
        delay = min(self.base_retry_delay * (2 ** attempt), 300.0)
        jitter = random.uniform(-self.jitter_factor * delay, self.jitter_factor * delay)
        return max(0.1, delay + jitter)
        
    async def _make_request(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_multiplier: float = 1.0,
        error_msg_prefix: str = "[S2]"
    ) -> Optional[Any]:
        """
        通用的API请求方法，处理速率限制、重试、错误处理等
        
        Args:
            method: HTTP方法 ('GET' 或 'POST')
            url: 请求URL
            payload: POST请求的JSON数据 (可选)
            params: URL查询参数 (可选)
            timeout_multiplier: 超时时间倍数，用于批量请求等需要更长时间的操作
            error_msg_prefix: 错误日志前缀，用于标识请求类型
              Returns:
            成功时返回解析后的JSON数据，失败时返回None
        """
        for attempt in range(self.retry_count):
            await self.token_bucket.wait_for_token()
            
            try:
                async with aiohttp.ClientSession(headers=self.headers) as session:
                    timeout_obj = aiohttp.ClientTimeout(total=self.timeout * timeout_multiplier)
                    
                    if method.upper() == 'GET':
                        async with session.get(url, params=params, timeout=timeout_obj) as response:
                            return await self._handle_response(response, attempt, url, error_msg_prefix)
                    elif method.upper() == 'POST':
                        async with session.post(url, json=payload, params=params, timeout=timeout_obj) as response:
                            return await self._handle_response(response, attempt, url, error_msg_prefix)
                    else:
                        logger.error(f"{error_msg_prefix} 不支持的HTTP方法: {method}")
                        return None
                        
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"{error_msg_prefix} 请求出错 (尝试 {attempt+1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(self._exponential_backoff(attempt))
                else:
                    logger.error(f"{error_msg_prefix} 请求失败，达到最大重试次数。")
                    return None
            except Exception as e:
                logger.exception(f"{error_msg_prefix} 请求时发生意外错误 (尝试 {attempt+1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(self._exponential_backoff(attempt))
                else:
                    logger.error(f"{error_msg_prefix} 请求时发生意外错误，达到最大重试次数。")
                    return None
        return None
        
    async def _handle_response(self, response, attempt, url, error_msg_prefix):
        """处理API响应，包括状态码检查和JSON解析"""
        if response.status == 404:
            logger.warning(f"{error_msg_prefix} 资源未找到: {url}")
            return None
            
        if response.status == 429:
            retry_after_str = response.headers.get("Retry-After")
            try:
                retry_after = int(retry_after_str) if retry_after_str else self._exponential_backoff(attempt)
            except ValueError:
                retry_after = self._exponential_backoff(attempt)
                
            logger.warning(f"{error_msg_prefix} 达到API速率限制，等待 {retry_after:.2f} 秒后重试 (尝试 {attempt+1}/{self.retry_count})")
            await asyncio.sleep(retry_after)
            return "_RETRY_NEEDED_"
            
        try:
            response.raise_for_status()
            return await response.json()
        except Exception as e:
            logger.error(f"{error_msg_prefix} 响应处理错误: {e}")
            return None

    async def get_paper_details_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        异步根据DOI获取论文的Semantic Scholar详细信息。
        
        Args:
            doi: 文献的DOI
        
        Returns:
            包含论文详情的字典，或在出错时返回None
        """
        if not doi or not isinstance(doi, str): 
            return None
            
        doi = doi.strip().replace("https://doi.org/", "").replace("http://doi.org/", "")
        fields = config.S2_DEFAULT_FIELDS
        url = f"{self.base_url}/paper/DOI:{quote(doi, safe='')}"
        params = {"fields": fields}
        
        result = await self._make_request('GET', url, params=params, error_msg_prefix=f"[S2] DOI {doi}")
        
        if result == "_RETRY_NEEDED_":
            return await self.get_paper_details_by_doi(doi)
            
        if result and result.get("paperId"):
            logger.info(f"[S2] 成功获取DOI {doi} 的信息 (PaperID: {result.get('paperId')})。")
            return result
        return None

    async def get_papers_batch(self, doi_list: List[str]) -> List[Dict[str, Any]]:
        """
        批量获取论文信息 - 优化版本
        
        Args:
            doi_list: DOI列表
            
        Returns:
            论文信息列表
        """
        if not doi_list:
            return []
        
        valid_dois = [doi for doi in doi_list if doi and isinstance(doi, str) and doi.strip()]
        if not valid_dois:
            return []
            
        results = []
        batches = [valid_dois[i:i + self.batch_size] for i in range(0, len(valid_dois), self.batch_size)]
        
        logger.debug(f"请求字段参数: {config.S2_DEFAULT_FIELDS}")
        
        for i, batch in enumerate(batches):
            logger.info(f"正在获取批次 {i+1}/{len(batches)} ({len(batch)}个DOI)...")
            
            batch_results = await self._process_batch(batch)
            
            valid_count = len([r for r in batch_results if r])
            results.extend([r for r in batch_results if r])
            logger.info(f"批次 {i+1} 成功获取 {valid_count}/{len(batch)} 条参考文献的详细信息。")
            
            if i < len(batches) - 1:
                await asyncio.sleep(self.request_delay)
        
        return results

    async def _process_batch(self, doi_batch: List[str]) -> List[Optional[Dict[str, Any]]]:
        """处理单个DOI批次，使用批量API或并行单独请求"""
        try:
            fields = config.S2_DEFAULT_FIELDS
            if "authors.name" not in fields:
                fields += ",authors.name"
            if "venue" not in fields:
                fields += ",venue"
            if "year" not in fields:
                fields += ",year"
            
            payload = {"ids": [f"DOI:{doi.strip()}" for doi in doi_batch], 
                      "fields": fields}
            
            url = f"{self.base_url}/paper/batch"
            batch_response = await self._make_request(
                'POST', url, payload=payload, 
                timeout_multiplier=2.0, 
                error_msg_prefix=f"[S2 Batch] ({len(doi_batch)}个DOI)"
            )
            
            if batch_response == "_RETRY_NEEDED_":
                return await self._process_batch(doi_batch)
                
            if isinstance(batch_response, list):
                if batch_response and len(batch_response) > 0:
                    logger.debug(f"API响应示例 (第一条): {json.dumps(batch_response[0], indent=2)[:500]}...")
                return [item for item in batch_response if item and item.get("paperId")]
        except Exception as e:
            logger.error(f"[S2 Batch] 批量API处理失败，降级为并行单独请求: {e}")
            
        logger.info(f"[S2 Batch] 使用并行单独请求处理 {len(doi_batch)} 个DOI")
        tasks = [self.get_paper_details_by_doi(doi) for doi in doi_batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[S2] DOI {doi_batch[i]} 处理出错: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)
                
        return processed_results

    async def get_references_by_paper_id(self, paper_id: str, limit: Optional[int] = None) -> List[str]:
        """
        获取论文的参考文献DOI列表
        
        Args:
            paper_id: Semantic Scholar论文ID
            limit: 返回参考文献的最大数量
            
        Returns:
            参考文献DOI列表
        """
        if not paper_id:
            return []
            
        fields = config.S2_REFERENCES_FIELDS
        limit = limit or config.S2_REFERENCES_LIMIT
        url = f"{self.base_url}/paper/{paper_id}/references"
        params = {"fields": fields, "limit": limit}
        
        response_data = await self._make_request('GET', url, params=params, 
                                               error_msg_prefix=f"[S2] PaperID {paper_id} (参考文献)")
                                               
        if response_data == "_RETRY_NEEDED_":
            return await self.get_references_by_paper_id(paper_id, limit)
            
        if not response_data or not isinstance(response_data, dict):
            return []
            
        references_dois = []
        s2_references_data = response_data.get("data", [])
        
        for ref_item in s2_references_data:
            cited_paper = ref_item.get('citedPaper')
            if cited_paper and isinstance(cited_paper.get('externalIds'), dict):
                doi = cited_paper['externalIds'].get('DOI')
                if doi:
                    references_dois.append(doi)
                    
        logger.info(f"[S2] PaperID {paper_id}: 成功获取 {len(references_dois)} 条参考文献DOI。")
        return references_dois

    async def batch_get_references_by_papers(self, paper_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        logger.info(f"步骤1: 获取论文 {paper_id} 的参考文献列表")
        references_dois = await self.get_references_by_paper_id(paper_id, limit=limit)
        if not references_dois:
            logger.info(f"论文 {paper_id} 未找到参考文献DOI")
            return []
        logger.info(f"找到 {len(references_dois)} 个参考文献DOI")

        # 步骤2: 批量获取参考文献详细信息
        raw_papers = await self.get_papers_batch(references_dois)
        logger.info(f"从S2获取到 {len(raw_papers)} 条参考文献的完整详情")

        # 步骤2.5: 用DOI列表补全缺失的DOI
        for idx, paper in enumerate(raw_papers):
            if paper is not None:
                external_ids = paper.get("externalIds", {})
                if not external_ids.get("DOI") and idx < len(references_dois):
                    if "externalIds" not in paper or not isinstance(paper["externalIds"], dict):
                        paper["externalIds"] = {}
                    paper["externalIds"]["DOI"] = references_dois[idx]

        # 步骤3: 收集所有DOI，准备批量获取PubMed信息（无论是否已有PMID）
        doi_list = []
        for idx, paper in enumerate(raw_papers):
            if not paper:
                continue
            external_ids = paper.get("externalIds", {}) if paper.get("externalIds") else {}
            doi = external_ids.get("DOI", "") or ""
            if doi:
                doi = doi.strip().lower().replace("https://doi.org/", "").replace("http://doi.org/", "")
                doi_list.append(doi)

        pubmed_info_map = {}
        try:
            from slais.pubmed_client import PubMedClient
            pubmed_client = PubMedClient()
            email = getattr(config.settings, 'NCBI_EMAIL', 'example@example.com')
            # 优先批量查DOI→PMID（并发提升性能）
            async def get_pmid_for_doi(doi):
                try:
                    details = await pubmed_client.get_article_details_by_doi(doi, email)
                    return doi, details.get("pmid") if details and details.get("pmid") else None
                except Exception as e:
                    logger.warning(f"[PubMedClient] 并发获取PMID时DOI {doi} 出错: {e}")
                    return doi, None

            pmid_tasks = [get_pmid_for_doi(doi) for doi in doi_list]
            pmid_results = await asyncio.gather(*pmid_tasks)
            doi_to_pmid = {doi: pmid for doi, pmid in pmid_results}
            pmids = [pmid for pmid in doi_to_pmid.values() if pmid]

            # 批量efetch获取详情（并发提升性能）
            async def get_detail_for_pmid(pmid):
                try:
                    return await pubmed_client.get_article_details_by_pmid(pmid, email)
                except Exception as e:
                    logger.warning(f"[PubMedClient] 并发获取详情时PMID {pmid} 出错: {e}")
                    return None

            if pmids:
                detail_tasks = [get_detail_for_pmid(pmid) for pmid in pmids]
                pmid_details = await asyncio.gather(*detail_tasks)
                for detail in pmid_details:
                    if detail and detail.get("doi"):
                        pubmed_info_map[detail["doi"].lower()] = detail

            # 对于未查到PMID的DOI，降级为并发单个查找
            missing_dois = [doi for doi in doi_list if doi not in pubmed_info_map]
            if missing_dois:
                async def get_detail_for_doi(doi):
                    try:
                        detail = await pubmed_client.get_article_details_by_doi(doi, email)
                        return doi, detail
                    except Exception as e:
                        logger.warning(f"[PubMedClient] 并发补全DOI {doi} 详情时出错: {e}")
                        return doi, None
                detail_tasks = [get_detail_for_doi(doi) for doi in missing_dois]
                detail_results = await asyncio.gather(*detail_tasks)
                for doi, detail in detail_results:
                    if detail and detail.get("doi"):
                        pubmed_info_map[detail["doi"].lower()] = detail
        except Exception as e:
            logger.error(f"批量获取PubMed信息失败: {e}")

        # 步骤5: 组装最终输出，优先用PubMed信息补全
        formatted_references = []
        for idx, paper in enumerate(raw_papers):
            if not paper:
                continue
            external_ids = paper.get("externalIds", {}) if paper.get("externalIds") else {}
            pmid = external_ids.get("PubMed", "") or ""
            pmcid = external_ids.get("PMC", "") or ""
            paper_doi = external_ids.get("DOI", "") or ""
            s2_paper_id = paper.get("paperId", "") or ""
            year = paper.get("year", "")
            venue = paper.get("venue", "") or ""
            title = paper.get("title", "") or ""
            abstract = paper.get("abstract", "") or ""
            citation_count = paper.get("citationCount", 0)
            authors = []
            authors_str = ""
            if "authors" in paper and isinstance(paper["authors"], list):
                authors = [author.get("name", "") for author in paper["authors"] if isinstance(author, dict) and "name" in author]
                authors_str = "; ".join(filter(None, authors))

            # 用PubMed信息补全（只用DOI查找结果）
            pubmed_info = None
            doi_key = paper_doi.strip().lower().replace("https://doi.org/", "").replace("http://doi.org/", "")
            if doi_key and doi_key in pubmed_info_map:
                pubmed_info = pubmed_info_map[doi_key]

            if pubmed_info:
                title = pubmed_info.get("title") or title
                authors_str = pubmed_info.get("authors_str") or authors_str
                abstract = pubmed_info.get("abstract") or abstract
                venue = pubmed_info.get("journal") or venue
                year = pubmed_info.get("pub_date") or year
                pmcid = pubmed_info.get("pmcid") or pmcid
                pmcid_link = pubmed_info.get("pmcid_link") or (f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else "")
                pmid_link = pubmed_info.get("pmid_link") or (f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_info.get('pmid','')}/" if pubmed_info.get('pmid') else "")
                paper_doi = pubmed_info.get("doi") or paper_doi
                pmid = pubmed_info.get("pmid") or pmid
            else:
                pmid_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
                pmcid_link = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else ""

            formatted_paper = {
                "doi": str(paper_doi),
                "title": str(title),
                "authors_str": str(authors_str),
                "pub_date": str(year) if year else "",
                "journal": str(venue),
                "abstract": str(abstract),
                "pmid": str(pmid),
                "pmid_link": pmid_link,
                "pmcid": str(pmcid),
                "pmcid_link": pmcid_link,
                "citation_count": str(citation_count) if citation_count else "",
                "s2_paper_id": str(s2_paper_id)
            }
            # 保证所有字段都存在且为字符串
            required_fields = [
                "doi", "title", "authors_str", "pub_date", "journal", "abstract",
                "pmid", "pmid_link", "pmcid", "pmcid_link", "citation_count", "s2_paper_id"
            ]
            for field in required_fields:
                if field not in formatted_paper or formatted_paper[field] is None:
                    formatted_paper[field] = ""
            formatted_references.append(formatted_paper)

        return formatted_references