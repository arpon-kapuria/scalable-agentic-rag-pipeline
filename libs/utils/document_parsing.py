from pipelines.ingestion.loaders.docx import parse_docx_bytes
from pipelines.ingestion.loaders.html import parse_html_bytes
from pipelines.ingestion.loaders.pdf import parse_pdf_bytes


def parse_document(file_bytes: bytes, filename: str):
    """
    Routes document to the correct parser based on file extension.
    """
    ext = filename.lower().split(".")[-1]

    if ext == "pdf":
        return parse_pdf_bytes(file_bytes, filename)

    elif ext == "docx":
        return parse_docx_bytes(file_bytes, filename)

    elif ext in ["html", "htm"]:
        return parse_html_bytes(file_bytes, filename)

    else:
        raise ValueError(f"Unsupported file type: {ext}")