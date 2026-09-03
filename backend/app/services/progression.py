from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models import User, TournamentResult, Tournament, Achievement, UserAchievement, Notification
from app.services.economy import get_economy_config

DEFAULT_ACHIEVEMENTS = [
    ("first_tournament", "Primeira Arena", "Participou do primeiro torneio.", 50, 25),
    ("first_win", "Primeira Vitória", "Venceu o primeiro duelo.", 100, 50),
    ("first_title", "Primeiro Título", "Foi campeão de um torneio.", 250, 100),
    ("five_wins", "Cinco Vitórias", "Alcançou cinco vitórias em torneios.", 250, 150),
    ("ten_matches", "10 Duelos", "Participou de dez duelos.", 150, 100),
    ("twenty_five_matches", "25 Duelos", "Participou de vinte e cinco duelos.", 300, 200),
    ("fifty_wins", "50 Vitórias", "Alcançou cinquenta vitórias.", 500, 300),
    ("ten_titles", "Lenda da Arena", "Conquistou dez títulos.", 1000, 500),
]

def ensure_achievements(db: Session):
    for code,name,desc,xp,pts in DEFAULT_ACHIEVEMENTS:
        if not db.scalar(select(Achievement).where(Achievement.code==code)):
            db.add(Achievement(code=code,name=name,description=desc,xp_reward=xp,points_reward=pts,active=True))
    db.commit()

def notify(db,user_id,title,message,kind="system",tournament_id=None,match_id=None):
    db.add(Notification(user_id=user_id,title=title,message=message,kind=kind,tournament_id=tournament_id,match_id=match_id))

def _award(db,user,code):
    ach=db.scalar(select(Achievement).where(Achievement.code==code,Achievement.active.is_(True)))
    if not ach or db.scalar(select(UserAchievement).where(UserAchievement.user_id==user.id,UserAchievement.achievement_id==ach.id)):
        return False
    user.xp += ach.xp_reward
    user.points += ach.points_reward
    user.level = 1 + user.xp//int(get_economy_config()["progresso"]["xp_por_nivel"])
    db.add(UserAchievement(user_id=user.id,achievement_id=ach.id))
    notify(db,user.id,f"🏆 {ach.name}",f"{ach.description} +{ach.xp_reward} XP e +{ach.points_reward} pontos.","achievement")
    return True

def evaluate_user(db,user_id):
    user=db.get(User,user_id)
    if not user: return
    participations=db.scalar(select(func.count(TournamentResult.id)).where(TournamentResult.user_id==user_id)) or 0
    wins=db.scalar(select(func.count(TournamentResult.id)).where(TournamentResult.user_id==user_id,TournamentResult.position==1)) or 0
    # A result row represents participation. Titles are position 1.
    from app.models import TournamentMatch
    matches=db.scalar(select(func.count(TournamentMatch.id)).where(((TournamentMatch.player1_id==user_id)|(TournamentMatch.player2_id==user_id)), TournamentMatch.status=="finished")) or 0
    if participations>=1: _award(db,user,"first_tournament")
    if wins>=1: _award(db,user,"first_win")
    if wins>=1: _award(db,user,"first_title")
    if wins>=5: _award(db,user,"five_wins")
    if matches>=10: _award(db,user,"ten_matches")
    if matches>=25: _award(db,user,"twenty_five_matches")
    if wins>=50: _award(db,user,"fifty_wins")
    if wins>=10: _award(db,user,"ten_titles")

def seed_and_evaluate(db):
    ensure_achievements(db)
    for u in db.scalars(select(User).where(User.is_active.is_(True))).all():
        evaluate_user(db,u.id)
    db.commit()
