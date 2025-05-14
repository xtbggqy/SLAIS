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
            # SemanticScholarClient.batch_get_references_by_papers already fetches S2 details,
            # then tries to get PMID/PMCID and formats them including links.
            # It returns a list of formatted reference dictionaries.
            full_details = await self.s2_client.batch_get_references_by_papers(
                paper_id=paper_id, 
                limit=config.S2_REFERENCES_LIMIT
            )
            
            references_data["full_references_details"] = full_details
            references_data["reference_dois"] = [ref.get("doi") for ref in full_details if ref.get("doi")]
            
            logger.info(f"获取了 {len(references_data['reference_dois'])} 条参考文献的DOI，以及 {len(full_details)} 条参考文献的详细信息。")

        except Exception as e:
            logger.exception(f"获取论文 {paper_id} 的参考文献时发生错误: {e}")
            # Fallback or ensure structure is maintained even on error
            references_data["error"] = str(e)

        return references_data
