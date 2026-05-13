from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Float
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
