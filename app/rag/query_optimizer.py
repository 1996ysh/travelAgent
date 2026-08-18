"""
rag 查询优化模块
"""
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.utils.logger import app_logger

#初始化模型
model = ChatTongyi(
    model='qwen-plus',
    api_key=settings.dashscope_api_key,
    temperature = 0
)

class MultiQueryOptimizer:
    """
    Multi-Query 优化器
    生成查询的多个变体以提高召回率
    """

    def __init__(self,num_variants:int = 3):
        self.num_variants = num_variants

        #定义提示模式
        self.prompt = ChatPromptTemplate.from_template("""
        你是一个查询优化专家。给定一个用户查询，生成{num}个语义相似但表述不同的查询变体。
        原始查询：{query}
        要求：
        1.保持原查询的核心意图
        2.使用不同的词汇和表述方式
        3.考虑同义词、相关概念
        4.每行一个变体，不要编号
        变体列表:
        """)
    def optimize(self,query:str)->list[str]:
        """
        生成查询变体

        Args:
            query: 原始查询

        Returns:
             包含原始查询和变体的列表
        :param query:
        :return:
        """
        app_logger.info(f"生成查询变体: {query}")
        # 调用 LLM 生成变体
        messages = self.prompt.format_messages(
            query=query,
            num=self.num_variants
        )

        response = model.invoke(messages)
        variants = [line.strip() for line in response.content.strip().split('\n') if line.strip()]
        # 添加原始查询
        all_queries = [query] + variants[:self.num_variants]
        for i, q in enumerate(all_queries):
            app_logger.debug(f"  {i + 1}. {q}")

        return all_queries


class HyDEOptimizer:
    """
    HyDE (Hypothetical Document Embeddings) 优化器
    生成假设性文档用于检索

    这个意思就是不用用的query去检索vectorstore  而是根据query去生成假设性答案  然后去根据这个答案去检索vectorstore
    """

    def __init__(self):
        self.prompt = ChatPromptTemplate.from_template(
            """请根据以下问题，生成一段假设性的回答文档。这个文档应该包含可能的答案内容。

问题：{query}

要求：
1. 200-300 字
2. 包含具体的景点名称、特点、推荐理由
3. 使用旅游攻略的语言风格

假设性文档："""
        )

    def generate_hypothetical_doc(self, query: str) -> str:
            """
            生成假设性文档

            Args:
                query: 原始查询

            Returns:
                假设性文档文本
            """

            app_logger.info(f"生成假设性文档: {query}")

            messages = self.prompt.format_messages(query=query)
            response = model.invoke(messages)

            hypothetical_doc = response.content.strip()

            app_logger.debug(f"假设性文档: {hypothetical_doc[:100]}...")

            return hypothetical_doc

class QueryRewriter:
        """
        查询改写器
        修正错别字、口语化表达
        """

        def __init__(self):
            self.prompt = ChatPromptTemplate.from_template(
                """你是一个查询改写专家。请将用户的口语化查询改写为更规范的书面表达。

    原始查询：{query}

    要求：
    1. 修正错别字
    2. 将口语转为书面语
    3. 保持查询意图不变
    4. 只返回改写后的查询，不要解释

    改写后："""
            )

        def rewrite(self, query: str) -> str:
            """
            改写查询

            Args:
                query: 原始查询

            Returns:
                改写后的查询
            """

            app_logger.info(f"改写查询: {query}")

            messages = self.prompt.format_messages(query=query)
            response = model.invoke(messages)

            rewritten = response.content.strip()

            app_logger.debug(f"改写结果: {rewritten}")

            return rewritten

##综合优化器

class AdvancedQueryOptimizer:
    """
    综合查询优化器
    整合了above  multiquery HYDE 查询改写
    """
    def __init__(self,strategy:str = 'multi_query'):
        """
        Args:
            strategy: 优化策略
                - "multi_query": 使用 Multi-Query
                - "hyde": 使用 HyDE
                - "rewrite": 使用查询改写
                - "hybrid": 组合使用
        """
        self.strategy = strategy
        self.multi_query = MultiQueryOptimizer()
        self.hyde = HyDEOptimizer()
        self.rewriter = QueryRewriter()

    def optimize(self,query:str)->list[str]:
        """
        根据策略优化查询
        :param query:
        :return:
        """
        if self.strategy == 'multi_query':
            return self.multi_query.optimize(query)
        elif self.strategy == 'hyde':
            return [query,self.hyde.generate_hypothetical_doc(query)]
        elif self.strategy == "hybrid":
            # 先改写，再生成变体
            rewritten = self.rewriter.rewrite(query)
            variants = self.multi_query.optimize(rewritten)
            return variants
        else:
            app_logger.warning(f"未知策略: {self.strategy}，使用原始查询")
            return [query]  #本质上是为了对齐下游