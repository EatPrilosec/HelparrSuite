from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class EpisodeSourceMetadata(Base):
    __tablename__ = "episode_source_metadata"
    __table_args__ = (UniqueConstraint("episode_id", "source_name", name="uix_episode_source"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    episode_id = Column(Integer, ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True)
    show_id = Column(Integer, ForeignKey("shows.id", ondelete="CASCADE"), nullable=False, index=True)

    source_name = Column(String(50), nullable=False, index=True)  # tmdb, tvmaze, omdb
    source_show_id = Column(String(100), nullable=True)
    source_episode_id = Column(String(100), nullable=True)

    # Source numbering variations (often differs from Sonarr)
    source_season_number = Column(Integer, nullable=True)
    source_episode_number = Column(Integer, nullable=True)
    source_absolute_number = Column(Integer, nullable=True)

    title = Column(String(255), nullable=True)
    alternate_titles = Column(Text, nullable=True)  # JSON-encoded array of title aliases
    overview = Column(Text, nullable=True)
    air_date = Column(String(50), nullable=True)
    runtime_mins = Column(Integer, nullable=True)

    # Verification metadata
    match_method = Column(String(50), default="LLM_METADATA_CONFIRMED")
    match_confidence = Column(Float, default=1.0)
    llm_reasoning = Column(Text, nullable=True)
    raw_metadata = Column(Text, nullable=True)  # JSON dump of source payload

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    episode = relationship("Episode", back_populates="source_variations")
    show = relationship("Show", back_populates="source_metadata")
