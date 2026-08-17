from pathlib import Path

from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_core.documents import Document

from app.utils.logger import app_logger


class DocumentManager:
    """文档管理器"""
    def __init__(self,base_dir:str=None,):
        if base_dir is None:
            #获取项目根目录  __file__是内置变量表示当前文件所在的位置
            project_root = Path(__file__).parent.parent.parent
            self.base_dir = project_root/'data'/'documents'
        else:
            self.base_dir = Path(base_dir)
    def load_destination_documents(self)->list[Document]:
        """加载所有目的地文档"""
        destinations_dir = self.base_dir/'destinations'
        if not destinations_dir.exists():
            app_logger.warning(f"目的地文档目录不存在: {destinations_dir}")
            return []
        # 加载 Markdown 文件
        loader = DirectoryLoader(
            str(destinations_dir),
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"} # 自动检测文件编码（避免乱码）
        )
        documents = loader.load()
        app_logger.info(f"加载了 {len(documents)} 个目的地文档")
        # 添加元数据
        for doc in documents:
            doc.metadata["source_type"] = "destination_guide"
            doc.metadata["category"] = "destinations"

        return documents
    def load_food_documents(self) -> list[Document]:
        """加载美食文档"""
        pass

    def load_accommodation_documents(self) -> list[Document]:
        """加载住宿文档"""
        pass
