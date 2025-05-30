from typing import List, Optional, Dict, Any
from slais.pubmed_client import PubMedClient, ArticleDetails
from slais.semantic_scholar_client import SemanticScholarClient
from slais.utils.logging_utils import logger
from slais import config # 添加此行导入

class MetadataFetchingAgent:
    def __init__(self):
        self.pubmed_client = PubMedClient()
        self.s2_client = SemanticScholarClient()

    async def fetch_metadata(self, doi: str, email: str) -> Dict[str, Any]:
        """
        获取文章的元数据，包括PubMed和Semantic Scholar信息。
        """
        metadata = {"pubmed_info": None, "s2_info": None}

        # 从PubMed获取信息
        try:
            metadata["pubmed_info"] = await self.pubmed_client.get_article_details(doi, email)  # 修正方法名
        except Exception as e:
            logger.error(f"[MetadataFetchingAgent] 从PubMed获取元数据时出错: {e}")

        original_s2_info: Optional[Dict[str, Any]] = None

        logger.info(f"从配置中获取的DOI: {doi}")
        logger.info(f"从配置中获取的邮箱: {email}")

        logger.info(f"正在从 Semantic Scholar 获取原始文章 (DOI: {doi}) 的信息...")
        original_s2_info = await self.s2_client.get_paper_details_by_doi(doi)

        if original_s2_info and original_s2_info.get('paperId'):
            logger.info(f"成功从S2获取原始文章信息 (S2 PaperID: {original_s2_info['paperId']})")
            # s2_paper_id_original = original_s2_info['paperId'] # Not used further in this method

            s2_external_ids = original_s2_info.get('externalIds', {})
            pmid_from_s2 = s2_external_ids.get('PubMed') if isinstance(s2_external_ids, dict) else None

            if pmid_from_s2:
                logger.info(f"S2提供了PMID: {pmid_from_s2}。正在从PubMed获取/核实...")
                # 如果从S2获得了PMID，直接使用PMID获取PubMed详情
                pubmed_info_s2_pmid = await self.pubmed_client.get_article_details_by_pmid(pmid_from_s2, email)
                if pubmed_info_s2_pmid:
                    metadata["pubmed_info"] = pubmed_info_s2_pmid
                else:
                    logger.warning(f"未能从PubMed获取PMID {pmid_from_s2} 的信息，将主要依赖S2数据。")
            else:
                # S2没有提供PMID，尝试使用原始DOI从PubMed获取
                logger.info("S2未提供PMID。尝试使用原始DOI从PubMed获取信息...")
                pubmed_info_direct_doi = await self.pubmed_client.get_article_details(doi, email)
                if pubmed_info_direct_doi:
                    metadata["pubmed_info"] = pubmed_info_direct_doi
                else:
                    logger.warning(f"也未能通过原始DOI {doi} 从PubMed获取信息。")
        else: # S2未能获取信息
            logger.warning(f"未能从S2获取原始文章信息。尝试直接从PubMed获取 (使用原始DOI: {doi})...")
            pubmed_info_direct_doi = await self.pubmed_client.get_article_details(doi, email)
            if pubmed_info_direct_doi:
                metadata["pubmed_info"] = pubmed_info_direct_doi
            else:
                logger.error(f"从S2和PubMed均未能获取DOI {doi} 的元数据。")

        metadata["s2_info"] = original_s2_info
        logger.info("元数据获取完成。")
        return metadata
        
    async def fetch_related_articles(self, pmid: str, email: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取与给定PMID相关的文献列表 (来自PubMed)。
        """
        logger.info(f"正在从PubMed获取PMID:{pmid}的相关文章...")
        related_articles: List[ArticleDetails] = []
        try:
            related_articles = await self.pubmed_client.get_related_articles(pmid, email)
            logger.info(f"成功获取 {len(related_articles)} 篇PubMed相关文章")
        except Exception as e:
            logger.error(f"获取PubMed相关文章时出错: {e}")
        return related_articles
    
    async def fetch_references(self, paper_id: str, email: Optional[str] = None) -> Dict[str, Any]:
        """
        获取给定S2 Paper ID的参考文献详细信息。
        利用SemanticScholarClient的batch_get_references_by_papers方法。
        """
        logger.info(f"正在从Semantic Scholar获取论文ID:{paper_id}的参考文献...")
        references_data: Dict[str, Any] = {
            "source_paper_id": paper_id,
            "reference_dois": [],
            "full_references_details": []
        }
        
        if not paper_id:
            logger.warning("未提供Paper ID，无法获取参考文献。")
            return references_data

        try:
            # 获取参考文献详情
            full_details = await self.s2_client.batch_get_references_by_papers(
                paper_id=paper_id, 
                limit=config.S2_REFERENCES_LIMIT
            )
            
            logger.info(f"从S2获取到 {len(full_details)} 条参考文献的完整详情")
            
            # 检查数据的完整性
            if full_details:
                # 分析第一条记录中有哪些字段
                sample = full_details[0] if full_details else {}
                logger.debug(f"参考文献数据字段完整性统计:")
                logger.debug(f"- DOI字段: {sum(1 for ref in full_details if ref.get('doi'))}/{len(full_details)}")
                logger.debug(f"- 标题字段: {sum(1 for ref in full_details if ref.get('title'))}/{len(full_details)}")
                logger.debug(f"- 作者字段: {sum(1 for ref in full_details if ref.get('authors_str'))}/{len(full_details)}")
                logger.debug(f"- 期刊字段: {sum(1 for ref in full_details if ref.get('journal'))}/{len(full_details)}")
                logger.debug(f"- 发表日期字段: {sum(1 for ref in full_details if ref.get('pub_date'))}/{len(full_details)}")
                logger.debug(f"- 摘要字段: {sum(1 for ref in full_details if ref.get('abstract'))}/{len(full_details)}")
            
            # 确保所有必需的字段都存在
            enriched_details = []
            for ref in full_details:
                # authors_str 优先用 authors 列表拼接
                authors_list = ref.get("authors", [])
                # 兼容 S2 返回 authors 为对象列表（如 [{'name': 'xxx'}, ...]）
                if isinstance(authors_list, list) and authors_list:
                    # 如果元素是字典（如 {'name': ...}），拼接 name 字段
                    if all(isinstance(a, dict) and "name" in a for a in authors_list):
                        authors_str = "; ".join(a["name"] for a in authors_list if "name" in a)
                    else:
                        authors_str = "; ".join(str(a) for a in authors_list)
                else:
                    authors_str = ref.get("authors_str", "")

                # pub_date 优先用 pub_date，其次 publication_date，其次 year
                pub_date = (
                    ref.get("pub_date")
                    or ref.get("publication_date")
                    or (str(ref.get("year")) if ref.get("year") else "")
                    or ""
                )

                ref_enriched = {
                    "doi": ref.get("doi", ""),
                    "title": ref.get("title", ""),
                    "authors_str": authors_str,
                    "pub_date": pub_date,
                    "journal": ref.get("journal", ""),
                    "abstract": ref.get("abstract", ""),
                    "pmid": ref.get("pmid", ""),
                    "pmid_link": ref.get("pmid_link", ""),
                    "pmcid": ref.get("pmcid", ""),
                    "pmcid_link": ref.get("pmcid_link", ""),
                    "citation_count": ref.get("citation_count", 0),
                    "s2_paper_id": ref.get("s2_paper_id", "")
                }

                # authors 字段保留原始结构
                ref_enriched["authors"] = authors_list if authors_list else []

                enriched_details.append(ref_enriched)
            
            references_data["full_references_details"] = enriched_details
            
            # 验证参考文献DOI数据质量
            valid_dois = []
            unique_dois = set()
            for ref in enriched_details:
                doi = ref.get("doi", "")
                if doi:
                    # 检查DOI重复情况
                    if doi in unique_dois:
                        logger.warning(f"发现重复的DOI: {doi}")
                    else:
                        unique_dois.add(doi)
                        valid_dois.append(doi)
            
            # 检查所有DOI是否相同
            if len(valid_dois) > 1 and len(set(valid_dois)) == 1:
                logger.error(f"所有参考文献使用相同的DOI: {valid_dois[0]}，这可能是数据错误，清除这些DOI")
                # 清除错误的相同DOI
                for ref in enriched_details:
                    ref["doi"] = ""
                valid_dois = []
            
            references_data["reference_dois"] = valid_dois
            
            # 正确地从完整详情中提取DOI
            valid_dois = [ref.get("doi") for ref in enriched_details if ref.get("doi")]
            references_data["reference_dois"] = valid_dois
            
            # 更新日志以显示实际有效的DOI数量
            doi_count = len(valid_dois)
            details_count = len(enriched_details)
            logger.info(f"获取了 {doi_count} 条参考文献的DOI，以及 {details_count} 条参考文献的详细信息。")
            
            # 如果DOI全部缺失但有详情，尝试直接请求DOI列表
            if doi_count == 0 and details_count > 0:
                logger.warning("参考文献详情中没有DOI，尝试直接获取DOI列表...")
                direct_dois = await self.s2_client.get_references_by_paper_id(paper_id, limit=config.S2_REFERENCES_LIMIT)
                if direct_dois:
                    # 尝试将直接获取的DOI与详情匹配
                    for i, ref in enumerate(enriched_details):
                        if i < len(direct_dois):
                            ref["doi"] = direct_dois[i]
                    
                    # 更新引用数据
                    references_data["full_references_details"] = enriched_details
                    references_data["reference_dois"] = direct_dois
                    
                    logger.info(f"直接获取DOI后: 获取了 {len(direct_dois)} 条参考文献的DOI")

            # 新增: 从Semantic Scholar获取的数据中提取PMID，并使用PubMed API获取更多信息
            # 收集所有已有的PMID
            pmids = [ref.get("pmid") for ref in enriched_details if ref.get("pmid")]
            if pmids:
                logger.info(f"发现 {len(pmids)} 个参考文献已有PMID，从PubMed获取详细信息...")
                pubmed_details = await self.pubmed_client.get_articles_by_pmids(pmids, email or "")
                  # 创建PMID到PubMed详情的映射
                pmid_to_pubmed = {detail.get("pmid"): detail for detail in pubmed_details if detail.get("pmid")}
                  # 更新参考文献的PubMed信息
                updated_count = 0
                field_update_stats = {
                    "authors_str": 0,
                    "authors": 0,
                    "pub_date": 0,
                    "title": 0,
                    "journal": 0,
                    "abstract": 0
                }
                
                for ref in enriched_details:
                    pmid = ref.get("pmid", "")
                    if pmid and pmid in pmid_to_pubmed:
                        pubmed_info = pmid_to_pubmed[pmid]
                        initial_empty_fields = []
                        
                        # 记录初始为空的字段
                        if not ref.get("authors_str"):
                            initial_empty_fields.append("authors_str")
                        if not ref.get("authors"):
                            initial_empty_fields.append("authors")
                        if not ref.get("pub_date"):
                            initial_empty_fields.append("pub_date")
                        if not ref.get("title"):
                            initial_empty_fields.append("title")
                        if not ref.get("journal"):
                            initial_empty_fields.append("journal")
                        if not ref.get("abstract"):
                            initial_empty_fields.append("abstract")
                        
                        # 更新PubMed相关字段
                        ref["pmid_link"] = pubmed_info.get("pmid_link", ref.get("pmid_link", ""))
                        ref["pmcid"] = pubmed_info.get("pmcid", ref.get("pmcid", ""))
                        ref["pmcid_link"] = pubmed_info.get("pmcid_link", ref.get("pmcid_link", ""))
                        
                        # 更新作者信息 - 优先使用PubMed数据（更准确）
                        if pubmed_info.get("authors_str"):
                            ref["authors_str"] = pubmed_info.get("authors_str", "")
                            field_update_stats["authors_str"] += 1
                        # 更新authors列表
                        if pubmed_info.get("authors"):
                            ref["authors"] = pubmed_info.get("authors", [])
                            field_update_stats["authors"] += 1
                        
                        # 更新发表日期 - 优先使用PubMed数据（更准确）
                        if pubmed_info.get("pub_date"):
                            ref["pub_date"] = pubmed_info.get("pub_date", "")
                            field_update_stats["pub_date"] += 1
                        
                        # 更新标题（如果原标题为空）
                        if pubmed_info.get("title") and not ref.get("title"):
                            ref["title"] = pubmed_info.get("title", "")
                            field_update_stats["title"] += 1
                        
                        # 更新期刊信息（如果原期刊为空）
                        if pubmed_info.get("journal") and not ref.get("journal"):
                            ref["journal"] = pubmed_info.get("journal", "")
                            field_update_stats["journal"] += 1
                        
                        # 如果参考文献的摘要为空，且PubMed有摘要，则使用PubMed的摘要
                        if not ref.get("abstract") and pubmed_info.get("abstract"):
                            ref["abstract"] = pubmed_info.get("abstract", "")
                            field_update_stats["abstract"] += 1
                        
                        # 记录这条参考文献的字段更新情况
                        updated_fields = []
                        if "authors_str" in initial_empty_fields and ref.get("authors_str"):
                            updated_fields.append("authors_str")
                        if "pub_date" in initial_empty_fields and ref.get("pub_date"):
                            updated_fields.append("pub_date")
                        if "title" in initial_empty_fields and ref.get("title"):
                            updated_fields.append("title")
                        if "journal" in initial_empty_fields and ref.get("journal"):
                            updated_fields.append("journal")
                        if "abstract" in initial_empty_fields and ref.get("abstract"):
                            updated_fields.append("abstract")
                        
                        if updated_fields:
                            logger.debug(f"PMID {pmid} 的字段已从PubMed更新: {', '.join(updated_fields)}")
                        
                        updated_count += 1
                
                logger.info(f"成功更新了 {updated_count} 条参考文献的PubMed信息")
                logger.info(f"字段更新统计: authors_str: {field_update_stats['authors_str']}, pub_date: {field_update_stats['pub_date']}, title: {field_update_stats['title']}, journal: {field_update_stats['journal']}, abstract: {field_update_stats['abstract']}")
                
                # 更新references_data
                references_data["full_references_details"] = enriched_details

        except Exception as e:
            logger.exception(f"获取论文 {paper_id} 的参考文献时发生错误: {e}")
            # 确保即使出错也保持结构一致
            references_data["error"] = str(e)

        return references_data
