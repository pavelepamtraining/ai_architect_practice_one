from rag.retriever import RAGRetriever


def test_rag_retrieval():

    retriever = RAGRetriever(
        index_path="rag/vector_store/index.faiss",
        documents_path="rag/vector_store/documents.pkl"
    )

    results = retriever.retrieve(
        query="economic impact of inflation",
        k=3
    )

    assert len(results) > 0

    combined_text = " ".join(results).lower()

    assert (
        "inflation" in combined_text
        or "economy" in combined_text
        or "market" in combined_text
    )
