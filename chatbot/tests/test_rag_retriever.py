from rag.retriever import RAGRetriever


def test_rag_retrieval():

    retriever = RAGRetriever(
        index_path="rag/vector_store/index.faiss",
        documents_path="rag/vector_store/documents.pkl"
    )

    query = "economic impact of inflation"

    results = retriever.retrieve(
        query=query,
        k=3
    )

    print("\nRESULTS:")
    print("=" * 80)

    for i, result in enumerate(results, 1):

        print(f"\nResult #{i}")
        print("-" * 80)
        print(result[:1000])

    # --------------------------------------------------------
    # Basic assertions
    # --------------------------------------------------------

    assert len(results) > 0

    combined_text = " ".join(results).lower()

    expected_keywords = [
        "economy",
        "inflation",
        "market",
        "financial",
        "prices"
    ]

    assert any(
        keyword in combined_text
        for keyword in expected_keywords
    )