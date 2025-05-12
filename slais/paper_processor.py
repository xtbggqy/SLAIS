import os
import csv
import logging
from typing import List, Dict
from pubmed_client import PubmedClient

logger = logging.getLogger(__name__)

class PaperProcessor:
    def __init__(self, metadata=None):
        self.metadata = metadata
        self.pubmed_client = None

    async def get_related_articles_pubmed(self, pmid: str = None, max_results: int = None, years_back: int = None) -> List[Dict]:
        """获取PubMed相关文章"""
        if not self.pubmed_client:
            self.pubmed_client = PubmedClient()

        if pmid is None and self.metadata and self.metadata.get("pubmed_info") and self.metadata["pubmed_info"].get("pmid"):
            pmid = self.metadata["pubmed_info"]["pmid"]

        if not pmid:
            logger.warning("No PMID provided for getting related articles")
            return []
            
        # 从配置中获取最大结果数量和回溯年数
        if max_results is None:
            max_results = config.RELATED_ARTICLES_MAX
            
        if years_back is None:
            years_back = config.RELATED_ARTICLES_YEARS_BACK
            
        logger.info(f"Fetching PubMed related articles with max_results: {max_results}, years_back: {years_back}")

        related_articles = await self.pubmed_client.get_related_articles(
            pmid, 
            max_results=max_results,
            years_back=years_back
        )
        
        # 确保每条相关文章都有DOI字段，即使是空值
        for article in related_articles:
            if "doi" not in article:
                article["doi"] = ""
        
        return related_articles

    def save_related_pubmed_as_csv(self, related_articles, output_path):
        """保存PubMed相关文章为CSV"""
        if not related_articles:
            logger.warning("No related articles to save")
            return
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        fieldnames = [
            'doi', 'title', 'authors_str', 'pub_date', 'journal', 
            'abstract', 'pmid', 'pmid_link', 'pmcid', 'pmcid_link', 
            'citation_count', 's2_paper_id'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for article in related_articles:
                # 确保所有必要字段都存在
                for field in fieldnames:
                    if field not in article:
                        article[field] = ""
                writer.writerow(article)
        
        logger.info(f"Saved {len(related_articles)} related PubMed articles to {output_path}")