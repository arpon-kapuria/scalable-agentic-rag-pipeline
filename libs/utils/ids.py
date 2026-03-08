"""
Handle unique id generation for chat sessions, file uploads, and OpenTelemetry traces.
Handles session for each user.
"""

import uuid
import hashlib

def generate_session_id() -> str:
    """Generates a standard UUID for for chat sessions"""
    return str(uuid.uuid4())

def generate_file_id(content: bytes) -> str:
    """
    Generate a deterministic ID based on file content.
    Prevents uploading the exact same file twice.
    """
    return hashlib.md5(content).hexdigest()

def generate_trace_id() -> str:
    """Generate ID for OpenTelemetry traces"""
    return uuid.uuid4().hex
