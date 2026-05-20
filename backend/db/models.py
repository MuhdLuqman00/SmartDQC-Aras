from datetime import datetime
from sqlalchemy import Boolean, Integer, String, DateTime, ForeignKey, Float, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    sessions: Mapped[list["Session"]] = relationship(back_populates="dataset")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"), nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    dataset: Mapped["Dataset"] = relationship(back_populates="sessions")
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(back_populates="session")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False)
    result_type: Mapped[str] = mapped_column(String, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    session: Mapped["Session"] = relationship(back_populates="analysis_results")


class ZscoreArchive(Base):
    __tablename__ = "zscore_archive"

    id:         Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    ic_no:      Mapped[str]        = mapped_column(String,  nullable=False)
    period:     Mapped[str]        = mapped_column(String,  nullable=False)
    district:   Mapped[str]        = mapped_column(String,  nullable=False)
    state:      Mapped[str | None] = mapped_column(String,  nullable=True)
    waz:        Mapped[float | None] = mapped_column(Float, nullable=True)
    haz:        Mapped[float | None] = mapped_column(Float, nullable=True)
    baz:        Mapped[float | None] = mapped_column(Float, nullable=True)
    age_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime]   = mapped_column(DateTime, nullable=False)


class IndicatorSnapshot(Base):
    __tablename__ = "indicator_snapshots"

    id:               Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    period:           Mapped[str]        = mapped_column(String,  nullable=False)
    district:         Mapped[str]        = mapped_column(String,  nullable=False)
    state:            Mapped[str | None] = mapped_column(String,  nullable=True)
    stunting_rate:    Mapped[float | None] = mapped_column(Float, nullable=True)
    wasting_rate:     Mapped[float | None] = mapped_column(Float, nullable=True)
    underweight_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    overweight_rate:  Mapped[float | None] = mapped_column(Float, nullable=True)
    n_records:        Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at:       Mapped[datetime]   = mapped_column(DateTime, nullable=False)


class EntityLinkage(Base):
    __tablename__ = "entity_linkage"

    id:               Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    ic_no:            Mapped[str]        = mapped_column(String,  nullable=False)
    source_type:      Mapped[str]        = mapped_column(String,  nullable=False)
    dataset_id:       Mapped[str | None] = mapped_column(String,  ForeignKey("datasets.id"), nullable=True)
    name:             Mapped[str | None] = mapped_column(String,  nullable=True)
    dob:              Mapped[str | None] = mapped_column(String,  nullable=True)
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at:       Mapped[datetime]   = mapped_column(DateTime, nullable=False)


class User(Base):
    __tablename__ = "users"

    id:            Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    username:      Mapped[str]      = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str]      = mapped_column(String(200), nullable=False)
    role:          Mapped[str]      = mapped_column(String(20), nullable=False, default="viewer")
    is_active:     Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key:        Mapped[str]      = mapped_column(String(120), primary_key=True)
    value:      Mapped[str]      = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:    Mapped[int | None]    = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action:     Mapped[str]           = mapped_column(String(80), nullable=False)
    dataset_id: Mapped[str | None]    = mapped_column(String, ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    detail:     Mapped[str | None]    = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ChatSession(Base):
    """A persistent chat thread anchored to a dataset.

    One dataset can have many chat sessions (e.g. user opens a "stunting
    by district" chat, then later starts a "compare gender" chat against
    the same dataset). Cascading delete on dataset_id means the existing
    /datasets/delete flow auto-removes a dataset's chats with no extra
    code in _delete_datasets.
    """
    __tablename__ = "chat_sessions"

    id:         Mapped[str]      = mapped_column(String, primary_key=True)
    dataset_id: Mapped[str]      = mapped_column(String, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    # Auto-titled to the truncated first user question; user-renameable.
    title:      Mapped[str]      = mapped_column(String(200), nullable=False, default="New chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="chat_session", cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    """One turn in a chat session — user question, AI answer, or AI narrative.

    `data_json` carries auxiliary structured payload for the message:
    NLQ tabular results + optional chart_b64 for AI replies, the
    NarrativeRaw blob for narrative messages. `role` is the discriminator.
    """
    __tablename__ = "chat_messages"

    id:              Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_session_id: Mapped[str]              = mapped_column(
        String, ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role:            Mapped[str]              = mapped_column(String(20), nullable=False)  # 'user' | 'ai' | 'narrative'
    content:         Mapped[str]              = mapped_column(Text, nullable=False)
    data_json:       Mapped[dict | None]      = mapped_column(JSONB, nullable=True)
    created_at:      Mapped[datetime]         = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    chat_session: Mapped["ChatSession"] = relationship(back_populates="messages")
