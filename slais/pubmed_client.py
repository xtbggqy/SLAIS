import httpx
import urllib.parse
import json
import xml.etree.ElementTree as ET # 用于解析XML
import re   # 用于正则表达式处理
import math # 用于向上取整除法
import asyncio # 用于异步休眠
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
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
    """PubMed API客户端"""
    
    def __init__(self):
        # 从config加载配置而不是直接从环境变量加载
        self.base_url = config.PUBMED_API_BASE_URL
        self.email = config.NCBI_EMAIL
        self.tool = config.PUBMED_TOOL_NAME
        self.max_results = config.RELATED_ARTICLES_MAX  # 使用正确配置的整数值
        self.years_back = config.RELATED_ARTICLES_YEARS_BACK
        self.batch_size = config.PUBMED_EFETCH_BATCH_SIZE
        self.timeout = config.PUBMED_REQUEST_TIMEOUT
        self.delay = config.PUBMED_REQUEST_DELAY
        self.retry_count = config.PUBMED_RETRY_COUNT

    def _extract_text(self, element: Optional[ET.Element]) -> str:
        return element.text.strip() if element is not None and element.text else ""

    def _parse_article_details_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        articles = []
        try:
            root = ET.fromstring(xml_content)
            for article_xml in root.findall('.//PubmedArticle'):
                pmid_val = self._extract_text(article_xml.find(".//PMID"))
                title = self._extract_text(article_xml.find(".//ArticleTitle"))
                
                authors_list = []
                author_list_xml = article_xml.find(".//AuthorList")
                if author_list_xml is not None:
                    for author_xml in author_list_xml.findall(".//Author"):
                        lastname = self._extract_text(author_xml.find(".//LastName"))
                        forename = self._extract_text(author_xml.find(".//ForeName"))
                        if lastname:
                            authors_list.append(f"{forename} {lastname}" if forename else lastname)

                journal_title = self._extract_text(article_xml.find(".//Journal/Title"))
                pub_date_year = self._extract_text(article_xml.find(".//Journal/JournalIssue/PubDate/Year"))
                pub_date_month = self._extract_text(article_xml.find(".//Journal/JournalIssue/PubDate/Month"))
                pub_date_day = self._extract_text(article_xml.find(".//Journal/JournalIssue/PubDate/Day"))
                
                pub_date_medline = self._extract_text(article_xml.find(".//Journal/JournalIssue/PubDate/MedlineDate"))

                if pub_date_year and pub_date_month and pub_date_day:
                    pub_date = f"{pub_date_year}-{pub_date_month}-{pub_date_day}"
                elif pub_date_year and pub_date_month:
                    pub_date = f"{pub_date_year}-{pub_date_month}"
                elif pub_date_year:
                    pub_date = pub_date_year
                elif pub_date_medline: # Fallback to MedlineDate if structured date is not available
                    pub_date = pub_date_medline
                else:
                    pub_date = ""

                abstract_parts = [self._extract_text(p) for p in article_xml.findall(".//Abstract/AbstractText")]
                abstract = "\n".join(filter(None, abstract_parts))
                
                pmcid_element = article_xml.find(".//ArticleIdList/ArticleId[@IdType='pmc']")
                pmcid = pmcid_element.text.strip() if pmcid_element is not None and pmcid_element.text else ""

                # Corrected DOI Extraction
                doi_element = article_xml.find("./MedlineCitation/Article/ArticleIdList/ArticleId[@IdType='doi']")
                if doi_element is None: # Fallback to ELocationID
                    doi_element = article_xml.find("./MedlineCitation/Article/ELocationID[@EIdType='doi']")
                
                doi = self._extract_text(doi_element)

                article_data = {
                    "pmid": pmid_val,
                    "title": title,
                    "authors": authors_list,
                    "journal": journal_title,
                    "pub_date": pub_date,
                    "abstract": abstract,
                    "pmcid": pmcid,
                    "doi": doi,
                    "pmid_link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid_val}/" if pmid_val else "",
                    "pmcid_link": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else "",
                }
                articles.append(article_data)
        except ET.ParseError as e:
            logger.error(f"[PubMedClient] XML解析错误: {e}")
        return articles

    @retry(stop=stop_after_attempt(config.PUBMED_RETRY_COUNT), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def batch_get_article_details_by_pmids(self, pmids: List[str], email: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        if not pmids:
            return {}
        
        unique_pmids = sorted(list(set(filter(None, pmids))))
        if not unique_pmids:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        email_to_use = email or config.NCBI_EMAIL
        if not email_to_use:
            logger.warning("[PubMedClient] 未提供邮箱地址，PubMed API请求可能受限。")

        tool = config.PUBMED_TOOL_NAME
        base_url = config.PUBMED_API_BASE_URL.rstrip('/')
        efetch_url = f"{base_url}/efetch.fcgi"
        batch_size = config.PUBMED_EFETCH_BATCH_SIZE

        async with httpx.AsyncClient(timeout=config.PUBMED_REQUEST_TIMEOUT) as client:
            for i in range(0, len(unique_pmids), batch_size):
                batch_pmids = unique_pmids[i:i+batch_size]
                params = {
                    "db": "pubmed",
                    "id": ",".join(batch_pmids),
                    "retmode": "xml",
                    "tool": tool,
                    "email": email_to_use
                }
                
                logger.info(f"[PubMedClient] 批量获取PMID详情: {len(batch_pmids)}个 (批次 {i//batch_size + 1})")
                
                try:
                    response = await client.get(efetch_url, params=params)
                    response.raise_for_status()
                    
                    parsed_articles = self._parse_article_details_xml(response.text)
                    for article_detail in parsed_articles:
                        if article_detail.get('pmid'):
                            results[article_detail['pmid']] = article_detail
                        else:
                            logger.warning(f"[PubMedClient] 解析到的文章缺少PMID: {str(article_detail)[:100]}")
                            
                    if len(batch_pmids) > 1 and i + batch_size < len(unique_pmids): # Avoid sleep for single batch or last batch
                        await asyncio.sleep(config.PUBMED_REQUEST_DELAY) # Respect NCBI rate limits

                except httpx.HTTPStatusError as e:
                    logger.error(f"[PubMedClient] 批量获取PMID详情时HTTP错误: {e.response.status_code} - {e.response.text[:200]}")
                except httpx.RequestError as e:
                    logger.error(f"[PubMedClient] 批量获取PMID详情时请求错误: {e}")
                except Exception as e:
                    logger.exception(f"[PubMedClient] 批量获取PMID详情时发生意外错误: {e}")
        
        logger.info(f"[PubMedClient] 成功获取 {len(results)}/{len(unique_pmids)} 个PMID的详细信息。")
        return results

    async def get_article_details_by_pmid(self, pmid: str, email: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        异步根据PMID获取单篇PubMed文章的详细信息。
        """
        if not pmid:
            logger.debug(f"[PubMedClient] get_article_details_by_pmid 调用时未提供 pmid。")
            return None
        
        logger.debug(f"[PubMedClient] 准备为单个 pmid 调用 batch_get_article_details_by_pmids: {pmid}")
        try:
            results_dict = await self.batch_get_article_details_by_pmids(pmids=[pmid], email=email)
            article_detail = results_dict.get(pmid)
            if article_detail:
                logger.debug(f"[PubMedClient] 成功获取 pmid 的详细信息: {pmid}")
            else:
                logger.warning(f"[PubMedClient] 未能从批量调用中获取 pmid 的详细信息: {pmid}")
            return article_detail
        except Exception as e:
            logger.exception(f"[PubMedClient] get_article_details_by_pmid 执行 pmid: {pmid} 时出错: {e}")
            return None

    async def get_related_articles(self, pmid: str, max_results: int = None, years_back: int = None) -> List[Dict[str, Any]]:
        """
        获取与PMID相关的文章
        
        参数:
            pmid: PubMed ID
            max_results: 最大结果数量，如果为None则使用配置值
            years_back: 回溯年数，如果为None则使用配置值
        返回:
            相关文章列表
        """
        if not pmid:
            return []
        
        # 使用参数值或默认配置值
        if max_results is None:
            max_results = self.max_results
        try:
            max_results = int(max_results)
        except (ValueError, TypeError):
            logger.warning(f"Invalid max_results value, using default: {self.max_results}")
            max_results = self.max_results
            
        if years_back is None:
            years_back = self.years_back
        try:
            years_back = int(years_back)
        except (ValueError, TypeError):
            logger.warning(f"Invalid years_back value, using default: {self.years_back}")
            years_back = self.years_back
            
        logger.info(f"Getting related articles for PMID: {pmid}, max_results: {max_results}, years_back: {years_back}")
        
        # 构建URL时添加参数
        url = f"{self.base_url}elink.fcgi?dbfrom=pubmed&db=pubmed&id={pmid}&cmd=neighbor&retmode=json&retmax={max_results}&tool={self.tool}&email={self.email}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    related_pmids = []
                    try:
                        related_links = data["linksets"][0]["linksetdbs"]
                        for link_item in related_links:
                            if link_item["linkname"] == "pubmed_pubmed":
                                related_pmids = [str(link_pmid) for link_pmid in link_item["links"]]
                                if isinstance(max_results, int) and max_results > 0:
                                    related_pmids = related_pmids[:max_results]
                                break
                    except (KeyError, IndexError, TypeError) as e:
                        logger.warning(f"Failed to get related PMIDs from response for PMID: {pmid}, error: {str(e)}")
                        return []
                    
                    if not related_pmids:
                        logger.info(f"No related PMIDs found for PMID: {pmid}")
                        return []
                        
                    logger.info(f"Found {len(related_pmids)} related PMIDs for PMID: {pmid}")
                    return await self.get_articles_by_pmids(related_pmids)
        except Exception as e:
            logger.error(f"Error getting related articles for PMID {pmid}: {str(e)}")
            return []

    async def get_articles_by_pmids(self, pmids: List[str]) -> List[Dict[str, Any]]:
        """通过PMID列表获取文章详情"""
        if not pmids:
            return []
            
        pmids_str = ",".join(pmids)
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmids_str}&retmode=json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    results = []
                    for pmid in pmids:
                        if pmid in data["result"]:
                            article_data = data["result"][pmid]
                            # 尝试提取DOI
                            doi = ""
                            if "articleids" in article_data:
                                for id_obj in article_data["articleids"]:
                                    if id_obj["idtype"] == "doi":
                                        doi = id_obj["value"]
                                        break
                                        
                            # 提取PMCID
                            pmcid = ""
                            pmcid_link = ""
                            if "articleids" in article_data:
                                for id_obj in article_data["articleids"]:
                                    if id_obj["idtype"] == "pmc":
                                        pmcid = id_obj["value"]
                                        if pmcid.startswith("PMC"):
                                            pmcid_link = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
                                        break
                            
                            # 提取作者信息
                            authors = []
                            if "authors" in article_data and article_data["authors"]:
                                authors = [author.get("name", "") for author in article_data["authors"]]
                            authors_str = "; ".join(authors)
                            
                            result = {
                                "doi": doi,
                                "pmid": pmid,
                                "pmid_link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                                "title": article_data.get("title", ""),
                                "authors_str": authors_str,
                                "pub_date": article_data.get("pubdate", ""),
                                "journal": article_data.get("source", ""),
                                "abstract": article_data.get("abstract", ""),
                                "pmcid": pmcid,
                                "pmcid_link": pmcid_link,
                                "citation_count": "",
                                "s2_paper_id": ""
                            }
                            results.append(result)
                    
                    logger.info(f"Retrieved {len(results)} articles details from PMIDs")
                    return results
        except Exception as e:
            logger.error(f"Error getting articles by PMIDs {pmids}: {str(e)}")
            return []
