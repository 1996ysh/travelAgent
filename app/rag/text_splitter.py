"""
文本切分:父文档+子文档策略
"""
from typing import Tuple

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.utils.logger import app_logger


class ParentDocumentSplitter:
    """
    父文档切分器

    策略：
    - 父文档：1000 字符/块（用于最终上下文）
    - 子文档：200 字符/块（用于向量检索）
    - 子文档关联父文档 ID
    """
    def __init__(
            self,
            parent_chunk_size:int = 1000,
            parent_chunk_overlap:int = 200,
            child_chunk_size:int = 200,
            child_chunk_overlap:int = 50
            ):
             self.parent_splitter = RecursiveCharacterTextSplitter(
                 chunk_size=parent_chunk_size,
                 chunk_overlap=parent_chunk_overlap,
                 separators=["\n\n", "\n", "。", "，", " ", ""]
             )
             self.child_splitter = RecursiveCharacterTextSplitter(
                 chunk_size=child_chunk_size,
                 chunk_overlap=child_chunk_overlap,
                 separators=["\n\n", "\n", "。", "，", " ", ""]
             )
    def split_documents(
            self,
            documents:list[Document]
            )->Tuple[list[Document],list[Document]]:
        """
        切分文档为父文档和子文档
        :param documents: 父文档列表
        :return:子文档列表（包含 parent_id）
        """
        parent_docs = []
        child_docs = []
        #interpret this code that
        # first  for split  the source doc into some parent docs
        # second for split  every parent docs into child parent and add id attach it
        # third  for attach parent_id into every child parent
        for doc in documents:
            #切分源文档为父文档
            parent_chunks = self.parent_splitter.split_documents([doc])
            #为每个父文档生成id
            for i,parent_chunks in enumerate(parent_chunks):
                parent_id = f'{doc.metadata.get('source','unknow')}_{i}'
                parent_chunks.metadata['parent_id'] = parent_id
                parent_docs.append(parent_chunks)
                #把父文档切分成子文档
                child_chunks = self.parent_splitter.split_documents([parent_chunks])
                for child_chunk in child_chunks:
                    child_chunk.metadata['parent_id'] = parent_id
                    child_docs.append(child_chunk)
        app_logger.info(
            f"切分完成: {len(parent_docs)} 个父文档, "
            f"{len(child_docs)} 个子文档"
        )
        return parent_docs, child_docs
