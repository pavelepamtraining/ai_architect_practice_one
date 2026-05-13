import os
import pickle

import faiss
import kagglehub
import numpy as np
import pandas as pd

from sentence_transformers import SentenceTransformer


# ============================================================
# Configuration
# ============================================================

DATASET_ID = "hgultekin/bbcnewsarchive"

VECTOR_STORE_DIR = "vector_store"

INDEX_PATH = os.path.join(
    VECTOR_STORE_DIR,
    "index.faiss"
)

DOCUMENTS_PATH = os.path.join(
    VECTOR_STORE_DIR,
    "documents.pkl"
)

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

MAX_DOCUMENTS = 10000


# ============================================================
# Load Dataset
# ============================================================

def load_dataset() -> pd.DataFrame:

    print("\nDownloading dataset from Kaggle...")

    path = kagglehub.dataset_download(DATASET_ID)

    files = os.listdir(path)

    csv_file = next(
        f for f in files
        if f.endswith(".csv")
    )

    csv_path = os.path.join(path, csv_file)

    print(f"CSV file: {csv_path}")

    df = pd.read_csv(
        csv_path,
        sep="\t",
        on_bad_lines="skip"
    )

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    return df


# ============================================================
# Build Text Documents
# ============================================================

def build_documents(df: pd.DataFrame) -> list[str]:
    """
    Convert BBC news rows into semantic documents.
    """

    documents = []

    for _, row in df.iterrows():

        title = str(row.get("title", ""))

        content = str(row.get("content", ""))

        category = str(row.get("category", ""))

        document = (
            f"Category: {category}\n"
            f"Title: {title}\n\n"
            f"{content}"
        )

        documents.append(document)

    return documents


# ============================================================
# Main Index Builder
# ============================================================

def main():

    print("BUILDING BBC NEWS RAG INDEX")

    # --------------------------------------------------------
    # Create vector store directory
    # --------------------------------------------------------

    os.makedirs(
        VECTOR_STORE_DIR,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Load dataset
    # --------------------------------------------------------

    df = load_dataset()

    print(f"\nDataset rows: {len(df)}")

    # --------------------------------------------------------
    # Limit dataset size for demo
    # --------------------------------------------------------

    df = df.head(MAX_DOCUMENTS)

    # --------------------------------------------------------
    # Build semantic documents
    # --------------------------------------------------------

    print("\nBuilding semantic documents...")

    documents = build_documents(df)

    print(f"Generated documents: {len(documents)}")

    # --------------------------------------------------------
    # Load embedding model
    # --------------------------------------------------------

    print("\nLoading embedding model...")

    embedding_model = SentenceTransformer(
        EMBEDDING_MODEL_NAME
    )

    # --------------------------------------------------------
    # Generate embeddings
    # --------------------------------------------------------

    print("\nGenerating embeddings...")

    embeddings = embedding_model.encode(
        documents,
        show_progress_bar=True
    )

    embeddings = np.array(
        embeddings,
        dtype="float32"
    )

    print(f"Embeddings shape: {embeddings.shape}")

    # --------------------------------------------------------
    # Build FAISS index
    # --------------------------------------------------------

    print("\nBuilding FAISS index...")

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)

    index.add(embeddings)

    print(f"Indexed vectors: {index.ntotal}")

    # --------------------------------------------------------
    # Save FAISS index
    # --------------------------------------------------------

    print("\nSaving FAISS index...")

    faiss.write_index(
        index,
        INDEX_PATH
    )

    # --------------------------------------------------------
    # Save documents
    # --------------------------------------------------------

    print("Saving documents...")

    with open(DOCUMENTS_PATH, "wb") as f:

        pickle.dump(documents, f)

    print("\nDONE")
    print("=" * 80)
    print(f"FAISS index: {INDEX_PATH}")
    print(f"Documents: {DOCUMENTS_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()