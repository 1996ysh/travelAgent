"""
使用 Ragas 评估旅行 RAG 的质量与效率（仅依赖 ragas + 项目现有依赖）。

指标：faithfulness / answer_relevancy / context_precision / context_recall
效率：检索延迟、端到端（检索+生成）延迟、缓存加速

运行：
  .venv/Scripts/python.exe tests/test_rag/ragas_eval.py
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from langchain_community.chat_models import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage
from ragas import EvaluationDataset, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from app.config import settings
from app.rag.Pipeline import AdvancedRAGPipeline
from app.rag.document_loader import DocumentManager
from app.rag.text_splitter import ParentDocumentSplitter
from app.rag.vectorstore import VectorStoreManager

EVAL_CASES = [
    {
        "category": "destinations",
        "question": "武汉黄鹤楼的门票多少钱？开放时间是什么？",
        "ground_truth": "黄鹤楼门票70元（学生半价35元），开放时间8:30-18:00。",
    },
    {
        "category": "destinations",
        "question": "成都大熊猫繁育研究基地有什么游玩建议？",
        "ground_truth": "建议游览约3小时，务必早8点前抵达因上午熊猫活跃、下午多睡觉；可关注月亮产房、太阳产房、幼年大熊猫别墅，园区可坐观光车。",
    },
    {
        "category": "food",
        "question": "武汉有哪些必吃美食和推荐美食街区？",
        "ground_truth": "必吃包括热干面、三鲜豆皮、排骨藕汤、油饼包烧麦、潜江油焖大虾、糊汤粉配油条；美食街区有粮道街、吉庆街、水塔街。",
    },
    {
        "category": "food",
        "question": "重庆火锅人均大概多少？不吃辣要注意什么？",
        "ground_truth": "重庆火锅人均约80-120元；不吃辣应提前告知店家微辣或免辣，也可搭配冰粉等解辣。",
    },
    {
        "category": "accommodation",
        "question": "第一次去成都住哪个区域比较方便？大概什么价位？",
        "ground_truth": "首次出游优先春熙路/太古里区域，交通美食购物便利，价格约200-500元/晚。",
    },
    {
        "category": "accommodation",
        "question": "青岛栈桥附近住宿有什么特点？",
        "ground_truth": "栈桥/老城区欧式建筑集中、临近海边景点密集，价格约200-480元/晚，适合观光打卡；部分老楼可能无电梯。",
    },
    {
        "category": "tips",
        "question": "去重庆旅游穿什么鞋？有哪些出行避坑？",
        "ground_truth": "务必穿舒适防滑运动鞋勿穿高跟鞋；山城导航可能失灵要多看路标；洪崖洞解放碑节假日人多建议错峰；行程勿过满。",
    },
    {
        "category": "tips",
        "question": "咸宁泡温泉有什么注意事项？最佳季节是什么时候？",
        "ground_truth": "温泉旺季约11月到次年3月；泡汤每次约15-20分钟休息一次避免头晕；自带泳衣更划算；高血压心脏病患者需遵医嘱且勿饮酒后入池。",
    },
    {
        "category": "destinations",
        "question": "长沙湖南省博物馆需要预约吗？有什么必看展品？",
        "ground_truth": "免费但需提前约3天预约，周一闭馆；必看马王堆汉墓陈列、素纱襌衣、T型帛画。",
    },
    {
        "category": "food",
        "question": "青岛吃海鲜推荐去哪些街区？要注意什么？",
        "ground_truth": "可去营口路海鲜夜市、劈柴院、台东步行街；应选择正规门店避免无资质摊贩，按斤点先问价，注意海鲜过敏与适量饮酒。",
    },
]


def build_pipeline(enable_cache: bool = False, *, recreate_index: bool = True) -> AdvancedRAGPipeline:
    """用同一套切分结果建库，保证 parent_id 与检索子块一致。"""
    import shutil

    doc_manager = DocumentManager()
    documents = doc_manager.load_all_documents()
    splitter = ParentDocumentSplitter()
    _, child_docs = splitter.split_documents(documents)
    vs_manager = VectorStoreManager()
    if recreate_index:
        if vs_manager.persist_directory.exists():
            shutil.rmtree(vs_manager.persist_directory, ignore_errors=True)
        vs_manager.persist_directory.mkdir(parents=True, exist_ok=True)
        vectorstore = vs_manager.create_vectorstore(child_docs)
    else:
        try:
            vectorstore = vs_manager.load_vectorstore()
        except Exception:
            vectorstore = vs_manager.create_vectorstore(child_docs)
    return AdvancedRAGPipeline(
        vectorstore=vectorstore,
        all_documents=child_docs,
        parent_splitter=splitter,
        query_strategy="multi_query",
        use_llm_reranker=False,
        top_k=3,
        enable_cache=enable_cache,
    )


# 评测默认用较便宜且额度更稳的模型；可用环境变量 RAGAS_EVAL_MODEL 覆盖
EVAL_MODEL = __import__("os").environ.get("RAGAS_EVAL_MODEL", "qwen-turbo")


def make_llm() -> ChatTongyi:
    return ChatTongyi(
        model=EVAL_MODEL,
        api_key=settings.dashscope_api_key,
        temperature=0.2,
    )


def generate_answer(llm: ChatTongyi, question: str, contexts: list[str]) -> str:
    context_block = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(contexts, 1))
    messages = [
        SystemMessage(
            content=(
                "你是旅行顾问。请严格依据给定资料回答用户问题，"
                "不要编造资料中没有的信息；若资料不足请明确说明。"
            )
        ),
        HumanMessage(
            content=f"资料：\n{context_block}\n\n问题：{question}\n\n请用简洁中文回答。"
        ),
    ]
    resp = llm.invoke(messages)
    return (resp.content or "").strip()


def summarize_latency(values: list[float]) -> dict:
    return {
        "avg_ms": round(statistics.mean(values), 1),
        "p50_ms": round(statistics.median(values), 1),
        "min_ms": round(min(values), 1),
        "max_ms": round(max(values), 1),
    }


def measure_cache_speedup(pipeline_cached: AdvancedRAGPipeline) -> dict:
    q = EVAL_CASES[0]["question"]
    t0 = time.perf_counter()
    pipeline_cached.retrieve(q)
    cold = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    pipeline_cached.retrieve(q)
    warm = (time.perf_counter() - t1) * 1000
    return {
        "query": q,
        "cold_ms": round(cold, 1),
        "warm_ms": round(warm, 1),
        "speedup_x": round(cold / warm, 2) if warm > 0 else None,
    }


def main() -> None:
    print("=" * 60)
    print("Ragas RAG 评测开始")
    print("=" * 60)

    llm = make_llm()
    pipeline = build_pipeline(enable_cache=False)

    rows = []
    retrieve_latencies: list[float] = []
    e2e_latencies: list[float] = []
    per_case = []

    for case in EVAL_CASES:
        q = case["question"]
        t0 = time.perf_counter()
        docs = [
            d
            for d in pipeline.retrieve(q, category=case["category"])
            if d is not None
        ]
        t1 = time.perf_counter()
        ctxs = [d.page_content for d in docs]
        ans = generate_answer(llm, q, ctxs)
        t2 = time.perf_counter()

        retrieve_ms = (t1 - t0) * 1000
        e2e_ms = (t2 - t0) * 1000
        retrieve_latencies.append(retrieve_ms)
        e2e_latencies.append(e2e_ms)

        rows.append(
            {
                "user_input": q,
                "retrieved_contexts": ctxs,
                "response": ans,
                "reference": case["ground_truth"],
            }
        )
        per_case.append(
            {
                "category": case["category"],
                "question": q,
                "retrieve_ms": round(retrieve_ms, 1),
                "e2e_ms": round(e2e_ms, 1),
                "n_contexts": len(ctxs),
                "answer_preview": ans[:200],
            }
        )
        print(f"\n[{case['category']}] {q}")
        print(f"  retrieve={retrieve_ms:.0f}ms e2e={e2e_ms:.0f}ms ctx={len(ctxs)}")
        print(f"  answer: {ans[:120]}{'...' if len(ans) > 120 else ''}")

    dataset = EvaluationDataset.from_list(rows)
    evaluator_llm = LangchainLLMWrapper(llm)
    embeddings = LangchainEmbeddingsWrapper(
        DashScopeEmbeddings(
            model="text-embedding-v2",
            dashscope_api_key=settings.dashscope_api_key,
        )
    )

    print("\n开始 Ragas 指标计算...")
    t_eval = time.perf_counter()
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=evaluator_llm,
        embeddings=embeddings,
        raise_exceptions=False,
    )
    eval_sec = time.perf_counter() - t_eval

    # 汇总 Ragas 分数（按样本平均）
    score_rows = getattr(result, "scores", None) or []
    metric_names = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    scores: dict[str, float | None] = {}
    for name in metric_names:
        vals = []
        for row in score_rows:
            if isinstance(row, dict) and name in row and row[name] is not None:
                try:
                    vals.append(float(row[name]))
                except (TypeError, ValueError):
                    pass
        scores[name] = round(sum(vals) / len(vals), 4) if vals else None

    # 缓存效率：复用当前管道开启缓存后测冷/热
    try:
        pipeline.cache.enabled = True
    except Exception:
        pass
    cache_stats = measure_cache_speedup(pipeline)

    report = {
        "n_samples": len(EVAL_CASES),
        "ragas_scores": scores,
        "ragas_eval_seconds": round(eval_sec, 1),
        "efficiency": {
            "retrieve": summarize_latency(retrieve_latencies),
            "e2e_retrieve_generate": summarize_latency(e2e_latencies),
            "cache": cache_stats,
        },
        "per_case": per_case,
        "per_sample_scores": score_rows,
    }

    out_dir = Path("tests/test_rag/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ragas_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("Ragas 质量分数")
    print("=" * 60)
    for k, v in scores.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    print("\n效率")
    print(f"  检索: {report['efficiency']['retrieve']}")
    print(f"  端到端: {report['efficiency']['e2e_retrieve_generate']}")
    print(f"  缓存: {report['efficiency']['cache']}")
    print(f"\n报告: {out_path}")


if __name__ == "__main__":
    main()
