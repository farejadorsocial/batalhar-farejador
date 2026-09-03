from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, Notification, Achievement, UserAchievement, TournamentResult, LedgerTransaction, Tournament
from app.services.competitive import player_matches, player_stats, player_progression, ranking as competitive_ranking, ensure_season

router=APIRouter(prefix="/player",tags=["player"])

@router.get("/profile")
def profile(db:Session=Depends(get_db), user=Depends(get_current_user)):
    wins=db.scalar(select(func.count(TournamentResult.id)).where(TournamentResult.user_id==user.id,TournamentResult.position==1)) or 0
    tournaments=db.scalar(select(func.count(TournamentResult.id)).where(TournamentResult.user_id==user.id)) or 0
    unread=db.scalar(select(func.count(Notification.id)).where(Notification.user_id==user.id,Notification.is_read.is_(False))) or 0
    return {"id":user.id,"username":user.username,"created_at":user.created_at,"balance":user.balance,"xp":user.xp,"points":user.points,"level":user.level,"stats":{"tournaments":tournaments,"titles":wins,"unread_notifications":unread}}

@router.get("/ranking")
def ranking(limit:int=20, season:bool=False, db:Session=Depends(get_db), user=Depends(get_current_user)):
    limit=max(1,min(limit,100))
    return competitive_ranking(db,limit,season)

@router.get("/progression")
def progression(db:Session=Depends(get_db), user=Depends(get_current_user)):
    return player_progression(db,user.id)

@router.get("/stats")
def stats(db:Session=Depends(get_db), user=Depends(get_current_user)):
    return player_stats(db,user.id)

@router.get("/matches")
def matches(limit:int=50, db:Session=Depends(get_db), user=Depends(get_current_user)):
    return player_matches(db,user.id,limit)

@router.get("/season")
def season(db:Session=Depends(get_db), user=Depends(get_current_user)):
    s=ensure_season(db)
    return {"public_id":s.public_id,"name":s.name,"starts_at":s.starts_at,"ends_at":s.ends_at,"active":s.active}

@router.get("/notifications")
def notifications(unread_only:bool=False,db:Session=Depends(get_db),user=Depends(get_current_user)):
    q=select(Notification).where(Notification.user_id==user.id).order_by(Notification.created_at.desc()).limit(100)
    if unread_only:q=q.where(Notification.is_read.is_(False))
    rows=db.scalars(q).all()
    return [{"notification_id":n.notification_id,"kind":n.kind,"title":n.title,"message":n.message,"tournament_id":n.tournament_id,"match_id":n.match_id,"is_read":n.is_read,"created_at":n.created_at} for n in rows]

@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id:str,db:Session=Depends(get_db),user=Depends(get_current_user)):
    n=db.scalar(select(Notification).where(Notification.notification_id==notification_id,Notification.user_id==user.id))
    if n:
        n.is_read=True; db.commit()
    return {"ok":True}

@router.post("/notifications/read-all")
def read_all(db:Session=Depends(get_db),user=Depends(get_current_user)):
    rows=db.scalars(select(Notification).where(Notification.user_id==user.id,Notification.is_read.is_(False))).all()
    for n in rows:n.is_read=True
    db.commit()
    return {"ok":True,"count":len(rows)}

@router.get("/achievements")
def achievements(db:Session=Depends(get_db),user=Depends(get_current_user)):
    all_=db.scalars(select(Achievement).where(Achievement.active.is_(True)).order_by(Achievement.id)).all()
    owned={x.achievement_id for x in db.scalars(select(UserAchievement).where(UserAchievement.user_id==user.id)).all()}
    return [{"code":a.code,"name":a.name,"description":a.description,"xp_reward":a.xp_reward,"points_reward":a.points_reward,"unlocked":a.id in owned} for a in all_]

@router.get("/history")
def history(limit:int=50,db:Session=Depends(get_db),user=Depends(get_current_user)):
    limit=max(1,min(limit,100))
    results=db.scalars(select(TournamentResult).where(TournamentResult.user_id==user.id).order_by(TournamentResult.id.desc()).limit(limit)).all()
    tids=[r.tournament_id for r in results]
    names={}
    if tids:
        names={t.id:t.title for t in db.scalars(select(Tournament).where(Tournament.id.in_(tids))).all()}
    return [{"tournament_id":r.tournament_id,"title":names.get(r.tournament_id),"position":r.position,"points":r.points_earned,"xp":r.xp_earned} for r in results]
