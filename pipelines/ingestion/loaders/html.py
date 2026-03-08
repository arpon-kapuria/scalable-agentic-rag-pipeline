from bs4 import BeautifulSoup

def parse_html_bytes(file_bytes: bytes, filename: str):
    """
    Parses HTML content.
    Cleans scripts, styles, and extracts readable text.
    """
    soup = BeautifulSoup(file_bytes, "html.parser")

    # 1. Remove junk elements that confuse the LLM
    for script in soup(["script", "style", "meta", "noscript"]):
        script.decompose()

    # 2. Extract text
    text = soup.get_text(separator="\n")

    # 3. Clean Whitespace (Collapse multiple newlines)
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split(" "))
    text_content = "\n".join(chunk for chunk in chunks if chunk)

    metadata = {
        "filename": filename,
        "type": "html",
        "title": soup.title.string if soup.title else "Unltitled"
    }
    
    return text_content, metadata