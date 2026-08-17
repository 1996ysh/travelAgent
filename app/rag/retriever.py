"""
混合检索:BM25+Dense+RRF融合
"""
from typing import Tuple

import jieba
from langchain_chroma import Chroma
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from app.utils.logger import app_logger


class  HybridRetriever:
    """
    混合检索器
    结合:
    - BM25（关键词匹配）
    - Dense（语义相似度）
    - RRF（倒数排名融合）
    """

    def __init__(
            self,
            vectorstore:Chroma,
            documents: list[Document],
            k: int = 5
                 ):
        self.vectorstore = vectorstore
        self.documents = documents
        self.k = k

        # 初始化 BM25
        self._init_bm25()
    def _init_bm25(self):
        """初始化bm25索引"""

        app_logger.info('初始化bm25索引')

        #对所有文档进行分词 jieba是Python 最常用中文分词库
        tokenize_docs = [
            list(jieba.cut(doc.page_content))
            for doc in self.documents
        ]
        # 创建 BM25 索引
        self.bm25 = BM25Okapi(tokenize_docs)
        app_logger.info("✅ BM25 索引初始化完成")

    def  retrieve(self,query:str)->list[Document]:
        """
        混合检索
        流程: 1.BM25检索top-k 2.Dense检索 top-k  3.RRF融合 4.返回融合后的top-k
        :param query:
        :return:
        """
        ##BM25检索
        #对用户查询进行分词，与文档分词保持一致
        query_tokens = list(jieba.cut(query))
        #计算bm25得分
        bm25_scores = self.bm25.get_scores(query_tokens)
        #获取top-k索引
        bm25_top_indices = sorted(
            range(len(bm25_scores)),
            key = lambda i : bm25_scores[i],
            reverse=True
        )[:self.k * 2]  # 多取一些候选
        bm25_docs = [
            (self.documents[i], bm25_scores[i])
            for i in bm25_top_indices
        ]
        app_logger.debug(f"🔍 BM25 检索到 {len(bm25_docs)} 个候选")
        # ========== 2. Dense 检索 ==========
        dense_docs = self.vectorstore.similarity_search_with_score(
            query,
            k=self.k * 2
        )

        app_logger.debug(f"🔍 Dense 检索到 {len(dense_docs)} 个候选")
        # ========== 3. RRF 融合 ==========
        fused_docs = self._rrf_fusion(
            bm25_docs,
            dense_docs,
            k=self.k
        )

        app_logger.info(f"✅ 混合检索完成，返回 {len(fused_docs)} 个结果")

        return fused_docs
    def _rrf_fusion(
            self,
            bm25_docs: list[Tuple[Document, float]],
            dense_docs: list[Tuple[Document, float]],
            k: int = 60  # RRF 参数
    ) -> list[Document]:
        """
        倒数排名融合（Reciprocal Rank Fusion）

        公式：score(d) = Σ 1 / (k + rank(d))
        """

        scores = {}

        # BM25 排名得分
        for rank, (doc, _) in enumerate(bm25_docs, 1):
            doc_id = id(doc)
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)

        # Dense 排名得分   遍历元组需要两个变量去遍历
        for rank, (doc, _) in enumerate(dense_docs, 1):
            doc_id = id(doc)
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)

        # 按融合得分排序
        all_docs = {id(doc): doc for doc, _ in bm25_docs + dense_docs}

        sorted_docs = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [all_docs[doc_id] for doc_id, _ in sorted_docs[:self.k]]

