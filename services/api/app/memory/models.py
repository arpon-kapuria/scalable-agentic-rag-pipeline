from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from datetime import datetime, timezone

Base = declarative_base()

class ChatHistory(Base):
    """
    SQLAlchemy Model for the 'chat_history' table.
    Stores the raw conversation log for auditing and context.
    """
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Session ID links messages to a specific conversation thread
    session_id = Column(String(255), index=True, nullable=False)
    
    # User ID for multi-tenancy
    user_id = Column(String(255), index=True, nullable=False)
    
    # Role: 'user', 'assistant', or 'system'
    role = Column(String(50), nullable=False)
    
    # The actual message content
    content = Column(Text, nullable=False)
    
    # Metadata: Token usage, latency, model version used
    metadata_ = Column(JSON, default=lambda: {}, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class Feedback(Base):
    """
    SQLAlchemy Model for the 'feedback' table.
    Stores user feedback about assistant responses.
    """
    __tablename__ = "feedback"
    
    id         = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False)
    user_id    = Column(String(255), nullable=False)
    message_id = Column(Integer, nullable=False)
    score      = Column(Integer, nullable=False)   # 1 or -1
    comment    = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))