from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_text(text: str, chunk_size: int = 512, overlap: int = 50): 
    """
    Splits text into overlapping chunks.
    Standard optimization for Embedding Models (most have 512 or 8192 limits).
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, 
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunks = splitter.create_documents([text])

    # Map to dictionary format for Ray pipeline
    return [
        {
            "text": c.page_content, 
            "metadata": {
                "chunk_index": i
            }
        } 
        for i, c in enumerate(chunks)
    ]