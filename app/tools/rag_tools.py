"""
RAG 检索工具
将 Advanced RAG 管道封装为 Agent 可自主调用的工具

四个工具共用同一 Pipeline，但通过 category 硬过滤到对应知识库分区，
避免美食工具搜到住宿文档等跨类污染。
"""
from typing import Optional

from langchain_core.tools import tool, ToolException

from app.rag.Pipeline import AdvancedRAGPipeline
from app.rag.document_loader import DocumentManager
from app.rag.text_splitter import ParentDocumentSplitter
from app.rag.vectorstore import VectorStoreManager
from app.utils.logger import app_logger

# ============== 全局 RAG 管道实例（懒加载） ==============

_rag_pipeline: Optional[AdvancedRAGPipeline] = None
_parent_splitter: Optional[ParentDocumentSplitter] = None

# 工具 → 知识库 category 映射（与 document_loader 一致）
CATEGORY_DESTINATIONS = "destinations"
CATEGORY_FOOD = "food"
CATEGORY_ACCOMMODATION = "accommodation"
CATEGORY_TIPS = "tips"


async def _get_rag_pipeline() -> AdvancedRAGPipeline:
    """获取或初始化全局 RAG 管道实例（单例模式）"""
    global _rag_pipeline, _parent_splitter
    if _rag_pipeline is None:
        app_logger.info("🔧 初始化 RAG 管道...")
        # 1. 加载全部语料（目的地概览 + 美食/住宿/出行详情）
        doc_manager = DocumentManager()
        documents = doc_manager.load_all_documents()
        if not documents:
            app_logger.warning("⚠️ 未找到知识库文档，RAG 功能可能受限")
            documents = []
        # 2. 切分文档
        _parent_splitter = ParentDocumentSplitter()
        parent_docs, child_docs = _parent_splitter.split_documents(documents)
        # 3. 加载或创建向量数据库
        vs_manager = VectorStoreManager()
        try:
            vectorstore = vs_manager.load_vectorstore()
            app_logger.info("✅ 向量数据库加载成功")
        except Exception:
            app_logger.info("📦 向量数据库不存在，创建新的...")
            vectorstore = vs_manager.create_vectorstore(child_docs)
        # 4. 创建 RAG 管道
        _rag_pipeline = AdvancedRAGPipeline(
            vectorstore=vectorstore,
            all_documents=child_docs,
            parent_splitter=_parent_splitter,
            query_strategy="multi_query",
            use_llm_reranker=False,
            top_k=3,
            enable_cache=True,
        )
        app_logger.info("✅ RAG 管道初始化完成")
    return _rag_pipeline


def _format_rag_results(documents: list, query: str) -> str:
    """格式化 RAG 检索结果，附带 category / city 便于判断来源。"""
    if not documents:
        return f"未找到与「{query}」相关的信息。"

    result_parts = []
    for i, doc in enumerate(documents, 1):
        content = doc.page_content[:800]
        if len(doc.page_content) > 800:
            content += "..."

        source = doc.metadata.get("source", "未知来源")
        category = doc.metadata.get("category", "")
        city = doc.metadata.get("city", "")
        meta_bits = []
        if category:
            meta_bits.append(f"类型:{category}")
        if city:
            meta_bits.append(f"城市:{city}")
        meta_bits.append(f"来源:{source}")
        result_parts.append(f"【资料 {i}】\n{content}\n{' | '.join(meta_bits)}")

    return "\n\n".join(result_parts)


async def _retrieve_by_category(query: str, category: str) -> str:
    """统一检索入口：按 category 过滤后格式化返回。"""
    pipeline = await _get_rag_pipeline()
    documents = pipeline.retrieve(query, category=category)
    result = _format_rag_results(documents, query)
    app_logger.info(
        f"✅ RAG 检索完成 category={category}，返回 {len(documents)} 个文档"
    )
    return result


# ============== RAG 检索工具定义 ==============
@tool
async def search_destination_guide(query: str) -> str:
    """
    从目的地概览知识库中检索景点与行程信息。

    当你需要获取以下信息时应该使用此工具：
    - 目的地的景点介绍、门票价格、开放时间
    - 旅游攻略、游玩建议、推荐路线
    - 城市概况与行程骨架（美食/住宿仅作轻度提及）

    详细美食、住宿区域、出行注意事项请改用对应专用检索工具。

    Args:
        query: 检索查询，例如 "武汉黄鹤楼门票和游玩建议"、"成都必去景点推荐"

    Returns:
        检索到的相关攻略信息，如果没有找到会返回提示信息
    """
    app_logger.info(f"RAG 工具被调用[destinations]: {query}")
    try:
        return await _retrieve_by_category(query, CATEGORY_DESTINATIONS)
    except Exception as e:
        app_logger.error(f"❌ RAG 检索失败: {e}")
        raise ToolException(f"检索过程中出现错误：{str(e)}")


@tool
async def search_food_recommendations(query: str) -> str:
    """
    从分城市美食详细知识库中检索美食信息。

    当你需要获取以下信息时应该使用此工具：
    - 目的地的特色美食、必吃小吃与人均价格
    - 美食街区、餐次安排、饮食注意
    - 比目的地概览更细的餐饮资料

    Args:
        query: 美食相关查询，例如 "武汉特色美食推荐"、"成都火锅和建设路小吃"

    Returns:
        检索到的美食推荐信息
    """
    app_logger.info(f"美食检索工具被调用: {query}")
    try:
        return await _retrieve_by_category(query, CATEGORY_FOOD)
    except Exception as e:
        app_logger.error(f"❌ 美食检索失败: {e}")
        raise ToolException(f"检索过程中出现错误：{str(e)}")


@tool
async def search_accommodation_info(query: str) -> str:
    """
    从分城市住宿区域详细知识库中检索住宿建议。

    当你需要获取以下信息时应该使用此工具：
    - 目的地的住宿区域对比与推荐
    - 价位区间、适合人群、与景点动线关系
    - 酒店/民宿选区建议（具体可订房源请用酒店搜索工具）

    Args:
        query: 住宿相关查询，例如 "武汉住哪个区域好"、"成都春熙路附近住宿建议"

    Returns:
        检索到的住宿推荐信息
    """
    app_logger.info(f"住宿检索工具被调用: {query}")
    try:
        return await _retrieve_by_category(query, CATEGORY_ACCOMMODATION)
    except Exception as e:
        app_logger.error(f"❌ 住宿检索失败: {e}")
        raise ToolException(f"检索过程中出现错误：{str(e)}")


@tool
async def search_travel_tips(query: str) -> str:
    """
    从分城市出行建议详细知识库中检索实用信息。

    当你需要获取以下信息时应该使用此工具：
    - 目的地的旅行注意事项、避坑指南
    - 最佳旅游季节、穿衣建议
    - 当地交通、消费水平、预约与安全提示

    Args:
        query: 实用信息查询，例如 "武汉旅游注意事项"、"成都几月去最好"

    Returns:
        检索到的旅行实用信息
    """
    app_logger.info(f"旅行贴士检索工具被调用: {query}")
    try:
        return await _retrieve_by_category(query, CATEGORY_TIPS)
    except Exception as e:
        app_logger.error(f"❌ 旅行贴士检索失败: {e}")
        raise ToolException(f"检索过程中出现错误：{str(e)}")


# ============== 工具集合 ==============

def get_rag_tools() -> list:
    """获取所有 RAG 相关工具"""
    return [
        search_destination_guide,
        search_food_recommendations,
        search_accommodation_info,
        search_travel_tips,
    ]
