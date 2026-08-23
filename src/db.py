from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .models import ExceptionRecord, MatchResult, ReconciliationMetrics, SourceRecord

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "reconcio.db"


class Base(DeclarativeBase):
    pass


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False)
    match_rate: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    source_records: Mapped[list["SourceRecordRow"]] = relationship(back_populates="run")


class SourceRecordRow(Base):
    __tablename__ = "source_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("audit_log.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    transaction_date: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[str] = mapped_column(String(200), default="")
    payer_name: Mapped[str] = mapped_column(String(100), default="")
    payment_method: Mapped[str] = mapped_column(String(50), default="")
    run: Mapped[AuditLog] = relationship(back_populates="source_records")


class MatchResultRow(Base):
    __tablename__ = "match_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("audit_log.id"), nullable=False)
    transaction_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    amounts_json: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str] = mapped_column(String(30), nullable=False)
    rules_json: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(Float)


class ExceptionRow(Base):
    __tablename__ = "exceptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("audit_log.id"), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sources_present_json: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_trace_json: Mapped[str] = mapped_column(Text, default="[]")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    ai_explanation_json: Mapped[str | None] = mapped_column(Text)


def get_session_factory(db_path: Path | str = DEFAULT_DB_PATH):
    engine = create_engine(f"sqlite:///{Path(db_path).resolve()}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def persist_run(records_by_source: dict[str, list[SourceRecord]], matches: list[MatchResult], exceptions: list[ExceptionRecord], metrics: ReconciliationMetrics, db_path: Path | str = DEFAULT_DB_PATH) -> int:
    Session = get_session_factory(db_path)
    with Session.begin() as session:
        audit = AuditLog(batch_size=sum(len(rows) for rows in records_by_source.values()), match_rate=metrics.matched_pct, duration_seconds=metrics.processing_time_seconds)
        session.add(audit)
        session.flush()
        for records in records_by_source.values():
            for record in records:
                session.add(SourceRecordRow(run_id=audit.id, source=record.source, transaction_id=record.transaction_id, amount=record.amount, transaction_date=record.transaction_date.isoformat(), reference=record.reference, payer_name=record.payer_name, payment_method=record.payment_method))
        for match in matches:
            session.add(MatchResultRow(run_id=audit.id, transaction_ids_json=json.dumps(match.transaction_ids), amounts_json=json.dumps(match.amounts), tier=match.tier, rules_json=json.dumps(match.rules_fired), confidence=match.confidence, similarity_score=match.similarity_score))
        for item in exceptions:
            session.add(ExceptionRow(run_id=audit.id, transaction_id=item.transaction_id, sources_present_json=json.dumps(item.sources_present), amount=item.amount, reason_code=item.reason_code, rule_trace_json=json.dumps(item.rule_trace), confidence=item.confidence, ai_explanation_json=json.dumps(item.ai_explanation) if item.ai_explanation else None))
        return audit.id


def get_run_history(db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    Session = get_session_factory(db_path)
    with Session() as session:
        rows = session.scalars(select(AuditLog).order_by(AuditLog.id.desc())).all()
        return [{"id": row.id, "timestamp": row.timestamp.isoformat(), "batch_size": row.batch_size, "match_rate": row.match_rate, "duration_seconds": row.duration_seconds} for row in rows]
