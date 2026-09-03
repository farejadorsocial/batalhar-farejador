from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

def now(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(primary_key=True); email:Mapped[str]=mapped_column(String(320),unique=True,index=True); username:Mapped[str]=mapped_column(String(40),unique=True,index=True); password_hash:Mapped[str]=mapped_column(String(512))
    balance:Mapped[int]=mapped_column(Integer,default=0); points:Mapped[int]=mapped_column(Integer,default=0); xp:Mapped[int]=mapped_column(Integer,default=0); level:Mapped[int]=mapped_column(Integer,default=1)
    role:Mapped[str]=mapped_column(String(20),default="player"); is_active:Mapped[bool]=mapped_column(Boolean,default=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Tournament(Base):
    __tablename__="tournaments"
    id:Mapped[int]=mapped_column(primary_key=True); public_id:Mapped[str]=mapped_column(String(32),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    title:Mapped[str]=mapped_column(String(120)); category:Mapped[str]=mapped_column(String(40)); mode:Mapped[str]=mapped_column(String(20),default="free"); status:Mapped[str]=mapped_column(String(20),default="open")
    entry_fee:Mapped[int]=mapped_column(Integer,default=0); max_players:Mapped[int]=mapped_column(Integer); prize_pool:Mapped[int]=mapped_column(Integer,default=0)
    registration_deadline:Mapped[datetime]=mapped_column(DateTime(timezone=True)); starts_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); rules_json:Mapped[str]=mapped_column(Text,default="{}"); created_by:Mapped[int]=mapped_column(ForeignKey("users.id")); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class TournamentEntry(Base):
    __tablename__="tournament_entries"; __table_args__=(UniqueConstraint("tournament_id","user_id",name="uq_tournament_user"),)
    id:Mapped[int]=mapped_column(primary_key=True); entry_id:Mapped[str]=mapped_column(String(32),unique=True,index=True,default=lambda:uuid.uuid4().hex); tournament_id:Mapped[int]=mapped_column(ForeignKey("tournaments.id")); user_id:Mapped[int]=mapped_column(ForeignKey("users.id")); fee_paid:Mapped[int]=mapped_column(Integer,default=0); status:Mapped[str]=mapped_column(String(20),default="confirmed"); joined_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class TournamentMatch(Base):
    __tablename__="tournament_matches"
    id:Mapped[int]=mapped_column(primary_key=True)
    match_id:Mapped[str]=mapped_column(String(32),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    tournament_id:Mapped[int]=mapped_column(ForeignKey("tournaments.id"),index=True)
    round_number:Mapped[int]=mapped_column(Integer)
    match_number:Mapped[int]=mapped_column(Integer)
    player1_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True)
    player2_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True)
    player1_guess:Mapped[Optional[int]]=mapped_column(Integer,nullable=True)
    player2_guess:Mapped[Optional[int]]=mapped_column(Integer,nullable=True)
    target_number:Mapped[int]=mapped_column(Integer)
    winner_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True)
    status:Mapped[str]=mapped_column(String(20),default="pending")
    result_reason:Mapped[Optional[str]]=mapped_column(String(80),nullable=True)
    started_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    deadline:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    finished_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    replay_number:Mapped[int]=mapped_column(Integer,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint("tournament_id","round_number","match_number",name="uq_tournament_round_match"),)

class TournamentResult(Base):
    __tablename__="tournament_results"; __table_args__=(UniqueConstraint("tournament_id","user_id",name="uq_result_tournament_user"),)
    id:Mapped[int]=mapped_column(primary_key=True); tournament_id:Mapped[int]=mapped_column(ForeignKey("tournaments.id")); user_id:Mapped[int]=mapped_column(ForeignKey("users.id")); position:Mapped[int]=mapped_column(Integer); points_earned:Mapped[int]=mapped_column(Integer,default=0); xp_earned:Mapped[int]=mapped_column(Integer,default=0)

class Payment(Base):
    __tablename__="payments"
    id:Mapped[int]=mapped_column(primary_key=True); payment_id:Mapped[str]=mapped_column(String(32),unique=True,index=True,default=lambda:uuid.uuid4().hex); tournament_id:Mapped[int]=mapped_column(ForeignKey("tournaments.id")); user_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True); beneficiary_type:Mapped[str]=mapped_column(String(30)); position:Mapped[Optional[int]]=mapped_column(Integer,nullable=True); percentage:Mapped[int]=mapped_column(Integer,default=0); amount:Mapped[int]=mapped_column(Integer); status:Mapped[str]=mapped_column(String(20),default="pending"); ledger_transaction_id:Mapped[Optional[str]]=mapped_column(String(32),unique=True,nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class LedgerTransaction(Base):
    __tablename__="ledger_transactions"
    id:Mapped[int]=mapped_column(primary_key=True); transaction_id:Mapped[str]=mapped_column(String(32),unique=True,index=True,default=lambda:uuid.uuid4().hex); idempotency_key:Mapped[str]=mapped_column(String(120),unique=True,index=True); user_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True); tournament_id:Mapped[Optional[int]]=mapped_column(ForeignKey("tournaments.id"),nullable=True); kind:Mapped[str]=mapped_column(String(30)); amount:Mapped[int]=mapped_column(Integer); balance_after:Mapped[int]=mapped_column(Integer); reference_id:Mapped[Optional[str]]=mapped_column(String(64),nullable=True); description:Mapped[str]=mapped_column(String(255)); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class RefreshSession(Base):
    __tablename__="refresh_sessions"
    id:Mapped[int]=mapped_column(primary_key=True); jti:Mapped[str]=mapped_column(String(80),unique=True,index=True); user_id:Mapped[int]=mapped_column(ForeignKey("users.id")); expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); revoked:Mapped[bool]=mapped_column(Boolean,default=False)

class EconomyState(Base):
    __tablename__="economy_state"
    id:Mapped[int]=mapped_column(primary_key=True)
    authorized_supply:Mapped[int]=mapped_column(Integer,default=10000)
    minted_supply:Mapped[int]=mapped_column(Integer,default=0)
    xp_rate:Mapped[int]=mapped_column(Integer,default=1000)
    farejador_rate:Mapped[int]=mapped_column(Integer,default=1)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class Notification(Base):
    __tablename__="notifications"
    id:Mapped[int]=mapped_column(primary_key=True)
    notification_id:Mapped[str]=mapped_column(String(32),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    kind:Mapped[str]=mapped_column(String(40))
    title:Mapped[str]=mapped_column(String(120))
    message:Mapped[str]=mapped_column(String(500))
    tournament_id:Mapped[Optional[int]]=mapped_column(ForeignKey("tournaments.id"),nullable=True,index=True)
    match_id:Mapped[Optional[int]]=mapped_column(ForeignKey("tournament_matches.id"),nullable=True,index=True)
    is_read:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Achievement(Base):
    __tablename__="achievements"
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(50),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(100))
    description:Mapped[str]=mapped_column(String(255))
    xp_reward:Mapped[int]=mapped_column(Integer,default=0)
    points_reward:Mapped[int]=mapped_column(Integer,default=0)
    active:Mapped[bool]=mapped_column(Boolean,default=True)

class UserAchievement(Base):
    __tablename__="user_achievements"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    achievement_id:Mapped[int]=mapped_column(ForeignKey("achievements.id"),index=True)
    awarded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint("user_id","achievement_id",name="uq_user_achievement"),)


class PlatformLedgerTransaction(Base):
    __tablename__="platform_ledger"
    id:Mapped[int]=mapped_column(primary_key=True)
    transaction_id:Mapped[str]=mapped_column(String(32),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    tournament_id:Mapped[Optional[int]]=mapped_column(ForeignKey("tournaments.id"),nullable=True,index=True)
    kind:Mapped[str]=mapped_column(String(40))
    amount:Mapped[int]=mapped_column(Integer)
    balance_after:Mapped[int]=mapped_column(Integer)
    reference_id:Mapped[Optional[str]]=mapped_column(String(80),nullable=True,index=True)
    description:Mapped[str]=mapped_column(String(255))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class Season(Base):
    __tablename__="seasons"
    id:Mapped[int]=mapped_column(primary_key=True)
    public_id:Mapped[str]=mapped_column(String(32),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    name:Mapped[str]=mapped_column(String(100),unique=True)
    starts_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    ends_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    active:Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class TournamentEvent(Base):
    __tablename__="tournament_events"
    id:Mapped[int]=mapped_column(primary_key=True)
    event_id:Mapped[str]=mapped_column(String(32),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    tournament_id:Mapped[int]=mapped_column(ForeignKey("tournaments.id"),index=True)
    event_type:Mapped[str]=mapped_column(String(50),index=True)
    actor_user_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    match_id:Mapped[Optional[int]]=mapped_column(ForeignKey("tournament_matches.id"),nullable=True,index=True)
    payload_json:Mapped[str]=mapped_column(Text,default="{}")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class EconomyMarket(Base):
    __tablename__="economy_market"
    id:Mapped[int]=mapped_column(primary_key=True)
    name:Mapped[str]=mapped_column(String(40),unique=True)
    dynamic_pricing_enabled:Mapped[bool]=mapped_column(Boolean,default=False)
    base_xp_rate:Mapped[int]=mapped_column(Integer,default=1000)
    min_xp_rate:Mapped[int]=mapped_column(Integer,default=1000)
    max_xp_rate:Mapped[int]=mapped_column(Integer,default=1000000)
    buy_pressure:Mapped[int]=mapped_column(Integer,default=0)
    sell_pressure:Mapped[int]=mapped_column(Integer,default=0)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class Visitor(Base):
    __tablename__="security_visitors"
    id:Mapped[int]=mapped_column(primary_key=True)
    visitor_id:Mapped[str]=mapped_column(String(64),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    first_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    last_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
    first_path:Mapped[Optional[str]]=mapped_column(String(500),nullable=True)
    last_path:Mapped[Optional[str]]=mapped_column(String(500),nullable=True)
    referer:Mapped[Optional[str]]=mapped_column(String(1000),nullable=True)
    source:Mapped[Optional[str]]=mapped_column(String(120),nullable=True)
    medium:Mapped[Optional[str]]=mapped_column(String(120),nullable=True)
    campaign:Mapped[Optional[str]]=mapped_column(String(200),nullable=True)
    term:Mapped[Optional[str]]=mapped_column(String(200),nullable=True)
    content:Mapped[Optional[str]]=mapped_column(String(200),nullable=True)


class UserSession(Base):
    __tablename__="security_sessions"
    id:Mapped[int]=mapped_column(primary_key=True)
    session_id:Mapped[str]=mapped_column(String(64),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    visitor_id:Mapped[Optional[int]]=mapped_column(ForeignKey("security_visitors.id"),nullable=True,index=True)
    current_jti:Mapped[str]=mapped_column(String(100),unique=True,index=True)
    status:Mapped[str]=mapped_column(String(20),default="active",index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    last_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
    ended_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    end_reason:Mapped[Optional[str]]=mapped_column(String(120),nullable=True)
    ip:Mapped[Optional[str]]=mapped_column(String(128),nullable=True,index=True)
    ip_type:Mapped[Optional[str]]=mapped_column(String(10),nullable=True)
    user_agent:Mapped[Optional[str]]=mapped_column(Text,nullable=True)
    referer:Mapped[Optional[str]]=mapped_column(String(1000),nullable=True)
    accept_language:Mapped[Optional[str]]=mapped_column(String(255),nullable=True)
    sec_ch_ua:Mapped[Optional[str]]=mapped_column(String(1000),nullable=True)
    sec_ch_mobile:Mapped[Optional[str]]=mapped_column(String(40),nullable=True)
    sec_ch_platform:Mapped[Optional[str]]=mapped_column(String(100),nullable=True
    )


class DeviceProfile(Base):
    __tablename__="security_devices"
    id:Mapped[int]=mapped_column(primary_key=True)
    device_id:Mapped[str]=mapped_column(String(64),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    user_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    visitor_id:Mapped[Optional[int]]=mapped_column(ForeignKey("security_visitors.id"),nullable=True,index=True)
    user_agent:Mapped[Optional[str]]=mapped_column(Text,nullable=True)
    browser:Mapped[Optional[str]]=mapped_column(String(80),nullable=True)
    browser_version:Mapped[Optional[str]]=mapped_column(String(40),nullable=True)
    os:Mapped[Optional[str]]=mapped_column(String(80),nullable=True)
    platform:Mapped[Optional[str]]=mapped_column(String(80),nullable=True)
    device_model:Mapped[Optional[str]]=mapped_column(String(120),nullable=True)
    language:Mapped[Optional[str]]=mapped_column(String(80),nullable=True)
    timezone:Mapped[Optional[str]]=mapped_column(String(100),nullable=True)
    screen_width:Mapped[Optional[int]]=mapped_column(Integer,nullable=True)
    screen_height:Mapped[Optional[int]]=mapped_column(Integer,nullable=True)
    pixel_ratio:Mapped[Optional[str]]=mapped_column(String(20),nullable=True)
    touch_support:Mapped[Optional[bool]]=mapped_column(Boolean,nullable=True)
    first_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    last_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)


class ConnectionLog(Base):
    __tablename__="security_connections"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    session_id:Mapped[Optional[int]]=mapped_column(ForeignKey("security_sessions.id"),nullable=True,index=True)
    visitor_id:Mapped[Optional[int]]=mapped_column(ForeignKey("security_visitors.id"),nullable=True,index=True)
    ip:Mapped[str]=mapped_column(String(128),index=True)
    ip_type:Mapped[Optional[str]]=mapped_column(String(10),nullable=True)
    isp:Mapped[Optional[str]]=mapped_column(String(255),nullable=True)
    organization:Mapped[Optional[str]]=mapped_column(String(255),nullable=True)
    asn:Mapped[Optional[str]]=mapped_column(String(80),nullable=True)
    country:Mapped[Optional[str]]=mapped_column(String(100),nullable=True)
    region:Mapped[Optional[str]]=mapped_column(String(150),nullable=True)
    city:Mapped[Optional[str]]=mapped_column(String(150),nullable=True)
    timezone:Mapped[Optional[str]]=mapped_column(String(100),nullable=True)
    ipinfo_json:Mapped[str]=mapped_column(Text,default="{}")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)


class ActivityLog(Base):
    __tablename__="security_activity_logs"
    id:Mapped[int]=mapped_column(primary_key=True)
    activity_id:Mapped[str]=mapped_column(String(32),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    user_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    session_id:Mapped[Optional[int]]=mapped_column(ForeignKey("security_sessions.id"),nullable=True,index=True)
    visitor_id:Mapped[Optional[int]]=mapped_column(ForeignKey("security_visitors.id"),nullable=True,index=True)
    event_type:Mapped[str]=mapped_column(String(60),index=True)
    method:Mapped[Optional[str]]=mapped_column(String(10),nullable=True)
    path:Mapped[Optional[str]]=mapped_column(String(500),nullable=True)
    ip:Mapped[Optional[str]]=mapped_column(String(128),nullable=True,index=True)
    user_agent:Mapped[Optional[str]]=mapped_column(Text,nullable=True)
    metadata_json:Mapped[str]=mapped_column(Text,default="{}")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)


class SecurityAccount(Base):
    __tablename__="security_accounts"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),unique=True,index=True)
    status:Mapped[str]=mapped_column(String(20),default="active",index=True)
    reason:Mapped[Optional[str]]=mapped_column(String(500),nullable=True)
    suspended_until:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    risk_score:Mapped[int]=mapped_column(Integer,default=0)
    flagged:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)


class PermissionState(Base):
    __tablename__="security_permissions"
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    permission:Mapped[str]=mapped_column(String(30),index=True)
    state:Mapped[str]=mapped_column(String(20),default="unknown")
    request_id:Mapped[str]=mapped_column(String(64),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    requested_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    resolved_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
    value_json:Mapped[str]=mapped_column(Text,default="{}")
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
    __table_args__=(UniqueConstraint("user_id","permission",name="uq_security_permission_user"),)


class SecurityAction(Base):
    __tablename__="security_actions"
    id:Mapped[int]=mapped_column(primary_key=True)
    action_id:Mapped[str]=mapped_column(String(32),unique=True,index=True,default=lambda:uuid.uuid4().hex)
    admin_user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    target_user_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    target_session_id:Mapped[Optional[int]]=mapped_column(ForeignKey("security_sessions.id"),nullable=True,index=True)
    action:Mapped[str]=mapped_column(String(40),index=True)
    reason:Mapped[Optional[str]]=mapped_column(String(500),nullable=True)
    metadata_json:Mapped[str]=mapped_column(Text,default="{}")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
