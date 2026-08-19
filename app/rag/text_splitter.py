"""
文本切分:父文档+子文档策略
"""
from typing import Tuple, Dict

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
            #父子映射表
             self.parent_child_map:Dict[str,str]={}  # child_id -> parent_id
             self.parent_docs: Dict[str, Document] = {}  # parent_id -> Document

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
                parent_chunks.metadata["chunk_type"] = "parent"
                parent_docs.append(parent_chunks)
                # 保存父文档
                self.parent_docs[parent_id] = parent_chunks
                #把父文档切分成子文档
                child_chunks = self.child_splitter.split_documents([parent_chunks])
                for j, child_chunks in enumerate(child_chunks):
                    child_id = f"{parent_id}__child_{j}"
                    child_chunks.metadata["child_id"] = child_id
                    child_chunks.metadata["parent_id"] = parent_id
                    child_chunks.metadata["chunk_type"] = "child"
                    child_docs.append(child_chunks)

                    # 建立映射
                    self.parent_child_map[child_id] = parent_id
        app_logger.info(
            f"切分完成: {len(parent_docs)} 个父文档, "
            f"{len(child_docs)} 个子文档"
        )

        return parent_docs, child_docs

    def get_parent_context(self,child_docs:list[Document])->list[Document]:
        """
        根据子文档获取对应的父文档
                Args:
            child_docs: 检索到的子文档列表
                Returns:
            对应的父文档列表（去重）
        :param child_docs:
        :return:
        """
        ## 遍历子文档  获取每一个子文档的doc_id  然后通过这个docid去get父文档的docid 然后去映射出这个文档
        app_logger.info(f"映射到父文档: {len(child_docs)} 个子文档")
        parent_ids = set()
        parent_context = []
        for child_doc in child_docs:
            parent_id = child_doc.metadata.get('parent_id')
            if parent_id and parent_id not in parent_ids:
                parent_ids.add(parent_id)
                #从映射表中获取父文档
                parent_doc = self.parent_docs.get(parent_id)
                if parent_id:
                    parent_context.append(parent_doc)
        app_logger.info(f'获取了{len(parent_context)} 个父文档')

        return parent_context