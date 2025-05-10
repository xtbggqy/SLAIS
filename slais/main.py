import asyncio
import os
import argparse
import sys

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import csv # 导入 csv 模块
import json # 导入 json 模块，用于处理参考文献列表
# 现在导入项目模块
from slais.pdf_utils import convert_pdf_to_markdown
from slais.pubmed_client import PubMedClient, ArticleDetails # 从新的 pubmed_client 模块导入
from slais.semantic_scholar_client import SemanticScholarClient # 从新的 semantic_scholar_client 模块导入
from slais import config
from slais.utils.logging_utils import setup_logging # 导入日志设置函数

# 导入配置
try:
    from slais.config import DEFAULT_PDF_PATH, OUTPUT_BASE_DIR, ARTICLE_DOI, NCBI_EMAIL # 导入 NCBI_EMAIL
except ImportError:
    # 如果config.py不存在，使用默认值
    DEFAULT_PDF_PATH = "pdfs/example.pdf"
    OUTPUT_BASE_DIR = "output"
    ARTICLE_DOI = None
    NCBI_EMAIL = None # 默认邮箱为 None
    print("警告: 无法导入配置文件，使用默认配置")

async def main(pdf_path=None):
    # 使用默认PDF路径或命令行参数提供的路径
    if pdf_path is None:
        pdf_path = DEFAULT_PDF_PATH
    
    print(f"正在处理PDF文件: {pdf_path}")
    
    # Step 1: 从配置中获取DOI和邮箱
    doi = ARTICLE_DOI
    email = NCBI_EMAIL # 从配置中获取邮箱

    if doi is None:
        print("未在配置中找到DOI (ARTICLE_DOI 环境变量未设置)。")
        pdf_filename_no_ext = os.path.splitext(os.path.basename(pdf_path))[0]
        print(f"将使用PDF文件名 '{pdf_filename_no_ext}' 作为部分输出标识符，但PubMed查询将失败。")
    
    if not email:
        print("警告: 未在配置中找到 NCBI 邮箱 (NCBI_EMAIL 环境变量未设置)。PubMed 查询可能受限或失败。")

    # --- 初始化数据存储 ---
    original_s2_info: Optional[Dict[str, Any]] = None # S2对原始文章的信息
    original_pubmed_info: Optional[ArticleDetails] = None # PubMed对原始文章的信息 (可能通过S2的PMID获取)
    
    pubmed_related_articles: List[ArticleDetails] = [] # PubMed计算的相关文献
    
    s2_reference_dois: List[str] = [] # S2返回的参考文献DOI列表
    s2_references_s2_details: Dict[str, Optional[Dict[str, Any]]] = {} # S2对参考文献的详细信息 {doi: s2_info}
    s2_references_pubmed_details: List[ArticleDetails] = [] # PubMed对S2参考文献的补充信息

    # --- API客户端实例化 ---
    pubmed_client = PubMedClient()
    s2_client = SemanticScholarClient()

    if doi and email:
        print(f"从配置中获取的DOI: {doi}")
        print(f"从配置中获取的邮箱: {email}")

        # --- Step 2: 获取原始文章信息 ---
        # 2a. 从 Semantic Scholar 获取
        print(f"\n正在从 Semantic Scholar 获取原始文章 (DOI: {doi}) 的信息...")
        original_s2_info = await s2_client.get_paper_details_by_doi(doi)
        
        if original_s2_info and original_s2_info.get('paperId'):
            print(f"  成功从S2获取原始文章信息 (S2 PaperID: {original_s2_info['paperId']})")
            s2_paper_id_original = original_s2_info['paperId']
            
            # 2b. (可选) 从 PubMed 补充/核实原始文章信息 (如果S2提供了PMID)
            s2_external_ids = original_s2_info.get('externalIds', {})
            pmid_from_s2 = s2_external_ids.get('PubMed') if isinstance(s2_external_ids, dict) else None
            
            if pmid_from_s2:
                print(f"  S2提供了PMID: {pmid_from_s2}。正在从PubMed获取/核实...")
                original_pubmed_info = await pubmed_client.get_article_details_by_pmid(pmid_from_s2, email)
                if original_pubmed_info:
                    print(f"    成功从PubMed获取PMID {pmid_from_s2} 的信息。")
                else:
                    print(f"    未能从PubMed获取PMID {pmid_from_s2} 的信息，将主要依赖S2数据。")
            else: # S2未提供PMID，尝试用DOI从PubMed获取
                print(f"  S2未提供PMID。尝试用DOI从PubMed获取原始文章信息...")
                original_pubmed_info = await pubmed_client.get_article_details(doi, email)
                if original_pubmed_info:
                     print(f"    成功从PubMed获取DOI {doi} 的信息 (PMID: {original_pubmed_info.get('pmid')})。")
                else:
                    print(f"    也未能从PubMed通过DOI获取原始文章信息。")
        else:
            print(f"  未能从S2获取原始文章信息。尝试直接从PubMed获取...")
            original_pubmed_info = await pubmed_client.get_article_details(doi, email)
            if original_pubmed_info:
                 print(f"    成功从PubMed获取DOI {doi} 的信息 (PMID: {original_pubmed_info.get('pmid')})。")
            else:
                print(f"    也未能从PubMed通过DOI获取原始文章信息。处理可能无法继续。")

        # --- Step 3: 输出原始文章信息 (综合S2和PubMed) ---
        # (这部分可以更精细地合并数据，暂时简化)
        print("\n==== 原始文章详情 (综合S2/PubMed) ====")
        temp_title = (original_s2_info.get('title') if original_s2_info 
                      else (original_pubmed_info.get('title') if original_pubmed_info else "未提供标题"))
        print(f"标题: {temp_title}")
        # ... 可以添加更多字段的打印 ...
        if original_s2_info: print(f"S2 PaperID: {original_s2_info.get('paperId')}")
        if original_pubmed_info: print(f"PubMed PMID: {original_pubmed_info.get('pmid')}")
        print("==================================\n")

        # --- Step 4: 获取PubMed计算的相关文献 ---
        # 需要原始文章的PMID，优先从 original_pubmed_info 获取，其次从 original_s2_info 的 externalIds
        pmid_for_related = None
        if original_pubmed_info and original_pubmed_info.get('pmid'):
            pmid_for_related = original_pubmed_info['pmid']
        elif original_s2_info and isinstance(original_s2_info.get('externalIds'), dict):
            pmid_for_related = original_s2_info['externalIds'].get('PubMed')

        if pmid_for_related:
            print(f"正在使用PMID {pmid_for_related} 从PubMed获取相关文章...")
            pubmed_related_articles = await pubmed_client.get_related_articles(pmid_for_related, email)
            print(f"通过PubMed找到 {len(pubmed_related_articles)} 篇相关文章。")
            # (输出PubMed相关文章列表的逻辑可以保留或调整)
        else:
            print("无PMID用于查询PubMed相关文章。")
        print("==================================\n")

        # --- Step 5: 获取S2参考文献及其PubMed详情 ---
        s2_paper_id_original_for_refs = original_s2_info.get('paperId') if original_s2_info else None
        if s2_paper_id_original_for_refs:
            print(f"正在从 Semantic Scholar (PaperID: {s2_paper_id_original_for_refs}) 获取参考文献DOI列表...")
            s2_reference_dois = await s2_client.get_references_by_paper_id(s2_paper_id_original_for_refs)

            if s2_reference_dois:
                print(f"  S2返回 {len(s2_reference_dois)} 条参考文献DOI。")
                print(f"  正在从 Semantic Scholar 批量获取这些参考文献的详细信息...")
                s2_references_s2_details = await s2_client.batch_get_paper_details_by_dois(s2_reference_dois)
                valid_s2_ref_details_count = sum(1 for detail in s2_references_s2_details.values() if detail)
                print(f"    成功从S2获取了 {valid_s2_ref_details_count} 篇参考文献的详细信息。")

                # 从S2获取的参考文献详情中提取PMID，然后批量从PubMed补充
                pmids_from_s2_refs: List[str] = []
                for ref_doi, s2_detail in s2_references_s2_details.items():
                    if s2_detail and isinstance(s2_detail.get('externalIds'), dict):
                        pmid = s2_detail['externalIds'].get('PubMed')
                        if pmid:
                            pmids_from_s2_refs.append(pmid)
                
                if pmids_from_s2_refs:
                    unique_pmids_from_s2_refs = sorted(list(set(pmids_from_s2_refs))) # 去重并排序
                    print(f"  从S2参考文献中提取到 {len(unique_pmids_from_s2_refs)} 个唯一PMID。正在从PubMed批量获取/核实信息...")
                    s2_references_pubmed_details = await pubmed_client.batch_get_article_details_by_pmids(unique_pmids_from_s2_refs, email)
                    print(f"    成功从PubMed获取/核实了 {len(s2_references_pubmed_details)} 篇S2参考文献的PMID信息。")
                else:
                    print("  S2返回的参考文献中未能提取到PMID用于PubMed核实。")
            else:
                print("  未能从Semantic Scholar获取参考文献DOI列表。")
        else:
            print("无S2 PaperID用于查询参考文献。")
        print("==================================\n")
        
        # --- Step 6: CSV输出 ---
        # (确保 original_article_details, pubmed_related_articles, s2_references_s2_details, s2_references_pubmed_details 已填充)
        # CSV文件名基于DOI或PMID
        csv_file_name_base = "unknown_article"
        if original_pubmed_info and original_pubmed_info.get('pmid'):
            csv_file_name_base = original_pubmed_info['pmid']
        elif original_s2_info and original_s2_info.get('paperId'):
            csv_file_name_base = original_s2_info['paperId'].replace(':', '_') # S2 ID可能包含冒号
        elif doi:
            csv_file_name_base = "".join(c if c.isalnum() else "_" for c in doi)

        csv_file_name = f"{csv_file_name_base}_full_report.csv"
        csv_output_dir = os.path.join(OUTPUT_BASE_DIR, "csv_reports")
        os.makedirs(csv_output_dir, exist_ok=True)
        csv_file_path = os.path.join(csv_output_dir, csv_file_name)
        print(f"正在将所有信息保存到 CSV 文件: {csv_file_path}")

        # 定义更全面的CSV列名
        fieldnames = [
            "Type", "DataSource", "DOI", 
            "S2_PaperID", "PubMed_PMID", "PubMed_PMCID",
            "Title", "Abstract", "Authors", "Journal_Venue", "Year_PublicationDate",
            "S2_CitationCount", "S2_ReferenceCount", "S2_InfluentialCitationCount", 
            "S2_IsOpenAccess", "S2_FieldsOfStudy", "S2_PublicationTypes",
            "PubMed_Link", "PMCID_Link"
            # S2_References_DOIs (原始文章的S2参考文献DOI列表) 可以单独存储或作为原始文章行的一个字段
        ]

        with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()

            # 1. 写入原始文章信息
            row_original = {"Type": "Original", "DOI": doi} # 修正缩进
            if original_s2_info:
                # S2作者列表处理
                s2_authors_list = original_s2_info.get('authors', [])
                s2_author_names = ", ".join([a.get('name') for a in s2_authors_list if a.get('name')])
                row_original.update({
                    "DataSource": "Semantic Scholar" + (" + PubMed" if original_pubmed_info else ""),
                    "S2_PaperID": original_s2_info.get('paperId'),
                    "Title": original_s2_info.get('title'),
                    "Abstract": original_s2_info.get('abstract'),
                    "Authors": s2_author_names,
                    "Journal_Venue": original_s2_info.get('venue'),
                    "Year_PublicationDate": original_s2_info.get('year'),
                    "S2_CitationCount": original_s2_info.get('citationCount'),
                    "S2_ReferenceCount": original_s2_info.get('referenceCount'),
                    "S2_InfluentialCitationCount": original_s2_info.get('influentialCitationCount'),
                    "S2_IsOpenAccess": str(original_s2_info.get('isOpenAccess', '')),
                    "S2_FieldsOfStudy": json.dumps(original_s2_info.get('fieldsOfStudy')) if original_s2_info.get('fieldsOfStudy') else '',
                    "S2_PublicationTypes": json.dumps(original_s2_info.get('publicationTypes')) if original_s2_info.get('publicationTypes') else '',
                    "PubMed_PMID": original_s2_info.get('externalIds', {}).get('PubMed'),
                    "PubMed_PMCID": original_s2_info.get('externalIds', {}).get('PMC'),
                })
            if original_pubmed_info: # 用PubMed信息补充或覆盖
                row_original["DataSource"] = "PubMed" + (" + S2" if original_s2_info else "")
                if not row_original.get("Title"): row_original["Title"] = original_pubmed_info.get('title') # 优先S2，若无则用PubMed
                row_original["Abstract"] = original_pubmed_info.get('abstract') or row_original.get("Abstract") # 优先PubMed摘要
                # PubMed作者列表处理 (覆盖或补充S2的)
                pubmed_authors_list = original_pubmed_info.get('authors')
                row_original["Authors"] = ", ".join(pubmed_authors_list if pubmed_authors_list else []) or row_original.get("Authors")
                row_original["Journal_Venue"] = original_pubmed_info.get('journal') or row_original.get("Journal_Venue")
                row_original["Year_PublicationDate"] = original_pubmed_info.get('publication_date') or row_original.get("Year_PublicationDate")
                row_original["PubMed_PMID"] = original_pubmed_info.get('pmid') or row_original.get("PubMed_PMID")
                row_original["PubMed_PMCID"] = original_pubmed_info.get('pmcid') or row_original.get("PubMed_PMCID")
                row_original["PubMed_Link"] = original_pubmed_info.get('pmid_link')
                row_original["PMCID_Link"] = original_pubmed_info.get('pmcid_link')
            writer.writerow(row_original)

            # 2. 写入PubMed相关文献
            for article in pubmed_related_articles:
                writer.writerow({
                    "Type": "Related", "DataSource": "PubMed",
                    "DOI": None, # PubMed相关文献不直接提供DOI，但可以通过PMID反查
                    "PubMed_PMID": article.get('pmid'), "PubMed_PMCID": article.get('pmcid'),
                    "Title": article.get('title'), "Abstract": article.get('abstract'),
                    "Authors": ", ".join(article.get('authors') or []), 
                    "Journal_Venue": article.get('journal'),
                    "Year_PublicationDate": article.get('publication_date'),
                    "PubMed_Link": article.get('pmid_link'), "PMCID_Link": article.get('pmcid_link')
                })

            # 3. 写入S2参考文献 (结合S2详情和PubMed补充详情)
            # 创建一个字典，以PMID为键，存储PubMed补充的参考文献详情
            pubmed_ref_details_map = {ref.get('pmid'): ref for ref in s2_references_pubmed_details if ref.get('pmid')}

            for ref_doi, s2_ref_detail in s2_references_s2_details.items():
                if not s2_ref_detail: continue # 跳过未能从S2获取详情的
                
                row_ref = {"Type": "Reference", "DOI": ref_doi, "DataSource": "Semantic Scholar"}
                row_ref.update({
                    "S2_PaperID": s2_ref_detail.get('paperId'),
                    "Title": s2_ref_detail.get('title'),
                    "Abstract": s2_ref_detail.get('abstract'),
                    # S2参考文献的作者列表处理
                    "Authors": ", ".join([a.get('name') for a in s2_ref_detail.get('authors', []) if a.get('name')]),
                    "Journal_Venue": s2_ref_detail.get('venue'),
                    "Year_PublicationDate": s2_ref_detail.get('year'),
                    "S2_CitationCount": s2_ref_detail.get('citationCount'),
                    "S2_ReferenceCount": s2_ref_detail.get('referenceCount'),
                    "S2_InfluentialCitationCount": s2_ref_detail.get('influentialCitationCount'),
                    "S2_IsOpenAccess": str(s2_ref_detail.get('isOpenAccess', '')),
                    "S2_FieldsOfStudy": json.dumps(s2_ref_detail.get('fieldsOfStudy')) if s2_ref_detail.get('fieldsOfStudy') else '',
                    "S2_PublicationTypes": json.dumps(s2_ref_detail.get('publicationTypes')) if s2_ref_detail.get('publicationTypes') else '',
                })
                
                s2_ref_pmid = s2_ref_detail.get('externalIds', {}).get('PubMed')
                row_ref["PubMed_PMID"] = s2_ref_pmid
                row_ref["PubMed_PMCID"] = s2_ref_detail.get('externalIds', {}).get('PMC')

                # 如果有来自PubMed的补充信息
                if s2_ref_pmid and s2_ref_pmid in pubmed_ref_details_map:
                    pubmed_supplement = pubmed_ref_details_map[s2_ref_pmid]
                    row_ref["DataSource"] += " + PubMed (verified)"
                    # 可以选择性地用PubMed信息覆盖或补充S2信息
                    row_ref["Abstract"] = pubmed_supplement.get('abstract') or row_ref["Abstract"] # 优先PubMed摘要
                    # PubMed补充的作者列表处理
                    pubmed_ref_authors_list = pubmed_supplement.get('authors')
                    row_ref["Authors"] = ", ".join(pubmed_ref_authors_list if pubmed_ref_authors_list else []) or row_ref["Authors"]
                    row_ref["Journal_Venue"] = pubmed_supplement.get('journal') or row_ref["Journal_Venue"]
                    row_ref["Year_PublicationDate"] = pubmed_supplement.get('publication_date') or row_ref["Year_PublicationDate"]
                    row_ref["PubMed_Link"] = pubmed_supplement.get('pmid_link')
                    row_ref["PMCID_Link"] = pubmed_supplement.get('pmcid_link')
                writer.writerow(row_ref)
            print(f"所有信息已成功保存到: {csv_file_path}\n")

    elif doi and not email:
         print("由于未配置 NCBI 邮箱，跳过 PubMed 文章详情和相关文章获取。")
    else: # not doi
        print("由于未配置DOI，跳过PubMed文章详情和相关文章获取。")


    # Step 8: 将PDF转换为Markdown (保持原有功能)
    pdf_basename_no_ext = os.path.splitext(os.path.basename(pdf_path))[0]
    output_dir_for_pdf = os.path.join(OUTPUT_BASE_DIR, pdf_basename_no_ext)
    
    md_path = convert_pdf_to_markdown(pdf_path, output_dir_for_pdf)
    if md_path:
        print(f"PDF已转换为Markdown，保存在: {md_path}")

if __name__ == "__main__":
    # 命令行参数解析
    parser = argparse.ArgumentParser(description="PDF文献智能分析与洞察系统")
    parser.add_argument("-p", "--pdf", help="PDF文件路径", default=None)
    args = parser.parse_args()

    # 在参数解析后，实际运行主逻辑前设置日志
    setup_logging() 
    
    # 运行主函数
    asyncio.run(main(args.pdf))
