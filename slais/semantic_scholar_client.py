import asyncio
import random # 用于抖动
import time # 用于TokenBucket
import aiohttp # 导入 aiohttp
from typing import List, Optional, Dict, Any

from .utils.logging_utils import logger
from . import config # 导入 config 模块

# 速率限制控制 - 令牌桶实现 (来自用户提供的脚本)
class TokenBucket:
    def __init__(self, rate_per_minute: float, burst_limit: Optional[int] = None):
        self.rate_per_second = rate_per_minute / 60.0
        self.burst_limit = burst_limit if burst_limit is not None else max(10, int(rate_per_minute / 3))
        self.tokens = float(self.burst_limit) #确保tokens是浮点数
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
    def __init__(self):
        self.base_url = config.SEMANTIC_SCHOLAR_API_BASE_URL
        self.api_key = config.SEMANTIC_SCHOLAR_API_KEY
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["x-api-key"] = self.api_key
        
        self.timeout = config.S2_REQUEST_TIMEOUT
        self.retry_count = config.S2_RETRY_COUNT
        self.base_retry_delay = config.S2_BASE_RETRY_DELAY # 从配置获取
        self.jitter_factor = config.S2_JITTER_FACTOR # 从配置获取
        
        # 根据是否有API Key设置不同的速率限制
        rate_limit_per_minute = config.S2_RATE_LIMIT_WITH_KEY if self.api_key else config.S2_RATE_LIMIT_WITHOUT_KEY
        self.token_bucket = TokenBucket(rate_limit_per_minute * config.S2_RATE_LIMIT_BUFFER_FACTOR)

    def _exponential_backoff(self, attempt: int) -> float:
        delay = min(self.base_retry_delay * (2 ** attempt), 300.0) # 300.0 可以考虑也加入config
        jitter = random.uniform(-self.jitter_factor * delay, self.jitter_factor * delay)
        return max(0.1, delay + jitter)

    async def get_paper_details_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        异步根据DOI获取论文的Semantic Scholar详细信息。
        包括 paperId, title, authors, year, abstract, externalIds, citationCount, referenceCount等。
        """
        if not doi: return None

        fields = config.S2_DEFAULT_FIELDS # 从配置获取
        url = f"{self.base_url}/paper/DOI:{doi}?fields={fields}"
        
        for attempt in range(self.retry_count):
            await self.token_bucket.wait_for_token()
            try:
                async with aiohttp.ClientSession(headers=self.headers) as session:
                    timeout_obj = aiohttp.ClientTimeout(total=self.timeout)
                    async with session.get(url, timeout=timeout_obj) as response:
                        if response.status == 404:
                            logger.warning(f"[S2] DOI {doi} 在Semantic Scholar中未找到。")
                            return None
                        if response.status == 429:
                            retry_after_str = response.headers.get("Retry-After")
                            try: retry_after = int(retry_after_str) if retry_after_str else self._exponential_backoff(attempt)
                            except ValueError: retry_after = self._exponential_backoff(attempt)
                            logger.warning(f"[S2] DOI {doi}: 达到API速率限制，等待 {retry_after:.2f} 秒后重试 (尝试 {attempt+1}/{self.retry_count})")
                            await asyncio.sleep(retry_after)
                            continue
                        response.raise_for_status()
                        data = await response.json()
                        if data and data.get("paperId"):
                            logger.info(f"[S2] 成功获取DOI {doi} 的信息 (PaperID: {data.get('paperId')})。")
                            return data
                        else:
                            logger.warning(f"[S2] DOI {doi}: 获取成功但未找到paperId或有效数据。")
                            return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"[S2] 获取DOI {doi} 的信息时出错 (尝试 {attempt+1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1: await asyncio.sleep(self._exponential_backoff(attempt))
                else: logger.error(f"[S2] 获取DOI {doi} 的信息失败，达到最大重试次数。"); return None
            except Exception as e:
                logger.exception(f"[S2] 获取DOI {doi} 的信息时发生意外错误 (尝试 {attempt+1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1: await asyncio.sleep(self._exponential_backoff(attempt))
                else: return None
        return None

    async def batch_get_paper_details_by_dois(self, dois: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        异步批量获取多个DOI的文献详细信息。
        返回一个字典，键是原始DOI，值是获取到的论文信息字典或None。
        """
        if not dois: return {}
        
        results: Dict[str, Optional[Dict[str, Any]]] = {doi: None for doi in dois}
        valid_dois = [d for d in dois if d and isinstance(d, str) and d.strip()]
        if not valid_dois: return results

        fields = config.S2_DEFAULT_FIELDS # 从配置获取
        url = f"{self.base_url}/paper/batch"
        
        payload = {"ids": [f"DOI:{doi}" for doi in valid_dois], "fields": fields}

        for attempt in range(self.retry_count):
            await self.token_bucket.wait_for_token()
            try:
                async with aiohttp.ClientSession(headers=self.headers) as session:
                    timeout_obj = aiohttp.ClientTimeout(total=self.timeout * 2) # 批量请求可能需要更长时间
                    async with session.post(url, json=payload, timeout=timeout_obj) as response:
                        if response.status == 429:
                            retry_after_str = response.headers.get("Retry-After")
                            try: retry_after = int(retry_after_str) if retry_after_str else self._exponential_backoff(attempt)
                            except ValueError: retry_after = self._exponential_backoff(attempt)
                            logger.warning(f"[S2] 批量DOI请求: 达到API速率限制，等待 {retry_after:.2f} 秒后重试 (尝试 {attempt+1}/{self.retry_count})")
                            await asyncio.sleep(retry_after)
                            continue
                        response.raise_for_status()
                        api_data_list = await response.json() # 列表，可能包含null
                        
                        # 将结果映射回原始DOI
                        for i, paper_data in enumerate(api_data_list):
                            if i < len(valid_dois):  # 确保索引在有效范围内
                                original_doi = valid_dois[i] # 假设顺序对应
                                if paper_data and paper_data.get("paperId"):
                                    # 确保保留原始DOI，因为返回的paper_data中可能没有DOI或DOI不同
                                    if not paper_data.get("externalIds") or not paper_data["externalIds"].get("DOI"):
                                        # 如果API返回中没有DOI，将原始DOI添加到结果中
                                        if not paper_data.get("externalIds"):
                                            paper_data["externalIds"] = {}
                                        paper_data["externalIds"]["DOI"] = original_doi
                                    results[original_doi] = paper_data
                                elif paper_data: # 有数据但无paperId
                                    logger.warning(f"[S2 Batch] DOI {original_doi} 返回数据但无paperId: {str(paper_data)[:100]}")
                        logger.info(f"[S2 Batch] 成功处理 {len(valid_dois)} 个DOI的批量请求，获取到 {sum(1 for r in results.values() if r)} 条有效记录。")
                        
                        return results  # 修改：返回以DOI为键的字典，而不是API返回的列表
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"[S2 Batch] 批量获取DOI信息时出错 (尝试 {attempt+1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1: await asyncio.sleep(self._exponential_backoff(attempt))
                else: logger.error(f"[S2 Batch] 批量获取DOI信息失败，达到最大重试次数。"); break # 跳出重试
            except Exception as e:
                logger.exception(f"[S2 Batch] 批量获取DOI信息时发生意外错误 (尝试 {attempt+1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1: await asyncio.sleep(self._exponential_backoff(attempt))
                else: break # 跳出重试
        
        if not any(results.values()): # 如果一个都没成功
             logger.warning(f"[S2 Batch] 批量请求最终失败，将尝试逐个获取 {len(valid_dois)} 个DOI。")
             tasks = [self.get_paper_details_by_doi(doi) for doi in valid_dois]
             individual_results = await asyncio.gather(*tasks, return_exceptions=True)
             for i, res in enumerate(individual_results):
                 original_doi = valid_dois[i]
                 if isinstance(res, dict) and res.get("paperId"):
                     results[original_doi] = res
                 elif isinstance(res, Exception):
                     logger.error(f"[S2 Fallback] 获取DOI {original_doi} 详情时出错: {res}")
        return results

    async def batch_get_paper_details_by_dois_parallel(self, dois, batch_size=10, max_concurrent=5):
        """
        并行批量获取论文详细信息，使用异步并发控制
        
        Args:
            dois: DOI列表
            batch_size: 每批处理的DOI数量
            max_concurrent: 最大并发请求数
        
        Returns:
            包含论文详细信息的列表
        """
        import asyncio
        from asyncio import Semaphore, gather
        from slais.utils.logging_utils import logger
        
        results = []
        semaphore = Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(doi):
            async with semaphore:
                try:
                    # 使用短暂延迟避免完全同时发起请求
                    await asyncio.sleep(0.1)
                    return await self.get_paper_details_by_doi(doi)
                except Exception as e:
                    logger.warning(f"获取DOI {doi}的详情时出错: {e}")
                    return None
        
        # 批量处理DOIs
        for i in range(0, len(dois), batch_size):
            batch = dois[i:i+batch_size]
            logger.info(f"并行处理DOI批次 {i//batch_size+1}/{(len(dois)-1)//batch_size+1} ({len(batch)}个DOI)...")
            
            # 并行获取此批次的所有DOI详情
            batch_tasks = [fetch_with_semaphore(doi) for doi in batch]
            batch_results = await gather(*batch_tasks, return_exceptions=False)
            
            # 过滤掉None值并添加到结果中
            valid_results = [result for result in batch_results if result]
            results.extend(valid_results)
            
            logger.info(f"批次 {i//batch_size+1} 完成，成功获取 {len(valid_results)}/{len(batch)} 个DOI的详情")
            
            # 在批次间稍作暂停，避免触发API限制
            if i + batch_size < len(dois):
                await asyncio.sleep(1)
        
        return results

    async def get_references_by_paper_id(self, paper_id: str, limit: int = None) -> List[str]:
        if not paper_id: return []
        references_dois: List[str] = []
        fields = config.S2_REFERENCES_FIELDS # 从配置获取
        limit = limit or config.S2_REFERENCES_LIMIT # 使用传入的limit参数或配置值
        url = f"{self.base_url}/paper/{paper_id}/references?fields={fields}&limit={limit}"

        for attempt in range(self.retry_count):
            await self.token_bucket.wait_for_token()
            try:
                async with aiohttp.ClientSession(headers=self.headers) as session:
                    timeout_obj = aiohttp.ClientTimeout(total=self.timeout)
                    async with session.get(url, timeout=timeout_obj) as response:
                        if response.status == 429: 
                            retry_after_str = response.headers.get("Retry-After")
                            try: retry_after = int(retry_after_str) if retry_after_str else self._exponential_backoff(attempt)
                            except ValueError: retry_after = self._exponential_backoff(attempt)
                            logger.warning(f"[S2] PaperID {paper_id} (参考文献): 达到API速率限制，等待 {retry_after:.2f} 秒后重试 (尝试 {attempt+1}/{self.retry_count})")
                            await asyncio.sleep(retry_after)
                            continue
                        response.raise_for_status()
                        data = await response.json()
                        
                        # Semantic Scholar 的 /references 端点使用 next token 进行分页
                        # 为了简化，这里只处理第一页。完整的实现需要循环处理 next token。
                        s2_references_data = data.get("data", [])
                        for ref_item in s2_references_data:
                            cited_paper = ref_item.get('citedPaper')
                            if cited_paper and isinstance(cited_paper.get('externalIds'), dict):
                                doi = cited_paper['externalIds'].get('DOI')
                                if doi:
                                    references_dois.append(doi)
                        logger.info(f"[S2] PaperID {paper_id}: 成功获取 {len(references_dois)} 条参考文献DOI (来自第一页)。")
                        return references_dois 
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"[S2] 获取PaperID {paper_id} 的参考文献时出错 (尝试 {attempt+1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1: await asyncio.sleep(self._exponential_backoff(attempt))
                else: logger.error(f"[S2] 获取PaperID {paper_id} 的参考文献失败，达到最大重试次数。"); return []
            except Exception as e:
                logger.exception(f"[S2] 获取PaperID {paper_id} 的参考文献时发生意外错误 (尝试 {attempt+1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1: await asyncio.sleep(self._exponential_backoff(attempt))
                else: return []
        return []

    async def batch_get_references_by_papers(self, paper_id, limit=100):
        """
        批量获取论文的参考文献，使用更高效的方式
        
        Args:
            paper_id: 论文的SemanticScholar ID
            limit: 最大获取的参考文献数量
            
        Returns:
            包含参考文献详细信息的列表
        """
        from slais.utils.logging_utils import logger
        
        # 步骤1: 首先获取参考文献列表
        logger.info(f"步骤1: 获取论文 {paper_id} 的参考文献列表")
        references_dois = await self.get_references_by_paper_id(paper_id, limit=limit)
        if not references_dois:
            return []
            
        logger.info(f"找到 {len(references_dois)} 个参考文献DOI")
        
        # 步骤2: 批量获取DOI详细信息
        logger.info(f"步骤2: 批量获取参考文献详细信息")
        
        # 准备批量获取
        batch_size = 20  # 每批处理的引用数量
        all_references = []
        total_batches = (len(references_dois) + batch_size - 1) // batch_size
        
        for i in range(0, len(references_dois), batch_size):
            batch = references_dois[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            logger.info(f"正在获取批次 {batch_num}/{total_batches} ({len(batch)}个DOI)...")
            
            # 构造批量请求
            batch_paper_details_tasks = [self.get_paper_details_by_doi(doi) for doi in batch]
            batch_s2_results = await asyncio.gather(*batch_paper_details_tasks, return_exceptions=True)

            current_batch_formatted_results = []
            for result in batch_s2_results:
                if isinstance(result, Exception) or not result:
                    logger.warning(f"获取参考文献详情时出错或无结果: {result if isinstance(result, Exception) else '无结果'}")
                    continue

                try:
                    # 获取PMID和PMCID (如果存在)
                    pmid = result.get("externalIds", {}).get("PubMed", "")
                    pmcid = result.get("externalIds", {}).get("PMC", "")
                    s2_paper_id = result.get("paperId", "")
                    citation_count = result.get("citationCount", 0) # Default to 0 if not present
                    
                    # 确保字段一致性
                    formatted_result = {
                        "doi": result.get("externalIds", {}).get("DOI", ""), # Ensure DOI is from S2 if primary key was S2 ID
                        "title": result.get("title", ""),
                        "journal": result.get("venue", ""),
                        "pub_date": str(result.get("year", "")),
                        "abstract": result.get("abstract", ""),
                        "s2_paper_id": s2_paper_id,
                        "citation_count": citation_count,
                        "pmid": pmid,
                        "pmcid": pmcid,
                        "pmid_link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                        "pmcid_link": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else "",
                    }
                    
                    # 处理作者
                    if "authors" in result and isinstance(result["authors"], list):
                        author_names = [author.get("name", "") for author in result["authors"] if isinstance(author, dict) and "name" in author]
                        formatted_result["authors_str"] = "; ".join(author_names) # 修改键名
                    else:
                        formatted_result["authors_str"] = "" # 修改键名
                            
                    current_batch_formatted_results.append(formatted_result)
                except Exception as e:
                    logger.warning(f"格式化DOI {result.get('externalIds', {}).get('DOI', 'N/A')} 的S2详情时出错: {str(e)}")
                    continue
            
            all_references.extend(current_batch_formatted_results)
            logger.info(f"批次 {batch_num} 成功获取 {len(current_batch_formatted_results)}/{len(batch)} 条参考文献的详细格式化信息。")
            
            # 避免API限制，批次间短暂暂停
            if i + batch_size < len(references_dois):
                await asyncio.sleep(0.5)
        
        logger.info(f"成功获取 {len(all_references)}/{len(references_dois)} 条参考文献详情")
        return all_references
