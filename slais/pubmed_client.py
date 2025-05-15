import urllib.parse
import json
import xml.etree.ElementTree as ET # 用于解析XML
import re   # 用于正则表达式处理
import math # 用于向上取整除法
import asyncio # 用于异步休眠
import anyio # 添加 anyio 导入
import random # 添加 random 导入
import time # 添加 time 导入
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log, retry_if_exception_type
import logging
from typing import List, Optional, Dict, Any, TypedDict # 导入 TypedDict
from datetime import datetime, timedelta # 用于日期处理
import aiohttp

from .utils.logging_utils import logger
from . import config # 导入 config 模块

# --- TypedDict 定义 ---
class ArticleDetails(TypedDict): # PubMed 文章详情
    title: Optional[str]
    authors: Optional[List[str]]
    journal: Optional[str]
    publication_date: Optional[str]
    pmid: Optional[str]
    pmid_link: Optional[str]
    pmcid: Optional[str]
    pmcid_link: Optional[str]
    abstract: Optional[str]
    doi: Optional[str]  # 新增 DOI 字段

class Output(TypedDict): # 主要用于描述PubMedClient的输出结构
    original_article: Optional[ArticleDetails]
    related_articles: Optional[List[ArticleDetails]]
    related_articles_count: Optional[int]
    message: Optional[str]
    error: Optional[str]

# --- 月份名称到数字的映射 (用于日期解析) ---
MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}

# 辅助函数: 解析单个 PubmedArticle XML 元素
def parse_pubmed_article(article_xml: ET.Element) -> Optional[ArticleDetails]:
    """解析来自 efetch XML 的单个 <PubmedArticle> 元素."""
    if article_xml is None:
        return None

    pmid = None 
    doi_val = None  # 初始化 DOI 变量
    try:
        medline_citation = article_xml.find("./MedlineCitation")
        pubmed_data = article_xml.find("./PubmedData")

        if medline_citation is None:
             return None 

        pmid = medline_citation.findtext("./PMID")
        article = medline_citation.find("./Article")

        if article is None or pmid is None:
             return None 

        # 尝试从 PubmedData 的 ArticleIdList 中提取 DOI
        if pubmed_data is not None:
            doi_element = pubmed_data.find("./ArticleIdList/ArticleId[@IdType='doi']")
            if doi_element is not None and doi_element.text:
                doi_val = doi_element.text.strip()

        # 如果在 PubmedData 中没找到 DOI，尝试从 Article 的 ELocationID 中提取
        if not doi_val and article is not None:
            elocation_elements = article.findall("./ELocationID")
            for eloc_id in elocation_elements:
                if eloc_id.get("EIdType") == "doi" and eloc_id.get("ValidYN", "Y").upper() == "Y":
                    if eloc_id.text:
                        doi_val = eloc_id.text.strip()
                        break

        # 如果仍未找到 DOI，尝试从 Article 的 ArticleIdList 中提取（有些 XML 结构可能在这里存放）
        if not doi_val and article is not None:
            article_id_list = article.find("./ArticleIdList")
            if article_id_list is not None:
                for art_id in article_id_list.findall("./ArticleId"):
                    if art_id.get("IdType") == "doi":
                        if art_id.text:
                            doi_val = art_id.text.strip()
                            break

        pmid_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        title_element = article.find("./ArticleTitle")
        title = "".join(title_element.itertext()).strip() if title_element is not None else "未找到标题"

        author_list = []
        author_elements = article.findall("./AuthorList/Author")
        for author in author_elements:
            last_name = author.findtext("LastName")
            fore_name = author.findtext("ForeName")
            initials = author.findtext("Initials")
            collective_name = author.findtext("CollectiveName")
            if collective_name:
                 author_list.append(collective_name.strip())
            elif last_name:
                name_parts = []
                if fore_name: name_parts.append(fore_name.strip())
                elif initials: name_parts.append(initials.strip())
                name_parts.append(last_name.strip())
                author_list.append(" ".join(name_parts))

        abstract_parts = []
        abstract_elements = article.findall("./Abstract/AbstractText")
        if abstract_elements:
            for part in abstract_elements:
                 label = part.get("Label")
                 text = "".join(part.itertext()).strip()
                 if label and text: abstract_parts.append(f"{label.upper()}: {text}")
                 elif text: abstract_parts.append(text)
            abstract = "\n".join(abstract_parts) if abstract_parts else "未找到摘要"
        else:
            other_abstract_elements = article.findall("./OtherAbstract/AbstractText")
            if other_abstract_elements:
                for part in other_abstract_elements:
                    text = "".join(part.itertext()).strip()
                    if text: abstract_parts.append(text)
                abstract = "\n".join(abstract_parts) if abstract_parts else "未找到摘要"
            else:
                 abstract = "未找到摘要"

        pmcid_val = None
        pmcid_link_val = None
        if pubmed_data is not None:
            pmc_element = pubmed_data.find("./ArticleIdList/ArticleId[@IdType='pmc']")
            if pmc_element is not None and pmc_element.text:
                 pmcid_raw = pmc_element.text.strip().upper()
                 if pmcid_raw.startswith("PMC"):
                     pmcid_num = pmcid_raw[3:]
                     if pmcid_num.isdigit():
                          pmcid_val = f"PMC{pmcid_num}"
                          pmcid_link_val = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid_val}/"
                     else:
                          pmcid_val = pmcid_raw 
                 elif pmcid_raw.isdigit():
                      pmcid_val = f"PMC{pmcid_raw}"
                      pmcid_link_val = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid_val}/"
                 else: 
                      pmcid_val = f"PMC ID: {pmc_element.text.strip()}"

        journal_title_raw = article.findtext("./Journal/Title")
        journal_name = None
        if journal_title_raw:
            journal_name = re.sub(r'\s*\(.*?\)\s*', '', journal_title_raw).strip()
            if not journal_name: journal_name = journal_title_raw.strip()
        else:
             journal_name = "未找到期刊"

        publication_date_str = None
        pub_date_element = article.find("./Journal/JournalIssue/PubDate")
        article_date_element = article.find("./ArticleDate")
        year_str, month_str, day_str = None, None, None
        date_source_element = pub_date_element if pub_date_element is not None else article_date_element

        if date_source_element is not None:
            year_str = date_source_element.findtext("Year")
            month_elem = date_source_element.find("Month")
            day_str = date_source_element.findtext("Day")
            if month_elem is not None:
                month_text = month_elem.text.strip() if month_elem.text else None
                if month_text:
                    if month_text.isdigit(): month_str = month_text.zfill(2)
                    elif month_text in MONTH_MAP: month_str = MONTH_MAP[month_text]
            if year_str and year_str.isdigit() and len(year_str) == 4:
                month_str = month_str if month_str else "01"
                day_str = day_str.zfill(2) if day_str and day_str.isdigit() else "01"
                try:
                    datetime.strptime(f"{year_str}-{month_str}-{day_str}", "%Y-%m-%d")
                    publication_date_str = f"{year_str}-{month_str}-{day_str}"
                except ValueError:
                    month_str, day_str = "01", "01"
                    try: 
                        datetime.strptime(f"{year_str}-{month_str}-{day_str}", "%Y-%m-%d")
                        publication_date_str = f"{year_str}-{month_str}-{day_str}"
                    except ValueError: publication_date_str = None
        
        if publication_date_str is None and pub_date_element is not None:
            medline_date_text = pub_date_element.findtext("MedlineDate")
            if medline_date_text:
                match = re.search(r'\b(\d{4})\b', medline_date_text)
                if match:
                    year_str = match.group(1)
                    month_found = None
                    for mAbbr, mNum in MONTH_MAP.items():
                        if mAbbr.lower() in medline_date_text.lower(): month_found = mNum; break
                    month_str = month_found if month_found else "01"
                    day_str = "01"
                    publication_date_str = f"{year_str}-{month_str}-{day_str}"
        
        return {
            "title": title, "authors": author_list if author_list else None,
            "journal": journal_name, "publication_date": publication_date_str,
            "pmid": pmid, "pmid_link": pmid_link,
            "pmcid": pmcid_val, "pmcid_link": pmcid_link_val,
            "abstract": abstract if abstract != "未找到摘要" else None,
            "doi": doi_val,  # 添加提取到的 DOI
        }
    except Exception as e:
        logger.error(f"错误: 解析文章 PMID {pmid or 'UNKNOWN'} 时出错: {e}")
        return None

class PubMedClient:
    """PubMed API客户端"""
    def __init__(self, 
                 api_key: Optional[str] = None, 
                 email: Optional[str] = None,
                 timeout: float = config.settings.DEFAULT_REQUEST_TIMEOUT, # 从配置获取或设置默认值
                 retry_count: int = config.settings.PUBMED_RETRY_COUNT, # 从配置获取或设置默认值
                 ssl_verify: bool = True, # 增加ssl_verify选项
                 max_results: Optional[int] = None, # 修改为 Optional[int]
                 years_back: Optional[int] = None): # 修改为 Optional[int]
        self.base_url = config.settings.PUBMED_API_BASE_URL.rstrip('/')
        # 安全地访问 NCBI_API_KEY，如果未定义则默认为 None
        self.api_key = api_key or getattr(config.settings, 'NCBI_API_KEY', None) 
        self.email = email or config.settings.NCBI_EMAIL
        self.timeout = timeout
        self.retry_count = retry_count
        self.ssl_verify = ssl_verify
        
        # 初始化实例的默认值，确保它们是整数
        try:
            self.max_results = int(max_results if max_results is not None else getattr(config.settings, 'RELATED_ARTICLES_MAX', 50))
        except (ValueError, TypeError):
            logger.warning(f"Invalid initial max_results ('{max_results}' or config), defaulting to 50.")
            self.max_results = 50
        
        try:
            self.years_back = int(years_back if years_back is not None else getattr(config.settings, 'RELATED_ARTICLES_YEARS_BACK', 5))
        except (ValueError, TypeError):
            logger.warning(f"Invalid initial years_back ('{years_back}' or config), defaulting to 5.")
            self.years_back = 5

        self.tool = getattr(config.settings, 'PUBMED_TOOL_NAME', 'slais_pubmed_client')  # 添加tool属性用于URL构建
        # 添加batch_size属性
        self.efetch_batch_size = getattr(config.settings, 'PUBMED_EFETCH_BATCH_SIZE', 200)
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = 0
        self._min_interval = 0.35  # PubMed推荐每秒不超过3次请求
        logger.info(f"PubMedClient initialized. Email: {self.email}, API_KEY_PROVIDED: {bool(self.api_key)}, Max Results: {self.max_results}, Years Back: {self.years_back}")
    
    async def _wait_for_rate_limit(self):
        async with self._rate_limit_lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = time.time()

    def _exponential_backoff(self, attempt: int) -> float:
        """计算指数退避时间"""
        return min(config.settings.PUBMED_MAX_BACKOFF, (2 ** attempt) + (random.uniform(0, 1)))
    
    async def _get_doi_from_pmid_crossref(self, pmid_or_doi: str, email: str = None) -> str:
        """
        通过 CrossRef API 查询 DOI（支持传入PMID或DOI，自动判断）。
        """
        # CrossRef API 只支持通过DOI查元数据，不支持通过PMID查DOI
        # 但部分DOI格式可能需要归一化
        import re
        doi = pmid_or_doi
        # 如果传入的是PMID（纯数字），直接返回None
        if re.fullmatch(r"\d+", pmid_or_doi):
            return None
        # 归一化DOI
        doi = doi.strip().lower().replace("https://doi.org/", "").replace("http://doi.org/", "")
        url = f"https://api.crossref.org/works/{doi}"
        headers = {"User-Agent": f"SLAIS/1.0 (mailto:{email or self.email})"}
        try:
            timeout = aiohttp.ClientTimeout(total=getattr(self, "timeout", 20))
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=timeout) as response:
                    if response.status != 200:
                        logger.warning(f"[PubMedClient] CrossRef API 查询失败，状态码: {response.status}，DOI: {doi}")
                        return None
                    data = await response.json()
                    # CrossRef返回的DOI在 message.doi
                    message = data.get("message")
                    if message and message.get("DOI"):
                        return message.get("DOI")
                    return None
        except Exception as e:
            logger.error(f"通过 CrossRef 查询 DOI (PMID {pmid_or_doi}) 时发生未知错误: {e}")
            return None

    @retry(
        stop=stop_after_attempt(config.settings.PUBMED_RETRY_COUNT), # 使用配置的重试次数
        wait=wait_exponential(multiplier=1, min=1, max=10), # 指数等待
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)), # 更新为aiohttp的异常类型
        before_sleep=before_sleep_log(logger, logging.WARNING), # 重试前记录日志
        reraise=True # 重试失败后重新引发异常
    )
    async def get_related_articles(self, pmid: str, max_results: Optional[int] = None, years_back: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取与PMID相关的文章"""
        if not pmid:
            return []
        
        # 处理 max_results 参数
        effective_max_results = self.max_results
        if max_results is not None:
            try:
                val = int(max_results)
                if val > 0:
                    effective_max_results = val
                else:
                    logger.warning(f"Provided max_results ({max_results}) is not positive, using instance default: {self.max_results}")
            except (ValueError, TypeError):
                logger.warning(f"Invalid max_results value ('{max_results}') provided, using instance default: {self.max_results}")
        
        # 处理 years_back 参数
        effective_years_back = self.years_back
        if years_back is not None:
            try:
                val = int(years_back)
                if val >= 0: # years_back can be 0
                    effective_years_back = val
                else:
                    logger.warning(f"Provided years_back ({years_back}) is negative, using instance default: {self.years_back}")
            except (ValueError, TypeError):
                logger.warning(f"Invalid years_back value ('{years_back}') provided, using instance default: {self.years_back}")
            
        logger.info(f"Getting related articles for PMID: {pmid}, max_results: {effective_max_results}, years_back: {effective_years_back}")

        # 获取今天的日期和N年前的日期
        today = datetime.now()
        years_ago_date = today - timedelta(days=effective_years_back*365.25)
        min_date = years_ago_date.strftime("%Y/%m/%d")
        max_date = today.strftime("%Y/%m/%d")
        
        # 构建URL时添加斜杠，并使用 cmd=neighbor_history 获取相关文章
        url = f"{self.base_url}/elink.fcgi?dbfrom=pubmed&db=pubmed&id={pmid}&cmd=neighbor_history&retmode=json&email={self.email}&tool={self.tool}"
        if self.api_key:
            url += f"&api_key={self.api_key}"
            
        try:
            headers = {'User-Agent': f'{self.tool}/1.0 ({self.email})'}
            
            # 步骤1：使用 elink 获取相关文章历史记录
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                
                async with session.get(url, headers=headers, timeout=timeout, ssl=self.ssl_verify) as response:
                    response.raise_for_status()
                    elink_data = await response.json()
                    
                    # 提取WebEnv和QueryKey
                    webenv = None
                    query_key = None
                    
                    if "linksets" in elink_data and len(elink_data["linksets"]) > 0:
                        linkset = elink_data["linksets"][0]
                        if "webenv" in linkset:
                            webenv = linkset["webenv"]
                        if "linksetdbhistories" in linkset and len(linkset["linksetdbhistories"]) > 0:
                            for history in linkset["linksetdbhistories"]:
                                if history.get("linkname") == "pubmed_pubmed":
                                    query_key = history.get("querykey")
                                    break
                    
                    if not webenv or not query_key:
                        logger.warning(f"未能从elink响应中提取WebEnv或QueryKey。响应数据: {elink_data}")
                        return []
                    
                    # 步骤2：使用esearch过滤最近N年的相关文章
                    esearch_url = f"{self.base_url}/esearch.fcgi?db=pubmed&query_key={query_key}&WebEnv={webenv}&usehistory=y&retmax=0&datetype=pdat&mindate={min_date}&maxdate={max_date}&retmode=json&email={self.email}&tool={self.tool}"
                    if self.api_key:
                        esearch_url += f"&api_key={self.api_key}"
                    
                    async with session.get(esearch_url, headers=headers, timeout=timeout, ssl=self.ssl_verify) as response:
                        response.raise_for_status()
                        esearch_data = await response.json()
                        
                        # 提取过滤后的计数、WebEnv和QueryKey
                        count = 0
                        filtered_webenv = None
                        filtered_query_key = None
                        
                        if "esearchresult" in esearch_data:
                            result = esearch_data["esearchresult"]
                            if "count" in result:
                                try:
                                    count = int(result["count"])
                                except ValueError:
                                    logger.error(f"无法将count值 '{result['count']}' 转换为整数")
                            filtered_webenv = result.get("webenv")
                            filtered_query_key = result.get("querykey")
                        
                        if count == 0 or not filtered_webenv or not filtered_query_key:
                            logger.info(f"在最近 {effective_years_back} 年内未找到相关文章，或无法获取过滤后的WebEnv/QueryKey")
                            return []
                        
                        # 步骤3：获取相关文章的详细信息
                        # 限制最大结果数
                        actual_max = min(count, effective_max_results)
                        
                        # 计算需要多少批次
                        num_batches = math.ceil(actual_max / self.efetch_batch_size)
                        
                        all_results = []
                        
                        for batch in range(num_batches):
                            start = batch * self.efetch_batch_size
                            retmax = min(self.efetch_batch_size, actual_max - start)
                            
                            efetch_url = f"{self.base_url}/efetch.fcgi?db=pubmed&query_key={filtered_query_key}&WebEnv={filtered_webenv}&retstart={start}&retmax={retmax}&retmode=xml&email={self.email}&tool={self.tool}"
                            if self.api_key:
                                efetch_url += f"&api_key={self.api_key}"
                            
                            async with session.get(efetch_url, headers=headers, timeout=timeout, ssl=self.ssl_verify) as response:
                                response.raise_for_status()
                                efetch_text = await response.text()
                                
                                # 解析XML响应
                                efetch_xml = ET.fromstring(efetch_text)
                                article_elements = efetch_xml.findall(".//PubmedArticle")
                                
                                for article_element in article_elements:
                                    article_details = parse_pubmed_article(article_element)
                                    if article_details:
                                        # 如果从 PubMed XML 中没有提取到 DOI 但有 PMID，尝试通过 CrossRef 获取
                                        if not article_details.get("doi") and article_details.get("pmid"):
                                            logger.debug(f"PMID {article_details['pmid']} 的 DOI 在 PubMed XML 中未找到，尝试通过 CrossRef 获取。")
                                            crossref_doi = await self._get_doi_from_pmid_crossref(article_details["pmid"], session)
                                            if crossref_doi:
                                                article_details["doi"] = crossref_doi
                                        
                                        # 创建一个标准格式的结果字典
                                        result = {
                                            "doi": article_details.get("doi", ""),  # 使用提取或补充的 DOI
                                            "pmid": article_details.get("pmid", ""),
                                            "pmid_link": article_details.get("pmid_link", ""),
                                            "title": article_details.get("title", ""),
                                            "authors": article_details.get("authors", []),
                                            "pub_date": article_details.get("publication_date", ""),
                                            "journal": article_details.get("journal", ""),
                                            "abstract": article_details.get("abstract", ""),
                                            "pmcid": article_details.get("pmcid", ""),
                                            "pmcid_link": article_details.get("pmcid_link", ""),
                                            "citation_count": "",  # 从PubMed无法直接获取
                                            "s2_paper_id": ""  # PubMed不提供S2 ID
                                        }
                                        all_results.append(result)
                            
                            # 如果不是最后一批，加入延迟
                            if batch < num_batches - 1:
                                await asyncio.sleep(config.settings.PUBMED_REQUEST_DELAY or 0.33) # 默认延迟约1/3秒
                        
                        logger.info(f"Found {len(all_results)} related articles for PMID: {pmid}")
                        return all_results[:effective_max_results]  # 确保不超过请求的最大数量
                
        except aiohttp.ClientResponseError as e:
            logger.error(f"Error getting related articles for PMID {pmid}: {e.status}, message='{e.message}', url='{url}'")
            return []
        except Exception as e:
            logger.error(f"Generic error getting related articles for PMID {pmid}: {str(e)}")
            return []

    @retry(
        stop=stop_after_attempt(config.settings.PUBMED_RETRY_COUNT),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)), # 更新为aiohttp的异常类型
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def get_article_details_by_pmid(self, pmid: str, email: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        异步根据PMID获取文章的详细信息。
        处理潜在的网络错误和其他异常。
        """
        if not pmid:
            logger.warning("[PubMedClient] PMID为空，无法获取文章详情。")
            return None

        logger.info(f"[PubMedClient] 正在通过PMID '{pmid}' 获取文章详情...")
        
        efetch_url = f"{self.base_url}/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
            "tool": self.tool,
            "email": email or self.email,
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession() as session:
                async with session.get(efetch_url, params=params, timeout=timeout, ssl=self.ssl_verify) as response:
                    response.raise_for_status()
                    
                    # 解析XML响应
                    xml_content = await response.text()
                    root = ET.fromstring(xml_content)
                    
                    # 查找第一个PubmedArticle元素
                    article_element = root.find(".//PubmedArticle")
                    if article_element is None:
                        logger.warning(f"[PubMedClient] PMID {pmid} 的响应中未找到PubmedArticle元素。")
                        return None
                    
                    # 使用辅助函数解析文章
                    article_details = parse_pubmed_article(article_element)
                    if article_details:
                        # 如果从 PubMed XML 中没有提取到 DOI 但有 PMID，尝试通过 CrossRef 获取
                        if not article_details.get("doi") and article_details.get("pmid"):
                            logger.debug(f"[PubMedClient] PMID {article_details['pmid']} 的 DOI 在 PubMed XML 中未找到，尝试通过 CrossRef 获取。")
                            crossref_doi = await self._get_doi_from_pmid_crossref(article_details["pmid"], session)
                            if crossref_doi:
                                article_details["doi"] = crossref_doi
                        
                        logger.info(f"[PubMedClient] 成功获取PMID {pmid} 的文章详情。")
                        return article_details
                    else:
                        logger.warning(f"[PubMedClient] 解析PMID {pmid} 的文章详情失败。")
                        return None
                
        except aiohttp.ClientResponseError as e:
            logger.error(f"[PubMedClient] 通过PMID '{pmid}' 获取文章详情时发生HTTP状态错误: {e.status} - {e.message}")
            # 对于404等特定错误，可能不需要重试
            if e.status == 404:
                return None
            raise  # 其他HTTP错误重新引发，由tenacity处理
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"[PubMedClient] 通过PMID '{pmid}' 获取文章详情时发生网络传输错误: {type(e).__name__} - {e}")
            raise  # 重新引发，由tenacity处理
        except ET.ParseError as e:
            logger.error(f"[PubMedClient] 解析PMID '{pmid}' 的XML响应时出错: {e}")
            return None
        except Exception as e:
            logger.exception(f"[PubMedClient] 通过PMID '{pmid}' 获取文章详情时发生意外错误: {e}")
            raise  # 重新引发，由tenacity处理

    async def get_articles_by_pmids(self, pmids: List[str], email: str) -> List[Dict[str, Any]]:
        """通过PMID列表批量获取文章详情。"""
        if not pmids: return []
        logger.info(f"开始为 {len(pmids)} 个PMID批量获取文章详情 (PubMed efetch)。")
        
        all_article_details: List[Dict[str, Any]] = []
        pmid_batches = [pmids[i:i + self.efetch_batch_size] for i in range(0, len(pmids), self.efetch_batch_size)]
        headers = {'User-Agent': f'{self.tool}/1.0 ({email})'}

        timeout = aiohttp.ClientTimeout(total=self.timeout * 2) # 批量请求可能需要更长时间
        async with aiohttp.ClientSession() as session:
            for i, pmid_batch in enumerate(pmid_batches):
                if not pmid_batch: continue
                logger.info(f"正在处理PMID批次 {i+1}/{len(pmid_batches)} (数量: {len(pmid_batch)}) (PubMed efetch)")
                efetch_params = {
                    'db': 'pubmed', 'id': ",".join(pmid_batch), 'rettype': 'xml',
                    'retmode': 'xml', 'email': email, 'tool': self.tool
                }
                try:
                    async with session.get(f"{self.base_url}/efetch.fcgi", params=efetch_params, headers=headers, timeout=timeout, ssl=self.ssl_verify) as response:
                        response.raise_for_status()
                        efetch_content = await response.text()
                        efetch_xml = ET.fromstring(efetch_content)
                        articles_xml = efetch_xml.findall(".//PubmedArticle")
                        
                        # 为每一批创建需要进行 CrossRef DOI 查询的任务列表
                        tasks = []
                        parsed_articles_in_batch = []
                        
                        # 先解析所有文章并准备异步查询 CrossRef
                        for article_xml_elem in articles_xml:
                            details = parse_pubmed_article(article_xml_elem)
                            parsed_articles_in_batch.append(details)  # 可能包含 None
                            
                            if details and not details.get("doi") and details.get("pmid"):
                                # 如果没有 DOI 但有 PMID，准备任务
                                tasks.append(self._get_doi_from_pmid_crossref(details["pmid"], session))
                            else:
                                # 如果已有 DOI 或没有 PMID，创建一个立即完成的任务
                                tasks.append(asyncio.sleep(0, result=details.get("doi") if details else None))
                        
                        # 并行执行所有 CrossRef 查询
                        crossref_results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # 将 CrossRef 结果应用到解析的文章中
                        for idx, article_details in enumerate(parsed_articles_in_batch):
                            if article_details is None:
                                continue
                                
                            crossref_result = crossref_results[idx]
                            if isinstance(crossref_result, Exception):
                                logger.error(f"CrossRef 查询 PMID {article_details.get('pmid', 'unknown')} 出错: {crossref_result}")
                            elif crossref_result and not article_details.get("doi"):
                                # 如果 CrossRef 查询成功并且之前没有 DOI
                                article_details["doi"] = crossref_result
                                
                            # 创建结果字典
                            result = {
                                "doi": article_details.get("doi", ""),  # 使用提取或补充的 DOI
                                "pmid": article_details.get("pmid", ""),
                                "pmid_link": article_details.get("pmid_link", ""),
                                "title": article_details.get("title", ""),
                                "authors": article_details.get("authors", []),
                                "authors_str": "; ".join(article_details.get("authors", [])) if article_details.get("authors") else "",
                                "pub_date": article_details.get("publication_date", ""),
                                "journal": article_details.get("journal", ""),
                                "abstract": article_details.get("abstract", ""),
                                "pmcid": article_details.get("pmcid", ""),
                                "pmcid_link": article_details.get("pmcid_link", ""),
                                "citation_count": "",
                                "s2_paper_id": ""
                            }
                            all_article_details.append(result)
                    
                except aiohttp.ClientResponseError as e:
                    logger.error(f"批量efetch PMIDs时 HTTP错误: {e.status} - {e.request_info.url}")
                except Exception as e:
                    logger.error(f"批量efetch PMIDs时发生错误: {e}")
                
                if i < len(pmid_batches) - 1: # 批次间延迟
                    await asyncio.sleep(getattr(config.settings, 'PUBMED_REQUEST_DELAY', 0.33))
                    
        logger.info(f"批量获取完成，共获得 {len(all_article_details)} 篇文章的详细信息。")
        return all_article_details

    async def get_article_details_by_doi(self, doi: str, email: Optional[str] = None, max_retries: int = 5) -> Optional[Dict[str, Any]]:
        """
        异步根据DOI获取文章的详细信息（先用esearch查PMID，再用efetch查详情）。
        增加限流与指数退避重试。
        """
        if not doi:
            logger.warning("[PubMedClient] DOI为空，无法获取文章详情。")
            return None

        logger.info(f"[PubMedClient] 正在通过DOI '{doi}' 获取文章详情...")

        esearch_url = f"{self.base_url}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": f"{doi}[DOI]",
            "retmode": "json",
            "tool": self.tool,
            "email": email or self.email,
        }
        if self.api_key:
            params["api_key"] = self.api_key

        for attempt in range(max_retries):
            await self._wait_for_rate_limit()
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession() as session:
                    async with session.get(esearch_url, params=params, timeout=timeout, ssl=self.ssl_verify) as response:
                        if response.status == 429:
                            wait_time = min(2 ** attempt, 30)
                            logger.warning(f"[PubMedClient] 429 Too Many Requests, attempt {attempt+1}/{max_retries}, 等待 {wait_time}s")
                            await asyncio.sleep(wait_time)
                            continue
                        response.raise_for_status()
                        data = await response.json()
                        idlist = data.get("esearchresult", {}).get("idlist", [])
                        if not idlist:
                            logger.warning(f"[PubMedClient] DOI {doi} 未找到对应的PMID。")
                            return None
                        pmid = idlist[0]
                        return await self.get_article_details_by_pmid(pmid, email)
            except Exception as e:
                logger.error(f"[PubMedClient] 通过DOI '{doi}' 获取文章详情时出错: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(min(2 ** attempt, 30))
                else:
                    return None
        return None

    async def batch_get_pmids_from_dois(self, dois: List[str], email: Optional[str] = None) -> Dict[str, Optional[str]]:
        """
        批量通过DOI获取PMID，限流与重试。
        """
        result = {}
        for doi in dois:
            pmid = None
            try:
                details = await self.get_article_details_by_doi(doi, email)
                if details and details.get("pmid"):
                    pmid = details["pmid"]
            except Exception as e:
                logger.warning(f"[PubMedClient] 批量获取PMID时DOI {doi} 出错: {e}")
            result[doi] = pmid
        return result

    async def batch_get_article_details_by_pmids(self, pmids: List[str], email: Optional[str] = None, batch_size: int = 100) -> List[Dict[str, Any]]:
        """
        批量通过PMID获取文章详情，支持批量efetch，限流与重试。
        """
        results = []
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i:i+batch_size]
            for attempt in range(5):
                await self._wait_for_rate_limit()
                try:
                    # ...efetch批量请求逻辑...
                    # 假设有 self.get_article_details_by_pmid_batch(batch, email)
                    batch_results = await self.get_article_details_by_pmid_batch(batch, email)
                    results.extend(batch_results)
                    break
                except Exception as e:
                    logger.warning(f"[PubMedClient] 批量efetch失败，重试 {attempt+1}/5: {e}")
                    await asyncio.sleep(min(2 ** attempt, 30))
        return results

    async def get_article_details(self, identifier: str, email: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        根据提供的标识符类型（PMID或DOI）获取文章详情。
        自动检测标识符类型并调用相应的方法。
        
        Args:
            identifier: PMID或DOI标识符
            email: 可选，覆盖默认邮箱
        
        Returns:
            文章详情字典或None（如果找不到）
        """
        if not identifier:
            logger.warning("[PubMedClient] 提供的标识符为空")
            return None
            
        # 判断标识符类型：如果是纯数字或以"PMC"开头的数字，则视为PMID
        if identifier.isdigit() or (identifier.startswith("PMC") and identifier[3:].isdigit()):
            logger.info(f"[PubMedClient] 将标识符 '{identifier}' 识别为PMID，调用get_article_details_by_pmid")
            return await self.get_article_details_by_pmid(identifier, email)
        else:
            # 假设其他形式的标识符是DOI
            logger.info(f"[PubMedClient] 将标识符 '{identifier}' 识别为DOI，调用get_article_details_by_doi")
            return await self.get_article_details_by_doi(identifier, email)
