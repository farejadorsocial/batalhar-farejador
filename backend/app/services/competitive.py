import json
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models import User, Tournament, TournamentResult, TournamentMatch, TournamentEvent, Season, Achievement, UserAchievement, EconomyMarket, EconomyState

def now():
    return datetime.now(timezone.utc)

def _aware(dt):
    """Normaliza datetimes vindos do SQLite (que pode devolvê-los sem timezone)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def active_season(db: Session):
    s = db.scalar(select(Season).where(Season.active.is_(True)).order_by(Season.id.desc()))
    if not s:
        return None

    starts_at = _aware(s.starts_at)
    ends_at = _aware(s.ends_at)
    current = now()

    if starts_at <= current <= ends_at:
        return s

    return None

def ensure_season(db: Session):
    s = active_season(db)
    if s:
        return s
    # A default long-lived season keeps the competitive layer usable immediately.
    from datetime import timedelta
    start = now()
    s = Season(name=f"Temporada {start.year}-{start.month:02d}", starts_at=start,
               ends_at=start + timedelta(days=90), active=True)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

def log_event(db: Session, tournament_id: int, event_type: str, actor_user_id=None, match_id=None, payload=None):
    e = TournamentEvent(tournament_id=tournament_id, event_type=event_type,
                        actor_user_id=actor_user_id, match_id=match_id,
                        payload_json=json.dumps(payload or {}, ensure_ascii=False, default=str))
    db.add(e)
    return e

def tournament_events(db: Session, tournament_id: int, limit=100):
    rows = db.scalars(select(TournamentEvent).where(TournamentEvent.tournament_id==tournament_id)
                      .order_by(TournamentEvent.id.desc()).limit(max(1,min(limit,200)))).all()
    out=[]
    for e in reversed(rows):
        try: payload=json.loads(e.payload_json or "{}")
        except Exception: payload={}
        out.append({"event_id":e.event_id,"type":e.event_type,"actor_user_id":e.actor_user_id,
                    "match_id":e.match_id,"payload":payload,"created_at":e.created_at})
    return out

def player_matches(db: Session, user_id: int, limit=100):
    q = select(TournamentMatch).where(
        (TournamentMatch.player1_id==user_id) | (TournamentMatch.player2_id==user_id)
    ).order_by(TournamentMatch.id.desc()).limit(max(1,min(limit,100)))
    rows=db.scalars(q).all()
    tids=list({m.tournament_id for m in rows})
    trows=db.scalars(select(Tournament).where(Tournament.id.in_(tids))).all() if tids else []
    names={t.id:t.title for t in trows}; public_ids={t.id:t.public_id for t in trows}
    users={u.id:u.username for u in db.scalars(select(User).where(User.id.in_(
        {x for m in rows for x in (m.player1_id,m.player2_id) if x}
    ))).all()} if rows else {}
    out=[]
    for m in rows:
        opponent=m.player2_id if m.player1_id==user_id else m.player1_id
        if m.status=="finished":
            if m.winner_id==user_id: result="win"
            elif m.winner_id is None: result="draw"
            else: result="loss"
        else: result="pending"
        out.append({"match_id":m.match_id,"tournament_id":m.tournament_id,"tournament_public_id":public_ids.get(m.tournament_id),"tournament_title":names.get(m.tournament_id),
                    "round":m.round_number,"replay":m.replay_number,"opponent_id":opponent,
                    "opponent":users.get(opponent),"status":m.status,"result":result,
                    "winner_id":m.winner_id,"started_at":m.started_at,"deadline":m.deadline,"finished_at":m.finished_at,
                    "result_reason":m.result_reason,"is_my_turn":(
                        m.status=="pending" and
                        ((m.player1_id==user_id and m.player1_guess is None) or
                         (m.player2_id==user_id and m.player2_guess is None))
                    )})
    return out

def player_stats(db: Session, user_id: int):
    total=db.scalar(select(func.count(TournamentMatch.id)).where(
        ((TournamentMatch.player1_id==user_id)|(TournamentMatch.player2_id==user_id)),
        TournamentMatch.status=="finished")) or 0
    wins=db.scalar(select(func.count(TournamentMatch.id)).where(
        TournamentMatch.winner_id==user_id,TournamentMatch.status=="finished")) or 0
    draws=db.scalar(select(func.count(TournamentMatch.id)).where(
        ((TournamentMatch.player1_id==user_id)|(TournamentMatch.player2_id==user_id)),
        TournamentMatch.status=="finished",TournamentMatch.winner_id.is_(None))) or 0
    losses=max(0,total-wins-draws)
    titles=db.scalar(select(func.count(TournamentResult.id)).where(
        TournamentResult.user_id==user_id,TournamentResult.position==1)) or 0
    return {"matches":total,"wins":wins,"losses":losses,"draws":draws,"win_rate":round(wins/total*100,1) if total else 0,"titles":titles}

def ranking(db: Session, limit=100, season_only=False):
    # Season-aware points are computed from results created in the current active season
    # when season_only is requested. TournamentResult intentionally remains immutable.
    season=ensure_season(db) if season_only else None
    users=db.scalars(select(User).where(User.is_active.is_(True))).all()
    scores=[]
    for u in users:
        if season:
            tids=[t.id for t in db.scalars(select(Tournament).where(Tournament.created_at>=season.starts_at,Tournament.created_at<=season.ends_at)).all()]
            pts=sum(r.points_earned for r in db.scalars(select(TournamentResult).where(
                TournamentResult.user_id==u.id, TournamentResult.tournament_id.in_(tids)
            )).all()) if tids else 0
        else: pts=u.points
        scores.append((u,pts))
    scores.sort(key=lambda x:(-x[1],-x[0].xp,x[0].created_at,x[0].id))
    return [{"position":i+1,"user_id":u.id,"username":u.username,"points":pts,"xp":u.xp,"level":u.level,
             "balance":u.balance} for i,(u,pts) in enumerate(scores[:max(1,min(limit,100))])]

def ensure_market(db: Session):
    m=db.scalar(select(EconomyMarket).where(EconomyMarket.name=="farejador"))
    if not m:
        state=db.scalar(select(EconomyState).order_by(EconomyState.id.asc()))
        base=state.xp_rate if state else 1000
        m=EconomyMarket(name="farejador",base_xp_rate=base,min_xp_rate=base,max_xp_rate=1000000,dynamic_pricing_enabled=False)
        db.add(m); db.commit(); db.refresh(m)
    return m

def market_quote(db: Session):
    m=ensure_market(db)
    # Dynamic pricing is deliberately disabled until a real exchange/order system exists.
    return {"asset":"farejador","dynamic_pricing_enabled":m.dynamic_pricing_enabled,
            "xp_per_farejador":m.base_xp_rate if not m.dynamic_pricing_enabled else max(m.min_xp_rate,min(m.max_xp_rate,
                int(m.base_xp_rate*(1+(m.buy_pressure-m.sell_pressure)/1000)))),
            "buy_pressure":m.buy_pressure,"sell_pressure":m.sell_pressure,
            "status":"fixed" if not m.dynamic_pricing_enabled else "dynamic"}


def player_progression(db: Session, user_id: int):
    """Resumo derivado da carreira do jogador, sem armazenar estado duplicado."""
    rows=list(db.scalars(select(TournamentMatch).where(
        ((TournamentMatch.player1_id==user_id)|(TournamentMatch.player2_id==user_id)),
        TournamentMatch.status=="finished"
    ).order_by(TournamentMatch.finished_at.desc(), TournamentMatch.id.desc())).all())

    current_streak=0
    for m in rows:
        if m.winner_id != user_id:
            break
        current_streak += 1
    best_streak=0
    running=0
    for m in rows:
        if m.winner_id == user_id:
            running += 1
            best_streak=max(best_streak,running)
        else:
            running=0

    wins=sum(1 for m in rows if m.winner_id==user_id)
    losses=sum(1 for m in rows if m.winner_id is not None and m.winner_id!=user_id)
    draws=sum(1 for m in rows if m.winner_id is None)
    user=db.get(User,user_id)
    xp=int(user.xp or 0) if user else 0
    level=int(user.level or 1) if user else 1
    current_xp=xp%100
    unlocked=db.scalar(select(func.count(UserAchievement.id)).where(UserAchievement.user_id==user_id)) or 0
    total_achievements=db.scalar(select(func.count(Achievement.id)).where(Achievement.active.is_(True))) or 0
    return {
        "user_id":user_id,
        "level":level,
        "xp":xp,
        "current_xp":current_xp,
        "xp_to_next":100-current_xp if current_xp else 100,
        "current_streak":current_streak,
        "best_streak":best_streak,
        "wins":wins,
        "losses":losses,
        "draws":draws,
        "matches":len(rows),
        "win_rate":round(wins/len(rows)*100,1) if rows else 0,
        "achievements_unlocked":int(unlocked),
        "achievements_total":int(total_achievements),
    }
