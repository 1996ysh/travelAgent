"""
重排序器：使用 LLM 进行重排
"""
from langchain_community.chat_models import ChatTongyi
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.utils.logger import app_logger


class LLMReranker:
    """LLM 重排序器（简化版）"""
    def __init__(self,model_name:str = 'qwen-plus'):
        self.llm = ChatTongyi(
            model=model_name,
            api_key=settings.dashscope_api_key
        )
        self.scorePrompt =  ChatPromptTemplate.from_template([
            ('system',
             """
             评估文档与查询的相关性,给出0-10的分数
             评估标准:
             0-3:不相关，
             3-6:部分相关,
             7-10:高度相关
             """),
            ('human',"""查询:{query},文档:{document}""")
        ])

    def  _score_document(self,query:str,document:str)->float:
        """对单个文档评分"""
        response = (self.scorePrompt | self.llm).invoke({
            'query':query,
            'document':document
        })
        try:
            return float(response.content.strip())
        except:
            return 0.0
    def  rerank(
            self,
            query:str,
            documents:list[Document],
            top_k:int = 3,
            )->list[Document]:
        """
        llm  重排序
        策略：让 LLM 为每个文档打分（0-10）
        :param query:
        :param documents:
        :param top_k:
        :return:
        """
        if len(documents) <= top_k:
            return documents
        app_logger.info(f"🔄 重排序 {len(documents)} 个文档...")

        # 简化版：直接返回前 top_k 个
        # 生产环境应调用 LLM 打分
        #一种参考
        #重排序的文档
        scored_docs = []
        for doc in documents:
            score = self._score_document(query,doc.page_content)
            scored_docs.append((doc,score))
        #排序
        scored_docs.sort(key=lambda x:x[1],reverse=True)

        return [doc for doc,_ in scored_docs[:top_k] ]
