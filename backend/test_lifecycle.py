import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models import User, Tournament, TournamentEntry, TournamentMatch
from app.services.tournaments import process_tournament, now
from app.schemas.auth import RegisterIn


def make_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'lifecycle.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def make_tournament(db, max_players=4):
    users=[]
    for i in range(max_players):
        u=User(email=f"u{i}@test.local", username=f"u{i}", password_hash="x")
        db.add(u); users.append(u)
    db.flush()
    rules={
        "participants":{"minimum":2,"maximum":max_players},
        "timing":{"registration_minutes":15,"start_delay_after_full_minutes":5,"duel_minutes":6},
        "start_delay_after_full_minutes":5,"duel_minutes":6,
        "prize_pool":100,"prize_first":50,"prize_second":35,"organizer_percent":10,"system_percent":5,
        "card":{"tema_id":"cidades","tema_nome":"Cidades","opcoes_disponiveis":["A","B","C","D"],"quantidade_opcoes":2},
        "duel":{"quantidade_respostas":2},
    }
    t=Tournament(title="Teste",category="perfil",mode="free",entry_fee=0,max_players=max_players,prize_pool=100,
                 registration_deadline=now()+timedelta(minutes=15),starts_at=now()+timedelta(minutes=15),
                 rules_json=json.dumps(rules),created_by=users[0].id)
    db.add(t); db.flush()
    for u in users:
        db.add(TournamentEntry(tournament_id=t.id,user_id=u.id,fee_paid=0,status="confirmed"))
    db.commit(); db.refresh(t)
    return t


def test_full_tournament_countdown_is_set_once_and_then_starts(tmp_path):
    db=make_db(tmp_path)
    t=make_tournament(db,4)

    assert process_tournament(db,t) is True
    db.refresh(t)
    first_start=t.starts_at
    rules=json.loads(t.rules_json)
    assert rules["runtime"]["phase"] == "waiting_start"
    assert (first_start.replace(tzinfo=timezone.utc)-now()).total_seconds() <= 300
    assert (first_start.replace(tzinfo=timezone.utc)-now()).total_seconds() > 295

    # Reconcile again during the five-minute window: it must not reset the timer.
    process_tournament(db,t)
    db.refresh(t)
    assert t.starts_at == first_start
    assert t.status == "open"

    # Simulate the five minutes having elapsed.
    t.starts_at=now()-timedelta(seconds=1)
    db.commit()
    assert process_tournament(db,t) is True
    db.refresh(t)
    assert t.status == "live"
    assert db.scalar(select(TournamentMatch.id).where(TournamentMatch.tournament_id==t.id)) is not None
    db.close()


def test_registration_password_minimum_is_six():
    RegisterIn(email="x@example.com", username="tester", password="123456")
    try:
        RegisterIn(email="x2@example.com", username="tester2", password="12345")
    except Exception:
        return
    raise AssertionError("Senha com 5 caracteres deveria ser rejeitada")

from app.services.tournaments import create_card, join_tournament, submit_guess, settle_tournament
from app.models import Payment, LedgerTransaction, TournamentCard, TournamentGuess


def test_paid_tournament_debits_pool_pays_and_closes_ledger(tmp_path):
    db=make_db(tmp_path)
    admin=User(email="admin@example.com", username="adminpay", password_hash="x", role="admin", balance=0)
    db.add(admin)
    players=[]
    for i in range(4):
        u=User(email=f"p{i}@example.com", username=f"p{i}", password_hash="x", balance=20)
        db.add(u); players.append(u)
    db.flush()
    rules={
        "participants":{"minimum":2,"maximum":4},"timing":{"registration_minutes":15,"start_delay_after_full_minutes":5,"duel_minutes":6},
        "start_delay_after_full_minutes":5,"duel_minutes":6,"prize_pool":0,"prize_first":50,"prize_second":35,"organizer_percent":10,"system_percent":5,
        "card":{"tema_id":"cidades","tema_nome":"Cidades","opcoes_disponiveis":["A","B","C","D"],"quantidade_opcoes":2},"duel":{"quantidade_respostas":2},
    }
    t=Tournament(title="Pago",category="perfil",mode="paid",entry_fee=20,max_players=4,prize_pool=80,
                 registration_deadline=now()+timedelta(minutes=15),starts_at=now()+timedelta(minutes=15),rules_json=json.dumps(rules),created_by=admin.id)
    db.add(t); db.flush()
    db.commit()
    for i,u in enumerate(players):
        card=create_card(db,u.id,t.public_id,["A","B"] if i%2==0 else ["C","D"])
        join_tournament(db,u.id,t.public_id,card.card_id)
    for u in players: db.refresh(u)
    assert [u.balance for u in players]==[0,0,0,0]
    assert t.prize_pool==80
    payments=[]
    # Payment pool is settled from the four real entry debits.
    settle_tournament(db,t,[(1,players[0].id),(2,players[1].id),(3,players[2].id),(4,players[3].id)])
    db.refresh(t); db.refresh(admin)
    for u in players: db.refresh(u)
    assert t.status=="finished"
    assert [u.balance for u in players]==[40,28,0,0]
    assert admin.balance==8
    payments=list(db.scalars(select(Payment).where(Payment.tournament_id==t.id)).all())
    assert sum(p.amount for p in payments)==80
    assert sorted((p.beneficiary_type,p.amount) for p in payments)==sorted([
        ("winner",40),("winner",28),("organizer",8),("system",4)
    ])
    txs=list(db.scalars(select(LedgerTransaction).where(LedgerTransaction.tournament_id==t.id)).all())
    # Player entry debits are -80; winner/organizer credits are +76, while the
    # 5% system fee is recorded separately in the platform ledger.
    assert sum(x.amount for x in txs)==-4
    from app.models import PlatformLedgerTransaction
    platform=list(db.scalars(select(PlatformLedgerTransaction).where(PlatformLedgerTransaction.tournament_id==t.id)).all())
    assert sum(x.amount for x in platform)==4
    assert all(c.status=="finalized" for c in db.scalars(select(TournamentCard).where(TournamentCard.tournament_id==t.id)).all())
    db.close()


def test_card_duel_correct_guess_finishes_match(tmp_path):
    db=make_db(tmp_path)
    users=[]
    for i in range(2):
        u=User(email=f"duel{i}@example.com", username=f"duel{i}", password_hash="x")
        db.add(u); users.append(u)
    db.flush()
    rules={
        "participants":{"minimum":2,"maximum":2},"timing":{"registration_minutes":15,"start_delay_after_full_minutes":0,"duel_minutes":6},
        "start_delay_after_full_minutes":0,"duel_minutes":6,"prize_pool":100,"prize_first":50,"prize_second":35,"organizer_percent":10,"system_percent":5,
        "card":{"tema_id":"cidades","tema_nome":"Cidades","opcoes_disponiveis":["A","B","C","D"],"quantidade_opcoes":2},"duel":{"quantidade_respostas":2},
    }
    t=Tournament(title="Duelo",category="perfil",mode="free",entry_fee=0,max_players=2,prize_pool=100,
                 registration_deadline=now()+timedelta(minutes=15),starts_at=now()+timedelta(minutes=15),rules_json=json.dumps(rules),created_by=users[0].id)
    db.add(t); db.flush(); db.commit()
    c1=create_card(db,users[0].id,t.public_id,["A","B"])
    c2=create_card(db,users[1].id,t.public_id,["C","D"])
    join_tournament(db,users[0].id,t.public_id,c1.card_id)
    join_tournament(db,users[1].id,t.public_id,c2.card_id)
    t.starts_at=now()-timedelta(seconds=1); db.commit()
    process_tournament(db,t)
    m=db.scalar(select(TournamentMatch).where(TournamentMatch.tournament_id==t.id))
    assert m is not None and m.status=="pending"
    # Find which player is attacking and guess an option from the opponent card.
    attacker=m.player1_id
    opponent=m.player2_id
    opponent_card=db.scalar(select(TournamentCard).where(TournamentCard.user_id==opponent,TournamentCard.tournament_id==t.id))
    correct=json.loads(opponent_card.selected_options_json)
    submit_guess(db,attacker,m.match_id,correct[0])
    db.refresh(m); db.refresh(t)
    assert m.status=="pending"
    submit_guess(db,attacker,m.match_id,correct[1])
    db.refresh(m); db.refresh(t)
    assert m.status=="finished"
    assert m.winner_id==attacker
    assert db.scalar(select(TournamentGuess).where(TournamentGuess.match_id==m.id)) is not None
    assert t.status=="finished"
    db.close()


def test_draw_creates_replay_and_notifies_players(tmp_path):
    db=make_db(tmp_path)
    users=[]
    for i in range(2):
        u=User(email=f"replay{i}@test.local", username=f"replay{i}", password_hash="x")
        db.add(u); users.append(u)
    db.flush()
    rules={"participants":{"minimum":2,"maximum":2},"timing":{"registration_minutes":15,"start_delay_after_full_minutes":0,"duel_minutes":6},
           "start_delay_after_full_minutes":0,"duel_minutes":6,"prize_pool":100,"prize_first":50,"prize_second":35,"organizer_percent":10,"system_percent":5,
           "card":{"tema_id":"cidades","tema_nome":"Cidades","opcoes_disponiveis":["A","B","C","D"],"quantidade_opcoes":2},"duel":{"quantidade_respostas":2}}
    t=Tournament(title="Replay",category="perfil",mode="free",entry_fee=0,max_players=2,prize_pool=100,
                 registration_deadline=now()+timedelta(minutes=15),starts_at=now()+timedelta(minutes=15),rules_json=json.dumps(rules),created_by=users[0].id)
    db.add(t); db.flush()
    from app.services.tournaments import create_card, join_tournament, submit_guess
    cards=[create_card(db,users[0].id,t.public_id,["A","B"]),create_card(db,users[1].id,t.public_id,["C","D"]) ]
    for u,c in zip(users,cards): join_tournament(db,u.id,t.public_id,c.card_id)
    t.starts_at=now()-timedelta(seconds=1); db.commit(); process_tournament(db,t)
    m=db.scalar(select(TournamentMatch).where(TournamentMatch.tournament_id==t.id))
    # Each player misses both attempts. The second-to-last attempt leaves the match pending; the final one creates replay.
    submit_guess(db,m.player1_id,m.match_id,"C"); submit_guess(db,m.player1_id,m.match_id,"D")
    submit_guess(db,m.player2_id,m.match_id,"A"); submit_guess(db,m.player2_id,m.match_id,"B")
    db.refresh(m)
    assert m.status=="pending" and m.replay_number==1 and m.result_reason=="replay_empate"
    assert db.scalar(select(TournamentGuess).where(TournamentGuess.match_id==m.id)) is None
    from app.models import Notification
    notes=list(db.scalars(select(Notification).where(Notification.tournament_id==t.id,Notification.kind=="match_replay")).all())
    assert len(notes)==2
    db.close()


def test_loss_marks_player_eliminated_and_winner_advanced(tmp_path):
    db=make_db(tmp_path)
    users=[]
    for i in range(2):
        u=User(email=f"result{i}@test.local", username=f"result{i}", password_hash="x")
        db.add(u); users.append(u)
    db.flush()
    rules={"participants":{"minimum":2,"maximum":2},"timing":{"registration_minutes":15,"start_delay_after_full_minutes":0,"duel_minutes":6},
           "start_delay_after_full_minutes":0,"duel_minutes":6,"prize_pool":100,"prize_first":50,"prize_second":35,"organizer_percent":10,"system_percent":5,
           "card":{"tema_id":"cidades","tema_nome":"Cidades","opcoes_disponiveis":["A","B","C","D"],"quantidade_opcoes":2},"duel":{"quantidade_respostas":2}}
    t=Tournament(title="Resultado",category="perfil",mode="free",entry_fee=0,max_players=2,prize_pool=100,
                 registration_deadline=now()+timedelta(minutes=15),starts_at=now()+timedelta(minutes=15),rules_json=json.dumps(rules),created_by=users[0].id)
    db.add(t); db.flush()
    from app.services.tournaments import create_card, join_tournament, submit_guess
    cards=[create_card(db,users[0].id,t.public_id,["A","B"]),create_card(db,users[1].id,t.public_id,["C","D"]) ]
    for u,c in zip(users,cards): join_tournament(db,u.id,t.public_id,c.card_id)
    t.starts_at=now()-timedelta(seconds=1); db.commit(); process_tournament(db,t)
    m=db.scalar(select(TournamentMatch).where(TournamentMatch.tournament_id==t.id))
    winner=m.player1_id; loser=m.player2_id
    # Winner discovers the entire opponent card; this immediately resolves the duel.
    submit_guess(db,winner,m.match_id,"C"); submit_guess(db,winner,m.match_id,"D")
    db.refresh(m)
    assert m.status=="finished" and m.winner_id==winner
    from app.models import Notification
    assert db.scalar(select(Notification).where(Notification.user_id==loser,Notification.kind=="match_eliminated")) is not None
    assert db.scalar(select(Notification).where(Notification.user_id==winner,Notification.kind=="match_advanced")) is not None
    db.close()
