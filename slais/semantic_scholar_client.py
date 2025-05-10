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
        self.base_retry_delay = 2.0 # 秒
        self.jitter_factor = 0.25
        
        # 根据是否有API Key设置不同的速率限制
        rate_limit_per_minute = 800 if self.api_key else 120 # 参考用户脚本中的值
        self.token_bucket = TokenBucket(rate_limit_per_minute * 0.8) # 80% buffer

    def _exponential_backoff(self, attempt: int) -> float:
        delay = min(self.base_retry_delay * (2 ** attempt), 300.0) 
        jitter = random.uniform(-self.jitter_factor * delay, self.jitter_factor * delay)
        return max(0.1, delay + jitter)

    async def get_paper_details_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        异步根据DOI获取论文的Semantic Scholar详细信息。
        包括 paperId, title, authors, year, abstract, externalIds, citationCount, referenceCount等。
        """
        if not doi: return None

        fields = "paperId,externalIds,url,title,abstract,venue,year,referenceCount,citationCount,influentialCitationCount,isOpenAccess,fieldsOfStudy,publicationTypes,authors.name,authors.url"
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

        fields = "paperId,externalIds,url,title,abstract,venue,year,referenceCount,citationCount,influentialCitationCount,isOpenAccess,fieldsOfStudy,publicationTypes,authors.name"
        url = f"{self.base_url}/paper/batch"
        
        # Semantic Scholar 批量API一次最多处理1000个ID，但建议更小批次以避免超时和大型响应
        # 我们将遵循用户脚本中的BATCH_SIZE，但这里没有直接传递，可以考虑在config中设置S2_BATCH_SIZE
        # 为简单起见，如果DOIs数量大，可以分批，但这里先尝试一次性（如果aiohttp和S2支持）
        # 或者，更稳妥的是，如果DOIs列表很大，则分批调用此方法。
        # 此方法内部先尝试一次批量请求。

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
                            original_doi = valid_dois[i] # 假设顺序对应
                            if paper_data and paper_data.get("paperId"):
                                results[original_doi] = paper_data
                            elif paper_data: # 有数据但无paperId
                                logger.warning(f"[S2 Batch] DOI {original_doi} 返回数据但无paperId: {str(paper_data)[:100]}")
                            # else paper_data is None, results[original_doi] 保持 None
                        logger.info(f"[S2 Batch] 成功处理 {len(valid_dois)} 个DOI的批量请求，获取到 {sum(1 for r in results.values() if r)} 条有效记录。")
                        return results
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"[S2 Batch] 批量获取DOI信息时出错 (尝试 {attempt+1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1: await asyncio.sleep(self._exponential_backoff(attempt))
                else: logger.error(f"[S2 Batch] 批量获取DOI信息失败，达到最大重试次数。"); break # 跳出重试
            except Exception as e:
                logger.exception(f"[S2 Batch] 批量获取DOI信息时发生意外错误 (尝试 {attempt+1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1: await asyncio.sleep(self._exponential_backoff(attempt))
                else: break # 跳出重试
        
        # 如果批量失败，可以考虑回退到单个请求，但这里为了简化，如果批量失败则返回已有的（可能为空的）results
        if not any(results.values()): # 如果一个都没成功
             logger.warning(f"[S2 Batch] 批量请求最终失败，将尝试逐个获取 {len(valid_dois)} 个DOI。")
             # 逐个获取 (使用之前的单DOI获取方法)
             tasks = [self.get_paper_details_by_doi(doi) for doi in valid_dois]
             individual_results = await asyncio.gather(*tasks, return_exceptions=True)
             for i, res in enumerate(individual_results):
                 original_doi = valid_dois[i]
                 if isinstance(res, dict) and res.get("paperId"):
                     results[original_doi] = res
                 elif isinstance(res, Exception):
                     logger.error(f"[S2 Fallback] 获取DOI {original_doi} 详情时出错: {res}")
        return results


    async def get_references_by_paper_id(self, paper_id: str) -> List[str]:
        if not paper_id: return []
        references_dois: List[str] = []
        fields = "citedPaper.externalIds" 
        url = f"{self.base_url}/paper/{paper_id}/references?fields={fields}&limit=1000" # 尝试获取更多

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
