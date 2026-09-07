from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Show(Base):
    __tablename__ = "shows"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sonarr_series_id = Column(Integer, unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False, index=True)
    clean_title = Column(String(255), nullable=True)
    sort_title = Column(String(255), nullable=True)
    original_title = Column(String(255), nullable=True)
    year = Column(Integer, nullable=True)
    status = Column(String(50), nullable=True)
    overview = Column(Text, nullable=True)
    poster_url = Column(String(500), nullable=True)
    original_language = Column(String(50), nullable=True, default="English")
    path = Column(String(500), nullable=True)
    monitored = Column(Boolean, default=True)

    # External cross-referenced identifiers
    tvdb_id = Column(Integer, nullable=True, index=True)
    tmdb_id = Column(Integer, nullable=True, index=True)
    imdb_id = Column(String(50), nullable=True, index=True)
    tvmaze_id = Column(Integer, nullable=True, index=True)

    # AI verification status across the entire show
    audit_status = Column(String(50), default="NOT_AUDITED")  # NOT_AUDITED, VERIFIED, HAS_WARNINGS, FAILED
    last_audited_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    episodes = relationship(
        "Episode",
        back_populates="show",
        cascade="all, delete-orphan",
        order_by="Episode.season_number, Episode.episode_number"
    )
    source_metadata = relationship(
        "EpisodeSourceMetadata",
        back_populates="show",
        cascade="all, delete-orphan"
    )
