from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

def now():
    return datetime.now(timezone.utc)

class TournamentCard(Base):
    __tablename__ = "tournament_cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, default=lambda: uuid.uuid4().hex)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    tournament_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tournaments.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    theme_id: Mapped[str] = mapped_column(String(80), index=True)
    selected_options_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="available", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reserved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class TournamentGuess(Base):
    __tablename__ = "tournament_guesses"
    id: Mapped[int] = mapped_column(primary_key=True)
    guess_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, default=lambda: uuid.uuid4().hex)
    match_id: Mapped[int] = mapped_column(ForeignKey("tournament_matches.id"), index=True)
    attacker_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_card_id: Mapped[int] = mapped_column(ForeignKey("tournament_cards.id"), index=True)
    option_value: Mapped[str] = mapped_column(String(255))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    attempt_number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
