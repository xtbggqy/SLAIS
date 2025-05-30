import sqlite3
import json
import os
from pathlib import Path
from slais import config
from slais.utils.logging_utils import logger

class DatabaseManager:
    def __init__(self):
        self.db_path = Path(config.settings.CACHE_DIR) / "literature_cache.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self.create_tables()
        logger.info(f"DatabaseManager initialized. Database path: {self.db_path}")

    def connect(self):
        """连接到SQLite数据库"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            logger.debug("Connected to SQLite database")
        return self.conn

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Closed SQLite database connection")

    def create_tables(self):
        """创建必要的表"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # 创建metadata表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                doi TEXT PRIMARY KEY,
                title TEXT,
                authors_str TEXT,
                pub_date TEXT,
                journal TEXT,
                abstract TEXT,
                pmid TEXT,
                pmid_link TEXT,
                pmcid TEXT,
                pmcid_link TEXT,
                citation_count INTEGER,
                s2_paper_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建literature_data表，整合相关文献和参考文献信息
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS literature_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doi TEXT,
                title TEXT,
                authors_str TEXT,
                pub_date TEXT,
                journal TEXT,
                abstract TEXT,
                pmid TEXT,
                pmid_link TEXT,
                pmcid TEXT,
                pmcid_link TEXT,
                citation_count INTEGER,
                s2_paper_id TEXT,
                data_type TEXT,
                source_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(doi, data_type, source_id)
            )
        ''')

        conn.commit()
        logger.info("Database tables created or verified")

    def get_metadata(self, doi: str) -> dict:
        """从数据库获取元数据"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM metadata WHERE doi = ?", (doi,))
        result = cursor.fetchone()
        if result:
            logger.info(f"从数据库中获取DOI {doi} 的元数据")
            columns = ['doi', 'title', 'authors_str', 'pub_date', 'journal', 'abstract', 'pmid', 'pmid_link', 'pmcid', 'pmcid_link', 'citation_count', 's2_paper_id', 'timestamp']
            return dict(zip(columns, result))
        logger.debug(f"数据库中未找到DOI {doi} 的元数据")
        return None

    def set_metadata(self, doi: str, data: dict):
        """将元数据存储到数据库"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO metadata 
            (doi, title, authors_str, pub_date, journal, abstract, pmid, pmid_link, pmcid, pmcid_link, citation_count, s2_paper_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doi,
            data.get('title', ''),
            data.get('authors_str', ''),
            data.get('pub_date', ''),
            data.get('journal', ''),
            data.get('abstract', ''),
            data.get('pmid', ''),
            data.get('pmid_link', ''),
            data.get('pmcid', ''),
            data.get('pmcid_link', ''),
            data.get('citation_count', 0),
            data.get('s2_paper_id', '')
        ))
        conn.commit()
        logger.info(f"已将DOI {doi} 的元数据存储到数据库中")

    def get_related_articles(self, pmid: str) -> list:
        """从数据库获取相关文章"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM literature_data WHERE source_id = ? AND data_type = 'related_article'", (pmid,))
        results = cursor.fetchall()
        if results:
            logger.info(f"从数据库中获取PMID {pmid} 的相关文章")
            columns = ['id', 'doi', 'title', 'authors_str', 'pub_date', 'journal', 'abstract', 'pmid', 'pmid_link', 'pmcid', 'pmcid_link', 'citation_count', 's2_paper_id', 'data_type', 'source_id', 'timestamp']
            return [dict(zip(columns, result)) for result in results]
        logger.debug(f"数据库中未找到PMID {pmid} 的相关文章")
        return []

    def set_related_articles(self, pmid: str, data: list):
        """将相关文章存储到数据库"""
        conn = self.connect()
        cursor = conn.cursor()
        if data and isinstance(data, list):
            for article in data:
                cursor.execute("""
                    INSERT OR REPLACE INTO literature_data 
                    (doi, title, authors_str, pub_date, journal, abstract, pmid, pmid_link, pmcid, pmcid_link, citation_count, s2_paper_id, data_type, source_id) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    article.get('doi', ''),
                    article.get('title', ''),
                    article.get('authors_str', ''),
                    article.get('pub_date', ''),
                    article.get('journal', ''),
                    article.get('abstract', ''),
                    article.get('pmid', ''),
                    article.get('pmid_link', ''),
                    article.get('pmcid', ''),
                    article.get('pmcid_link', ''),
                    article.get('citation_count', 0),
                    article.get('s2_paper_id', ''),
                    'related_article',
                    pmid
                ))
        conn.commit()
        logger.info(f"已将PMID {pmid} 的相关文章存储到数据库中")

    def get_references(self, paper_id: str) -> dict:
        """从数据库获取参考文献"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM literature_data WHERE source_id = ? AND data_type = 'reference'", (paper_id,))
        results = cursor.fetchall()
        if results:
            logger.info(f"从数据库中获取Paper ID {paper_id} 的参考文献")
            columns = ['id', 'doi', 'title', 'authors_str', 'pub_date', 'journal', 'abstract', 'pmid', 'pmid_link', 'pmcid', 'pmcid_link', 'citation_count', 's2_paper_id', 'data_type', 'source_id', 'timestamp']
            references = [dict(zip(columns, result)) for result in results]
            return {'full_references_details': references}
        logger.debug(f"数据库中未找到Paper ID {paper_id} 的参考文献")
        return {'full_references_details': []}

    def set_references(self, paper_id: str, data: dict):
        """将参考文献存储到数据库"""
        conn = self.connect()
        cursor = conn.cursor()
        references = data.get('full_references_details', [])
        if references and isinstance(references, list):
            for ref in references:
                cursor.execute("""
                    INSERT OR REPLACE INTO literature_data 
                    (doi, title, authors_str, pub_date, journal, abstract, pmid, pmid_link, pmcid, pmcid_link, citation_count, s2_paper_id, data_type, source_id) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ref.get('doi', ''),
                    ref.get('title', ''),
                    ref.get('authors_str', ''),
                    ref.get('pub_date', ''),
                    ref.get('journal', ''),
                    ref.get('abstract', ''),
                    ref.get('pmid', ''),
                    ref.get('pmid_link', ''),
                    ref.get('pmcid', ''),
                    ref.get('pmcid_link', ''),
                    ref.get('citation_count', 0),
                    ref.get('s2_paper_id', ''),
                    'reference',
                    paper_id
                ))
        conn.commit()
        logger.info(f"已将Paper ID {paper_id} 的参考文献存储到数据库中")
