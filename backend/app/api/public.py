from typing import Optional
from fastapi import APIRouter, Query, Depends
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import Season, Tournament, TournamentEntry, TournamentResult, User
from app.services.tournaments import list_tournaments, _rules, _aware
from app.services.competitive import ranking as competitive_ranking, ensure_season

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/tournaments")
def public_tournaments(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = list_tournaments(db, None, status)[:limit]
    items = []
    for t in rows:
        count = int(
            db.scalar(
                select(func.count(TournamentEntry.id)).where(
                    TournamentEntry.tournament_id == t.id,
                    TournamentEntry.status == "confirmed",
                )
            )
            or 0
        )
        rules = _rules(t)
        items.append(
            {
                "public_id": t.public_id,
                "title": t.title,
                "category": t.category,
                "category_label": str(t.category).replace("_", " ").title(),
                "mode": t.mode,
                "status": t.status,
                "max_players": t.max_players,
                "participant_count": count,
                "prize_pool": t.prize_pool,
                "entry_fee": t.entry_fee,
                "registration_deadline": _aware(t.registration_deadline),
                "starts_at": _aware(t.starts_at),
                "rules": {
                    "card": rules.get("card", {}),
                    "participants": rules.get("participants", {}),
                },
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/ranking")
def public_ranking(
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    # Never expose private account/economy fields through a public endpoint.
    rows = competitive_ranking(db, limit, False)
    return [
        {
            "position": item["position"],
            "user_id": item["user_id"],
            "username": item["username"],
            "points": item["points"],
            "xp": item["xp"],
            "level": item["level"],
        }
        for item in rows
    ]


@router.get("/results")
def public_results(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(TournamentResult)
        .order_by(TournamentResult.id.desc())
        .limit(limit)
    ).all()
    tids = list({r.tournament_id for r in rows})
    uids = list({r.user_id for r in rows})
    names = (
        {
            t.id: t.title
            for t in db.scalars(
                select(Tournament).where(Tournament.id.in_(tids))
            ).all()
        }
        if tids
        else {}
    )
    users = (
        {
            u.id: u.username
            for u in db.scalars(select(User).where(User.id.in_(uids))).all()
        }
        if uids
        else {}
    )
    return [
        {
            "tournament_id": r.tournament_id,
            "title": names.get(r.tournament_id, "Torneio"),
            "position": r.position,
            "username": users.get(r.user_id, "Jogador"),
            "points": r.points_earned,
            "xp": r.xp_earned,
        }
        for r in rows
    ]


@router.get("/players")
def public_players(
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    users = db.scalars(
        select(User)
        .where(User.is_active.is_(True))
        .order_by(User.points.desc(), User.xp.desc(), User.created_at.asc())
        .limit(limit)
    ).all()
    return [
        {
            "user_id": u.id,
            "username": u.username,
            "points": int(u.points or 0),
            "xp": int(u.xp or 0),
            "level": int(u.level or 1),
        }
        for u in users
    ]


@router.get("/seasons")
def public_seasons(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    ensure_season(db)
    seasons = db.scalars(
        select(Season)
        .order_by(Season.starts_at.desc(), Season.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "public_id": s.public_id,
            "name": s.name,
            "starts_at": _aware(s.starts_at),
            "ends_at": _aware(s.ends_at),
            "active": bool(s.active),
        }
        for s in seasons
    ]


@router.get("/health", include_in_schema=False)
def public_health():
    return {"status": "ok"}
