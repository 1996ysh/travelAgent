from pathlib import Path

from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_core.documents import Document

from app.utils.logger import app_logger


class DocumentManager:
    """文档管理器：按 destinations / food / accommodation / tips 分类加载。"""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            project_root = Path(__file__).parent.parent.parent
            self.base_dir = project_root / "data" / "documents"
        else:
            self.base_dir = Path(base_dir)

    def _load_markdown_dir(
        self,
        subdir: str,
        *,
        source_type: str,
        category: str,
        parse_city_from_filename: bool = False,
    ) -> list[Document]:
        """从子目录加载 Markdown，并写入统一元数据。"""
        target_dir = self.base_dir / subdir
        if not target_dir.exists():
            app_logger.warning(f"文档目录不存在: {target_dir}")
            return []

        loader = DirectoryLoader(
            str(target_dir),
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
        )
        documents = loader.load()
        app_logger.info(f"加载了 {len(documents)} 个 {category} 文档")

        for doc in documents:
            doc.metadata["source_type"] = source_type
            doc.metadata["category"] = category
            if parse_city_from_filename:
                source = doc.metadata.get("source", "")
                city = Path(source).stem if source else ""
                if city:
                    doc.metadata["city"] = city

        return documents

    def load_destination_documents(self) -> list[Document]:
        """加载按城市划分的目的地概览文档。"""
        return self._load_markdown_dir(
            "destinations",
            source_type="destination_guide",
            category="destinations",
            parse_city_from_filename=True,
        )

    def load_food_documents(self) -> list[Document]:
        """加载按城市划分的美食详细文档。"""
        return self._load_markdown_dir(
            "food",
            source_type="food_guide",
            category="food",
            parse_city_from_filename=True,
        )

    def load_accommodation_documents(self) -> list[Document]:
        """加载按城市划分的住宿区域详细文档。"""
        return self._load_markdown_dir(
            "accommodation",
            source_type="accommodation_guide",
            category="accommodation",
            parse_city_from_filename=True,
        )

    def load_travel_tips_documents(self) -> list[Document]:
        """加载按城市划分的出行建议详细文档。"""
        return self._load_markdown_dir(
            "tips",
            source_type="travel_tips",
            category="tips",
            parse_city_from_filename=True,
        )

    def load_all_documents(self) -> list[Document]:
        """合并四类语料，供 RAG 管道一次索引。"""
        documents = (
            self.load_destination_documents()
            + self.load_food_documents()
            + self.load_accommodation_documents()
            + self.load_travel_tips_documents()
        )
        app_logger.info(f"合计加载 {len(documents)} 个知识库文档")
        return documents
