import tempfile
import logging
from typing import Any, Dict, Tuple
from unstructured.partition.pdf import partition_pdf

logger = logging.getLogger(__name__)

def parse_pdf_bytes(file_bytes: bytes, filename: str) -> Tuple[str, Dict[str, Any]]: 
    """
    Parses a PDF file stream using a temporary file for memory efficiency.
    Extracts text and attempts to preserve table structure via HTML metadata.
    
    Args:
        file_bytes: The raw bytes of the PDF file.
        filename: Original filename for metadata.
        
    Returns:
        Tuple containing (extracted_text_content, metadata_dict)
    """
    text_content = ""
    tables = []

    # Use a temporary file on disk (EBS/Ephemeral storage)
    # instead of processing entirely in RAM (BytesIO).
    # This is critical for preventing OOM kills on K8s workers with large PDFs.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as temp_file:
        try:
            # 1. Write the PDF bytes to the temporary file
            temp_file.write(file_bytes)
            temp_file.flush()

            # 2. Partition PDF
            # strategy="hi_res" uses OCR (Tesseract) and Layout Analysis (Detectron2)
            # 'filename' arg allows unstructured to lazy-load chunks from disk.
            elements = partition_pdf(
                filename=temp_file.name, 
                strategy="hi_res",
                include_page_breaks=True,
                infer_table_structure=True
            )

            # 3. Process elements
            for element in elements:
                text_content += str(element) + "\n"

                # Check for Table elements to extract structural metadata
                if element.category == "Table":
                    # Save HTML representation for potential UI rendering later
                    if hasattr(element.metadata, "text_as_html"):
                        tables.append(element.metadata.text_as_html)

        except Exception as e:
            logger.error(f"Failed to parse PDF {filename}: {str(e)}")
            # In production, you might raise a specific ParseError here
            raise e
    
    metadata = {
        "filename": filename,
        "type": "pdf",
        "has_tables": len(tables) > 0,
        "table_count": len(tables)
    }
            
    return text_content, metadata