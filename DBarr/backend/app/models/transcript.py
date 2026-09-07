from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Transcript(Base):
    __tablename__ = "transcripts"
    __table_args__ = (UniqueConstraint("episode_id", "language", "source_provider", name="uix_episode_transcript"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    episode_id = Column(Integer, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    language = Column(String(20), nullable=False, default="en", index=True)
    is_native_language = Column(Boolean, default=True)
    source_provider = Column(String(50), nullable=False, index=True)  # opensubtitles, subdl
    
    # Dialogue content
    raw_content = Column(Text, nullable=False)  # Clean dialogue with timestamps & cues stripped
    preview_text = Column(Text, nullable=True)  # First ~500 chars for fast UI rendering
    dialogue_anchors = Column(Text, nullable=True)  # JSON-encoded array of opening lines & recognizable phrases
    subtitle_hash = Column(String(64), nullable=True, index=True)  # Hash to prevent duplicate downloads
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    episode = relationship("Episode", back_populates="transcripts")
