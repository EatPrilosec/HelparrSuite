from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    show_id = Column(Integer, ForeignKey("shows.id", ondelete="CASCADE"), nullable=False, index=True)
    sonarr_episode_id = Column(Integer, unique=True, index=True, nullable=False)
    season_number = Column(Integer, nullable=False, index=True)
    episode_number = Column(Integer, nullable=False, index=True)
    absolute_episode_number = Column(Integer, nullable=True)
    title = Column(String(255), nullable=False)
    overview = Column(Text, nullable=True)
    air_date = Column(String(50), nullable=True)
    runtime_mins = Column(Integer, nullable=True)
    has_file = Column(Boolean, default=False)
    monitored = Column(Boolean, default=True)

    # Local LLM Verification Status
    ai_verification_status = Column(String(50), default="PENDING")  # PENDING, EXACT_MATCH, AI_MATCHED, FLAGGED_MISMATCH, NO_MATCH
    ai_confidence_score = Column(Float, default=0.0)
    ai_audit_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    show = relationship("Show", back_populates="episodes")
    transcripts = relationship("Transcript", back_populates="episode", cascade="all, delete-orphan")
    source_variations = relationship("EpisodeSourceMetadata", back_populates="episode", cascade="all, delete-orphan")
