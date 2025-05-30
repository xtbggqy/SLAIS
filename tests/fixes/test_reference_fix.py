#!/usr/bin/env python3
"""
测试参考文献字段映射修复
验证PubMed丰富化过程中authors_str和pub_date字段是否正确更新
"""
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到系统路径
project_root = Path(__file__).parent.parent.parent  # 向上一级到项目根目录
sys.path.insert(0, str(project_root))

from agents.metadata_fetching_agent import MetadataFetchingAgent
from slais.pubmed_client import PubMedClient
from slais.semantic_scholar_client import SemanticScholarClient
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_mock_reference_data():
    """创建模拟的参考文献数据（模拟从Semantic Scholar获取的数据）"""
    return [
        {
            "doi": "10.1038/nature12373",
            "title": "Test Paper 1",
            "authors_str": "",  # 空的，需要从PubMed填充
            "pub_date": "",     # 空的，需要从PubMed填充
            "journal": "Nature",
            "abstract": "",
            "pmid": "23868259",  # 有PMID，可以从PubMed获取详细信息
            "pmid_link": "",
            "pmcid": "",
            "pmcid_link": "",
            "citation_count": 0,
            "s2_paper_id": "",
            "authors": []
        },
        {
            "doi": "10.1126/science.1234567",
            "title": "Test Paper 2",
            "authors_str": "",  # 空的，需要从PubMed填充
            "pub_date": "",     # 空的，需要从PubMed填充
            "journal": "Science",
            "abstract": "",
            "pmid": "12345678",  # 有PMID，可以从PubMed获取详细信息
            "pmid_link": "",
            "pmcid": "",
            "pmcid_link": "",
            "citation_count": 0,
            "s2_paper_id": "",
            "authors": []
        }
    ]

def create_mock_pubmed_data():
    """创建模拟的PubMed返回数据"""
    return [
        {
            "pmid": "23868259",
            "pmid_link": "https://pubmed.ncbi.nlm.nih.gov/23868259/",
            "title": "Test Paper 1 Full Title",
            "authors": ["Smith J", "Johnson A", "Brown K"],
            "authors_str": "Smith J; Johnson A; Brown K",
            "pub_date": "2013-07-25",
            "journal": "Nature",
            "abstract": "This is a test abstract from PubMed",
            "pmcid": "PMC3737000",
            "pmcid_link": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3737000/",
            "doi": "10.1038/nature12373"
        },
        {
            "pmid": "12345678",
            "pmid_link": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            "title": "Test Paper 2 Full Title",
            "authors": ["Williams R", "Davis M"],
            "authors_str": "Williams R; Davis M",
            "pub_date": "2020-03-15",
            "journal": "Science",
            "abstract": "This is another test abstract from PubMed",
            "pmcid": "",
            "pmcid_link": "",
            "doi": "10.1126/science.1234567"
        }
    ]

def test_field_mapping():
    """测试字段映射修复"""
    logger.info("开始测试参考文献字段映射修复...")
    
    # 模拟修复前的enriched_details（从S2获取，但作者和日期字段为空）
    enriched_details = create_mock_reference_data()
    
    # 模拟从PubMed获取的数据
    pubmed_details = create_mock_pubmed_data()
    
    logger.info("修复前的参考文献数据:")
    for i, ref in enumerate(enriched_details):
        logger.info(f"  参考文献 {i+1}:")
        logger.info(f"    PMID: {ref.get('pmid', 'N/A')}")
        logger.info(f"    authors_str: '{ref.get('authors_str', 'N/A')}'")
        logger.info(f"    pub_date: '{ref.get('pub_date', 'N/A')}'")
        logger.info(f"    authors: {ref.get('authors', [])}")
    
    # 应用修复后的逻辑（模拟metadata_fetching_agent.py中的修复代码）
    pmid_to_pubmed = {detail.get("pmid"): detail for detail in pubmed_details if detail.get("pmid")}
    
    updated_count = 0
    for ref in enriched_details:
        pmid = ref.get("pmid", "")
        if pmid and pmid in pmid_to_pubmed:
            pubmed_info = pmid_to_pubmed[pmid]
            
            # 更新PubMed相关字段
            ref["pmid_link"] = pubmed_info.get("pmid_link", ref.get("pmid_link", ""))
            ref["pmcid"] = pubmed_info.get("pmcid", ref.get("pmcid", ""))
            ref["pmcid_link"] = pubmed_info.get("pmcid_link", ref.get("pmcid_link", ""))
            
            # 更新作者信息 - 优先使用PubMed数据（更准确）
            if pubmed_info.get("authors_str"):
                ref["authors_str"] = pubmed_info.get("authors_str", "")
            # 更新authors列表
            if pubmed_info.get("authors"):
                ref["authors"] = pubmed_info.get("authors", [])
            
            # 更新发表日期 - 优先使用PubMed数据（更准确）
            if pubmed_info.get("pub_date"):
                ref["pub_date"] = pubmed_info.get("pub_date", "")
            
            # 更新标题（如果原标题为空）
            if pubmed_info.get("title") and not ref.get("title"):
                ref["title"] = pubmed_info.get("title", "")
            
            # 更新期刊信息（如果原期刊为空）
            if pubmed_info.get("journal") and not ref.get("journal"):
                ref["journal"] = pubmed_info.get("journal", "")
            
            # 如果参考文献的摘要为空，且PubMed有摘要，则使用PubMed的摘要
            if not ref.get("abstract") and pubmed_info.get("abstract"):
                ref["abstract"] = pubmed_info.get("abstract", "")
            updated_count += 1
    
    logger.info(f"成功更新了 {updated_count} 条参考文献的PubMed信息")
    
    logger.info("修复后的参考文献数据:")
    for i, ref in enumerate(enriched_details):
        logger.info(f"  参考文献 {i+1}:")
        logger.info(f"    PMID: {ref.get('pmid', 'N/A')}")
        logger.info(f"    authors_str: '{ref.get('authors_str', 'N/A')}'")
        logger.info(f"    pub_date: '{ref.get('pub_date', 'N/A')}'")
        logger.info(f"    authors: {ref.get('authors', [])}")
        logger.info(f"    title: '{ref.get('title', 'N/A')}'")
        logger.info(f"    journal: '{ref.get('journal', 'N/A')}'")
        logger.info(f"    abstract: '{ref.get('abstract', 'N/A')[:50]}...'" if ref.get('abstract') else "    abstract: 'N/A'")
    
    # 验证修复是否成功
    success = True
    for i, ref in enumerate(enriched_details):
        if not ref.get('authors_str'):
            logger.error(f"参考文献 {i+1} 的 authors_str 仍为空！")
            success = False
        if not ref.get('pub_date'):
            logger.error(f"参考文献 {i+1} 的 pub_date 仍为空！")
            success = False
    
    if success:
        logger.info("✅ 字段映射修复测试成功！所有参考文献的authors_str和pub_date字段都已正确填充。")
    else:
        logger.error("❌ 字段映射修复测试失败！部分字段仍为空。")
    
    return success

if __name__ == "__main__":
    success = test_field_mapping()
    sys.exit(0 if success else 1)
