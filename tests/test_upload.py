import requests

upload_url = "http://localhost:9000/omnirag-corpus/uploads/3470288e-e1da-4785-8072-cb21ca5d5109/025e88b9-bde4-46a4-aff5-7d89138a2fa6.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=omnirag_admin%2F20260903%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260903T121203Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=content-type%3Bhost%3Bx-amz-meta-corpus_id%3Bx-amz-meta-original_filename&X-Amz-Signature=156a78ff3b03b64958f7fe0f22e759cdaa5f416f5b2a428e5192228f12b93c0e"

with open("attention_is_all_you_need.pdf", "rb") as f:
    resp = requests.put(
        upload_url,
        data=f,
        headers={
            "Content-Type": "application/pdf",
            "x-amz-meta-corpus_id": "3470288e-e1da-4785-8072-cb21ca5d5109",
            "x-amz-meta-original_filename": "attention_is_all_you_need.pdf",
        },
    )
print(resp.status_code, resp.text)
