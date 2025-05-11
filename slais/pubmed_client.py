import httpx
import urllib.parse
import json
import xml.etree.ElementTree as ET # 用于解析XML
import re   # 用于正则表达式处理
import math # 用于向上取整除法
import asyncio # 用于异步休眠
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import List, Optional, Dict, Any, TypedDict # 导入 TypedDict
from datetime import datetime, timedelta # 用于日期处理

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
    try:
        medline_citation = article_xml.find("./MedlineCitation")
        pubmed_data = article_xml.find("./PubmedData")

        if medline_citation is None:
             return None 

        pmid = medline_citation.findtext("./PMID")
        article = medline_citation.find("./Article")

        if article is None or pmid is None:
             return None 

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
        }
    except Exception as e:
        logger.error(f"错误: 解析文章 PMID {pmid or 'UNKNOWN'} 时出错: {e}")
        return None

class PubMedClient:
    def __init__(self):
        self.base_url = config.PUBMED_API_BASE_URL
        self.tool_name = config.PUBMED_TOOL_NAME
        self.efetch_batch_size = config.PUBMED_EFETCH_BATCH_SIZE

    @retry(stop=stop_after_attempt(config.PUBMED_RETRY_COUNT), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_article_details(self, doi: str, email: str) -> Optional[ArticleDetails]:
        logger.info(f"开始为 DOI: {doi} 搜索 PubMed (使用邮箱: {email})")
        if not email or '@' not in email:
             logger.error("输入中未提供有效邮箱地址。NCBI E-utils 要求提供邮箱。")
             return None
        headers = {'User-Agent': f'{self.tool_name}/1.0 ({email})'}
        try:
            logger.info(f"步骤 1: 正在为 DOI {doi} 搜索 PMID")
            esearch_params = {
                'db': 'pubmed', 'term': f"{urllib.parse.quote(doi)}[doi]", 
                'retmax': 1, 'retmode': 'xml', 'email': email, 'tool': self.tool_name
            }
            async with httpx.AsyncClient(timeout=config.PUBMED_REQUEST_TIMEOUT) as client:
                response_esearch = await client.get(f"{self.base_url}esearch.fcgi", params=esearch_params, headers=headers)
                response_esearch.raise_for_status()
                esearch_xml = ET.fromstring(response_esearch.content)
                ids = esearch_xml.findall(".//Id")
            if not ids:
                logger.warning(f"未找到 DOI: {doi} 对应的 PubMed 记录")
                return None
            initial_pmid = ids[0].text
            logger.info(f"找到初始文章 PMID: {initial_pmid}")

            logger.info(f"步骤 2: 正在获取初始 PMID {initial_pmid} 的详细信息")
            efetch_params = {
                'db': 'pubmed', 'id': initial_pmid, 'rettype': 'xml', 
                'retmode': 'xml', 'email': email, 'tool': self.tool_name
            }
            async with httpx.AsyncClient(timeout=config.PUBMED_REQUEST_TIMEOUT) as client:
                response_efetch = await client.get(f"{self.base_url}efetch.fcgi", params=efetch_params, headers=headers)
                response_efetch.raise_for_status()
                efetch_xml = ET.fromstring(response_efetch.content)
                original_article_xml = efetch_xml.find(".//PubmedArticle")
            
            original_article_details = parse_pubmed_article(original_article_xml)
            if original_article_details is None:
                 logger.error(f"无法解析初始 PMID: {initial_pmid} 的文章信息")
                 return None
            logger.info(f"成功获取并解析初始文章 PMID: {initial_pmid}")
            return original_article_details
        except httpx.HTTPStatusError as e:
             logger.error(f"HTTP 错误: {e.response.status_code} - {e.request.url}\n响应内容: {e.response.text[:500]}", exc_info=False)
             return None
        except httpx.RequestError as e: logger.error(f"网络错误 (DOI: {doi}): {e}", exc_info=True); return None
        except ET.ParseError as e: logger.error(f"XML 解析错误 (DOI: {doi}): {e}", exc_info=True); return None
        except Exception as e: logger.exception(f"获取文章详情时发生意外错误 (DOI: {doi}): {e}"); return None

    @retry(stop=stop_after_attempt(config.PUBMED_RETRY_COUNT), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_article_details_by_pmid(self, pmid: str, email: str) -> Optional[ArticleDetails]:
        """通过PMID获取文章详情。"""
        if not pmid: return None
        logger.info(f"正在通过 PMID: {pmid} 获取 PubMed 文章详情 (使用邮箱: {email})")
        headers = {'User-Agent': f'{self.tool_name}/1.0 ({email})'}
        efetch_params = {
            'db': 'pubmed', 'id': pmid, 'rettype': 'xml',
            'retmode': 'xml', 'email': email, 'tool': self.tool_name
        }
        try:
            async with httpx.AsyncClient(timeout=config.PUBMED_REQUEST_TIMEOUT) as client:
                response_efetch = await client.get(f"{self.base_url}efetch.fcgi", params=efetch_params, headers=headers)
                response_efetch.raise_for_status()
                efetch_xml = ET.fromstring(response_efetch.content)
                article_xml_elem = efetch_xml.find(".//PubmedArticle") # 假设只返回一个
            
            article_details = parse_pubmed_article(article_xml_elem)
            if article_details is None:
                 logger.error(f"无法解析 PMID: {pmid} 的文章信息")
                 return None
            logger.info(f"成功获取并解析 PMID: {pmid} 的文章信息")
            return article_details
        except httpx.HTTPStatusError as e:
             logger.error(f"HTTP 错误 (PMID: {pmid}): {e.response.status_code} - {e.request.url}\n响应内容: {e.response.text[:500]}", exc_info=False)
             return None
        except httpx.RequestError as e: logger.error(f"网络错误 (PMID: {pmid}): {e}", exc_info=True); return None
        except ET.ParseError as e: logger.error(f"XML 解析错误 (PMID: {pmid}): {e}", exc_info=True); return None
        except Exception as e: logger.exception(f"获取文章详情时发生意外错误 (PMID: {pmid}): {e}"); return None

    async def _get_pmid_for_doi(self, doi: str, email: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore) -> Optional[str]:
        """辅助方法：使用esearch通过DOI获取PMID，受信号量控制。"""
        if not doi: return None
        esearch_params = {
            'db': 'pubmed', 'term': f"{urllib.parse.quote(doi)}[DOI]", # 确保[DOI]在term中
            'retmax': 1, 'retmode': 'xml', 'email': email, 'tool': self.tool_name
        }
        async with semaphore: # 获取信号量
            # NCBI建议没有API key时不超过3次请求/秒。我们在这里增加一个小的固定延迟。
            # 实际的速率限制应该由调用者（如batch_get_article_details_by_dois中的循环）或更高级别的速率限制器处理。
            # 但为了防止并发的_get_pmid_for_doi本身触发问题，这里加一个小的延迟。
            await asyncio.sleep(config.PUBMED_REQUEST_DELAY) # 使用配置的延迟
            try:
                logger.debug(f"PubMedClient: Fetching PMID for DOI: {doi}")
                response_esearch = await client.get(f"{self.base_url}esearch.fcgi", params=esearch_params)
                response_esearch.raise_for_status()
                esearch_xml = ET.fromstring(response_esearch.content)
                ids = esearch_xml.findall(".//Id")
                if ids:
                    return ids[0].text
                logger.warning(f"未能从DOI {doi} 获取PMID。")
                return None
            except httpx.HTTPStatusError as e:
                logger.error(f"获取PMID for DOI {doi} 时 HTTP错误: {e.response.status_code} - {e.request.url}")
                # 如果是429，可以考虑在这里也进行退避，或者让上层重试机制处理
                if e.response.status_code == 429:
                    # 可以考虑抛出特定异常或返回特殊值，以便上层进行退避
                    pass # tenacity 会处理重试
                return None
            except Exception as e:
                logger.error(f"获取PMID for DOI {doi} 时发生错误: {e}")
                return None

    @retry(stop=stop_after_attempt(config.S2_RETRY_COUNT), wait=wait_exponential(multiplier=1, min=2, max=60))
    async def batch_get_article_details_by_dois(self, dois: List[str], email: str) -> List[ArticleDetails]:
        """通过一批DOI批量获取文章详情。首先将DOI转为PMID，然后批量获取PMID详情。"""
        if not dois: return []
        logger.info(f"开始为 {len(dois)} 个DOI批量获取文章详情 (PubMed)。")
        
        pmids_map: Dict[str, str] = {} # doi -> pmid
        valid_dois = [d for d in dois if d and isinstance(d, str)]

        semaphore = asyncio.Semaphore(3) # 信号量限制并发的 _get_pmid_for_doi 调用
        async with httpx.AsyncClient(timeout=config.PUBMED_REQUEST_TIMEOUT, headers={'User-Agent': f'{self.tool_name}/1.0 ({email})'}) as client:
            pmid_tasks = {doi: self._get_pmid_for_doi(doi, email, client, semaphore) for doi in valid_dois}
            pmid_results = await asyncio.gather(*pmid_tasks.values(), return_exceptions=True)
            
            for doi, result in zip(pmid_tasks.keys(), pmid_results):
                if isinstance(result, str): pmids_map[doi] = result
                elif isinstance(result, Exception): logger.error(f"获取DOI {doi} 的PMID时发生异常: {result}")
        
        pmids_to_fetch = [pmid for pmid in pmids_map.values() if pmid]
        if not pmids_to_fetch:
            logger.warning("未能从提供的DOI列表中获取任何有效的PMID (PubMed)。")
            return []
        
        logger.info(f"成功将 {len(valid_dois)} 个DOI转换为 {len(pmids_to_fetch)} 个PMID。开始批量efetch (PubMed)。")
        return await self.batch_get_article_details_by_pmids(pmids_to_fetch, email)


    @retry(stop=stop_after_attempt(config.S2_RETRY_COUNT), wait=wait_exponential(multiplier=1, min=2, max=60))
    async def batch_get_article_details_by_pmids(self, pmids: List[str], email: str) -> List[ArticleDetails]:
        """通过一批PMID批量获取文章详情。"""
        if not pmids: return []
        logger.info(f"开始为 {len(pmids)} 个PMID批量获取文章详情 (PubMed efetch)。")
        
        all_article_details: List[ArticleDetails] = []
        pmid_batches = [pmids[i:i + self.efetch_batch_size] for i in range(0, len(pmids), self.efetch_batch_size)]
        headers = {'User-Agent': f'{self.tool_name}/1.0 ({email})'}

        async with httpx.AsyncClient(timeout=config.PUBMED_REQUEST_TIMEOUT * 2, headers=headers) as client: # 批量请求可能需要更长时间
            for i, pmid_batch in enumerate(pmid_batches):
                if not pmid_batch: continue
                logger.info(f"正在处理PMID批次 {i+1}/{len(pmid_batches)} (数量: {len(pmid_batch)}) (PubMed efetch)")
                efetch_params = {
                    'db': 'pubmed', 'id': ",".join(pmid_batch), 'rettype': 'xml',
                    'retmode': 'xml', 'email': email, 'tool': self.tool_name
                }
                try:
                    response_efetch = await client.get(f"{self.base_url}efetch.fcgi", params=efetch_params)
                    response_efetch.raise_for_status()
                    efetch_xml = ET.fromstring(response_efetch.content)
                    articles_xml = efetch_xml.findall(".//PubmedArticle")
                    for article_xml_elem in articles_xml:
                        details = parse_pubmed_article(article_xml_elem)
                        if details:
                            all_article_details.append(details)
                        else:
                            pmid_in_error = article_xml_elem.findtext('./MedlineCitation/PMID', '未知PMID')
                            logger.warning(f"无法解析批量获取中的文章 PMID: {pmid_in_error}")
                except httpx.HTTPStatusError as e:
                    logger.error(f"批量efetch PMIDs时 HTTP错误: {e.response.status_code} - {e.request.url}")
                except Exception as e:
                    logger.error(f"批量efetch PMIDs时发生错误: {e}")
                
                if i < len(pmid_batches) - 1: # 批次间延迟
                    await asyncio.sleep(config.PUBMED_REQUEST_DELAY)
                    
        logger.info(f"批量获取完成，共获得 {len(all_article_details)} 篇文章的详细信息。")
        return all_article_details

    @retry(stop=stop_after_attempt(config.PUBMED_RETRY_COUNT), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_related_articles(self, initial_pmid: str, email: str) -> List[ArticleDetails]:
        years_back = config.RELATED_ARTICLES_YEARS_BACK
        logger.info(f"开始为 PMID: {initial_pmid} 查找最近 {years_back} 年内的相关文章 (使用邮箱: {email})")
        if not email or '@' not in email:
             logger.error("输入中未提供有效邮箱地址。NCBI E-utils 要求提供邮箱。")
             return []
        headers = {'User-Agent': f'{self.tool_name}/1.0 ({email})'}
        related_articles_list: List[ArticleDetails] = []
        try:
            logger.info(f"步骤 1: 正在为 PMID {initial_pmid} 查找相关文章 (elink + history)")
            elink_params = {
                'dbfrom': 'pubmed', 'db': 'pubmed', 'id': initial_pmid, 
                'linkname': 'pubmed_pubmed', 'cmd': 'neighbor_history', 
                'email': email, 'tool': self.tool_name
            }
            async with httpx.AsyncClient(timeout=config.PUBMED_REQUEST_TIMEOUT) as client:
                response_elink = await client.get(f"{self.base_url}elink.fcgi", params=elink_params, headers=headers)
                response_elink.raise_for_status()
                elink_xml = ET.fromstring(response_elink.content)
            webenv_elink = elink_xml.findtext(".//WebEnv")
            query_key_elink = elink_xml.findtext(".//LinkSetDbHistory/QueryKey")
            if not webenv_elink or not query_key_elink:
                logger.info(f"未通过 elink 找到 PMID: {initial_pmid} 的相关文章")
                return []
            logger.info(f"找到相关文章的历史记录 (elink): WebEnv={webenv_elink}, QueryKey={query_key_elink}")

            logger.info(f"步骤 2: 使用 esearch 过滤相关文章 (最近 {years_back} 年)")
            today = datetime.now()
            years_ago_date = today - timedelta(days=years_back*365.25)
            min_date = years_ago_date.strftime("%Y/%m/%d")
            max_date = today.strftime("%Y/%m/%d")
            esearch_params = {
                'db': 'pubmed', 'query_key': query_key_elink, 'WebEnv': webenv_elink,
                'retmax': '0', 'retmode': 'xml', 'datetype': 'pdat', 
                'mindate': min_date, 'maxdate': max_date, 'email': email, 
                'tool': self.tool_name, 'usehistory': 'y'
            }
            async with httpx.AsyncClient(timeout=config.PUBMED_REQUEST_TIMEOUT) as client:
                response_esearch = await client.get(f"{self.base_url}esearch.fcgi", params=esearch_params, headers=headers)
                response_esearch.raise_for_status()
                esearch_xml = ET.fromstring(response_esearch.content)
            total_related_count_str = esearch_xml.findtext(".//Count")
            webenv_filtered = esearch_xml.findtext(".//WebEnv")
            query_key_filtered = esearch_xml.findtext(".//QueryKey")
            if not total_related_count_str or not webenv_filtered or not query_key_filtered:
                 logger.error("未能从过滤后的 esearch 获取计数或历史信息。")
                 return []
            try: total_related_count = int(total_related_count_str)
            except ValueError: logger.error(f"无法将计数 '{total_related_count_str}' 转换为整数。"); return []
            logger.info(f"在最近 {years_back} 年内找到 {total_related_count} 篇相关文章。过滤后的历史记录: WebEnv={webenv_filtered}, QueryKey={query_key_filtered}")
            if total_related_count == 0: return []

            num_batches = math.ceil(total_related_count / self.efetch_batch_size)
            logger.info(f"将分 {num_batches} 批次获取 {total_related_count} 篇相关文章的详细信息 (每批最多 {self.efetch_batch_size} 篇)。")
            async with httpx.AsyncClient(timeout=config.PUBMED_REQUEST_TIMEOUT) as client: # 使用配置的超时
                for i in range(num_batches):
                    retstart = i * self.efetch_batch_size
                    current_batch_size = min(self.efetch_batch_size, total_related_count - retstart)
                    logger.info(f"正在获取批次 {i+1}/{num_batches} (PMID 索引 {retstart+1} 到 {retstart+current_batch_size})...")
                    efetch_params_batch = {
                        'db': 'pubmed', 'query_key': query_key_filtered, 'WebEnv': webenv_filtered,
                        'retstart': str(retstart), 'retmax': str(current_batch_size),
                        'rettype': 'xml', 'retmode': 'xml', 'email': email, 'tool': self.tool_name
                    }
                    response_efetch_batch = await client.get(f"{self.base_url}efetch.fcgi", params=efetch_params_batch, headers=headers)
                    response_efetch_batch.raise_for_status()
                    efetch_xml_batch = ET.fromstring(response_efetch_batch.content)
                    related_article_elements = efetch_xml_batch.findall(".//PubmedArticle")
                    logger.info(f"正在解析批次 {i+1} 中获取到的 {len(related_article_elements)} 篇文章的详细信息。")
                    for article_xml_elem in related_article_elements:
                        details = parse_pubmed_article(article_xml_elem)
                        if details: related_articles_list.append(details)
                        else: logger.warning(f"无法解析批次 {i+1} 中的相关文章 PMID: {article_xml_elem.findtext('./MedlineCitation/PMID', '未知PMID')}")
                    if num_batches > 1 and i < num_batches - 1:
                         await asyncio.sleep(config.PUBMED_REQUEST_DELAY) # 使用配置的延迟
            logger.info(f"成功检索并解析了 {len(related_articles_list)}/{total_related_count} 篇相关文章的详细信息。")
            return related_articles_list
        except httpx.HTTPStatusError as e:
             logger.error(f"HTTP 错误: {e.response.status_code} - {e.request.url}\n响应内容: {e.response.text[:500]}", exc_info=False)
             return []
        except httpx.RequestError as e: logger.error(f"网络错误: {e}", exc_info=True); return []
        except ET.ParseError as e: logger.error(f"XML 解析错误: {e}", exc_info=True); return []
        except Exception as e: logger.exception(f"获取相关文章时发生意外错误: {e}"); return []
