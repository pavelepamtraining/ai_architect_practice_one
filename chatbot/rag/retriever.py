import pickle

import faiss
import numpy as np

from sentence_transformers import SentenceTransformer


class RAGRetriever:
    """Semantic retriever over FAISS vector store."""

    def __init__(
        self,
        index_path: str,
        documents_path: str,
        embedding_model_name: str = "all-MiniLM-L6-v2"
    ):

        # ----------------------------------------------------
        # Load embedding model
        # ----------------------------------------------------

        self.embedding_model = SentenceTransformer(
            embedding_model_name
        )

        # ----------------------------------------------------
        # Load FAISS index
        # ----------------------------------------------------

        self.index = faiss.read_index(index_path)

        # ----------------------------------------------------
        # Load documents
        # ----------------------------------------------------

        with open(documents_path, "rb") as f:

            self.documents = pickle.load(f)

    def retrieve(
        self,
        query: str,
        k: int = 3
    ) -> list[str]:

        # ----------------------------------------------------
        # Embed query
        # ----------------------------------------------------

        query_embedding = self.embedding_model.encode(
            [query]
        )

        query_embedding = np.array(
            query_embedding,
            dtype="float32"
        )

        # ----------------------------------------------------
        # Search FAISS
        # ----------------------------------------------------

        distances, indices = self.index.search(
            query_embedding,
            k
        )

        results = []

        for idx in indices[0]:

            if idx < len(self.documents):

                results.append(
                    self.documents[idx]
                )

        return results