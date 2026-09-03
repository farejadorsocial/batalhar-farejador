from datetime import datetime, timezone, timedelta
import json, random
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from app.models import (
    Tournament, TournamentEntry, TournamentResult, Payment, User, TournamentMatch,
    PlatformLedgerTransaction, TournamentCard, TournamentGuess,
)
from .economy import change_balance, get_economy_config
from .progression import notify, evaluate_user
from .competitive import log_event

def now(): return datetime.now(timezone.utc)
def _aware(dt): return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "torneios"
CONFIG_FILE = CONFIG_DIR / "torneios.json"
THEMES_DIR = CONFIG_DIR / "temas"

def _rules(t):
    try: r=json.loads(t.rules_json or "{}")
    except Exception: r={}
    r.setdefault("duel_minutes",10); r.setdefault("start_delay_after_full_minutes",30)
    r.setdefault("prize_pool",100); r.setdefault("prize_first",50); r.setdefault("prize_second",35)
    r.setdefault("organizer_percent",10); r.setdefault("system_percent",5)
    r.setdefault("card",{}); r.setdefault("duel",{})
    # Runtime data is stored inside the edition snapshot so the server can
    # distinguish registration from the post-full waiting phase without
    # changing the original configuration rules.
    r.setdefault("runtime",{})
    return r

def _save_rules(t, rules):
    t.rules_json=json.dumps(rules,ensure_ascii=False,default=str)

def _load_json(path, default):
    try: return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (OSError, json.JSONDecodeError): return default

def _load_tournament_configs():
    payload=_load_json(CONFIG_FILE,{})
    configs=payload.get("torneios",[]) if isinstance(payload,dict) else []
    return [c for c in configs if isinstance(c,dict) and c.get("ativo",True)]

def _load_themes(category=None):
    path=THEMES_DIR / (f"{category}.json" if category else "")
    if category: return _load_json(path,{}).get("temas",[])
    result={}
    for p in THEMES_DIR.glob("*.json"):
        result[p.stem]=_load_json(p,{}).get("temas",[])
    return result

def get_card_rules(t):
    rules=_rules(t); card=rules.get("card") or {}
    theme_id=str(card.get("tema_id",rules.get("theme_id", ""))).strip()
    available=list(card.get("opcoes_disponiveis") or [])
    quantity=max(1,int(card.get("quantidade_opcoes",1)))
    answers=max(1,int((rules.get("duel") or {}).get("quantidade_respostas",card.get("quantidade_respostas",quantity))))
    return {"category":t.category,"theme_id":theme_id,"theme_name":card.get("tema_nome",theme_id),"available_options":available,"quantity_options":quantity,"quantity_answers":answers}

def _theme_config(category, theme_id):
    for theme in _load_themes(category):
        if str(theme.get("id"))==str(theme_id): return theme
    return None

def _config_id(t):
    try: return json.loads(t.rules_json or "{}").get("config_id")
    except Exception: return None

def _config_dates(config):
    tempo=config.get("tempo",{}) or {}; reg=max(1,int(tempo.get("inscricao_minutos",60))); delay=max(0,int(tempo.get("inicio_apos_lotacao_minutos",30)))
    registration=now()+timedelta(minutes=reg); return registration,registration,delay

def sincronizar_torneios_configurados(db):
    configs=_load_tournament_configs()
    if not configs: return []
    existing=list(db.scalars(select(Tournament).where(Tournament.status.in_(["open","live"]))).all())
    existing_ids={_config_id(t) for t in existing}
    admin=db.scalar(select(User).where(User.role=="admin",User.is_active==True).order_by(User.id.asc()))
    if not admin: return []
    created=[]
    for c in configs:
        cid=str(c.get("id_config","")).strip()
        if not cid or cid in existing_ids: continue
        cat=str(c.get("categoria","perfil")); theme_id=str(c.get("tema_id") or (c.get("card") or {}).get("tema_id") or "")
        theme=_theme_config(cat,theme_id) if theme_id else None
        if not theme: continue
        tempo=c.get("tempo",{}) or {}; entrada=c.get("entrada",{}) or {}; premio=c.get("premiacao",{}) or {}
        mode="paid" if str(c.get("modalidade", "gratuito")).lower() in {"pago","paid","entrada","com_entrada"} else "free"
        fee=int(entrada.get("valor",0)) if mode=="paid" else 0
        participantes=c.get("participantes",{}) or {}
        minimum=max(2,int(participantes.get("minimo",2)))
        max_players=max(minimum,int(participantes.get("maximo",8)))
        registration,starts,delay=_config_dates(c)
        first=int(premio.get("primeiro",50)); second=int(premio.get("segundo",35)); org=int(premio.get("organizador",10)); system=int(premio.get("sistema",5))
        if first+second+org+system!=100: continue
        card=c.get("card",{}) or {}; duel=c.get("duelo",{}) or {}
        qty=max(1,int(card.get("quantidade_opcoes",1))); answers=max(1,int(duel.get("quantidade_respostas",qty)))
        allowed=list(theme.get("opcoes",[]))
        if qty>len(allowed): continue
        rules={"config_id":cid,"config_version":2,
               "participants":{"minimum":minimum,"maximum":max_players},
               "timing":{"registration_minutes":max(1,int(tempo.get("inscricao_minutos",60))),
                         "start_delay_after_full_minutes":delay,
                         "duel_minutes":max(1,int(tempo.get("duelo_minutos",10)))},
               "duel_minutes":max(1,int(tempo.get("duelo_minutos",10))),"start_delay_after_full_minutes":delay,
               "prize_pool":int(premio.get("valor",0)),"prize_first":first,"prize_second":second,"organizer_percent":org,"system_percent":system,
               "entry":{"type":str(entrada.get("tipo","gratuita")),"value":fee,"mode":mode},
               "card":{"tema_id":theme_id,"tema_nome":theme.get("nome",theme_id),"opcoes_disponiveis":allowed,"quantidade_opcoes":qty},
               "duel":{"quantidade_respostas":answers}}
        t=Tournament(title=str(c.get("nome",cid)),category=cat,mode=mode,entry_fee=fee,max_players=max_players,
            prize_pool=fee*max_players if mode=="paid" else int(premio.get("valor",0)),registration_deadline=registration,starts_at=starts,
            rules_json=json.dumps(rules,ensure_ascii=False),created_by=admin.id)
        db.add(t); db.flush(); log_event(db,t.id,"tournament_created_from_config",admin.id,payload={"config_id":cid,"theme_id":theme_id}); created.append(t); existing_ids.add(cid)
    if created:
        db.commit()
        for t in created: db.refresh(t)
    return created

def create_tournament(db:Session,creator_id,data):
    if data.mode=="free" and data.entry_fee!=0: raise HTTPException(400,"Torneio gratuito deve ter entrada 0.")
    if data.mode=="paid" and data.entry_fee<=0: raise HTTPException(400,"Torneio com entrada precisa de valor maior que zero.")
    category=str(data.category or "").strip()
    categories=_load_json(CONFIG_DIR / "categorias.json",{}).get("categorias",[])
    category_cfg=next((x for x in categories if str(x.get("id"))==category),None)
    if not category_cfg: raise HTTPException(400,"Categoria não encontrada no catálogo.")
    if not bool(category_cfg.get("ativa",True)): raise HTTPException(400,"A categoria selecionada está desativada.")
    theme=_theme_config(category,data.theme_id)
    if not theme: raise HTTPException(400,"Tema não encontrado para a categoria selecionada.")
    available=[str(x).strip() for x in (theme.get("opcoes") or []) if str(x).strip()]
    requested=[str(x).strip() for x in (data.card_options or []) if str(x).strip()]
    if not requested or len(set(requested))!=len(requested): raise HTTPException(400,"As opções do card são inválidas ou repetidas.")
    if any(x not in available for x in requested): raise HTTPException(400,"Há opções no card que não pertencem ao tema selecionado.")
    if data.card_quantity>len(requested): raise HTTPException(400,"A quantidade do card não pode superar as opções disponíveis.")
    if data.answer_limit>data.card_quantity: raise HTTPException(400,"Quantidade de respostas não pode superar as opções do card.")
    registration=_aware(data.registration_deadline); starts=_aware(data.starts_at)
    if registration<=now() or starts<registration: raise HTTPException(400,"Datas inválidas.")
    total=data.prize_first+data.prize_second+data.organizer_percent+data.system_percent
    if total!=100: raise HTTPException(400,"A soma da premiação deve ser 100%.")
    rules={"duel_minutes":data.duel_minutes,"prize_pool":data.prize_pool,"prize_first":data.prize_first,"prize_second":data.prize_second,"organizer_percent":data.organizer_percent,"system_percent":data.system_percent,
           "card":{"tema_id":data.theme_id,"tema_nome":theme.get("nome",data.theme_name or data.theme_id),"opcoes_disponiveis":requested,"quantidade_opcoes":data.card_quantity},"duel":{"quantidade_respostas":data.answer_limit}}
    t=Tournament(title=data.title,category=data.category,mode=data.mode,entry_fee=data.entry_fee,max_players=data.max_players,
        prize_pool=data.entry_fee*data.max_players if data.mode=="paid" else data.prize_pool,registration_deadline=registration,starts_at=starts,rules_json=json.dumps(rules,ensure_ascii=False),created_by=creator_id)
    db.add(t); db.flush(); log_event(db,t.id,"tournament_created",creator_id,payload={"title":t.title,"mode":t.mode,"category":t.category}); db.commit(); db.refresh(t); return t

def list_tournaments(db,mode=None,status=None):
    reconcile_all(db); q=select(Tournament).where(Tournament.status!="deleted").order_by(Tournament.starts_at.asc())
    if mode:q=q.where(Tournament.mode==mode)
    if status:q=q.where(Tournament.status==status)
    return list(db.scalars(q).all())
def count_tournaments(db,mode=None,live=False):
    reconcile_all(db); q=select(func.count(Tournament.id)).where(Tournament.status==("live" if live else "open"))
    if mode:q=q.where(Tournament.mode==mode)
    return int(db.scalar(q) or 0)
def _confirmed(db,t): return list(db.scalars(select(TournamentEntry).where(TournamentEntry.tournament_id==t.id,TournamentEntry.status=="confirmed").order_by(TournamentEntry.joined_at.asc())).all())

def _card_for_entry(db,entry): return db.scalar(select(TournamentCard).where(TournamentCard.user_id==entry.user_id,TournamentCard.tournament_id==entry.tournament_id,TournamentCard.status.in_(["reserved","in_tournament","finalized"])).order_by(TournamentCard.id.desc()))
def _make_match(db,t,round_number,match_number,p1,p2):
    mins=int(_rules(t).get("duel_minutes",10)); started=now()
    m=TournamentMatch(tournament_id=t.id,round_number=round_number,match_number=match_number,player1_id=p1,player2_id=p2,target_number=0,status="pending",started_at=started,deadline=started+timedelta(minutes=mins)); db.add(m); return m

def _start_tournament(db,t):
    if t.status!="open": return False
    entries=_confirmed(db,t)
    rules=_rules(t)
    participants=rules.get("participants") or {}
    minimum=max(2,int(participants.get("minimo",2)))
    if len(entries)<minimum: return False
    if db.scalar(select(TournamentMatch.id).where(TournamentMatch.tournament_id==t.id)): t.status="live"; return True
    ids=[e.user_id for e in entries]; random.shuffle(ids); t.status="live"; t.prize_pool=t.entry_fee*len(ids) if t.mode=="paid" else int(_rules(t).get("prize_pool",t.prize_pool or 0))
    for i in range(0,len(ids),2):
        p1=ids[i]; p2=ids[i+1] if i+1<len(ids) else None; m=_make_match(db,t,1,i//2+1,p1,p2)
        if p2 is None: m.winner_id=p1; m.status="finished"; m.result_reason="bye"; m.finished_at=now()
    log_event(db,t.id,"tournament_started",payload={"participants":len(ids)})
    for uid in ids: notify(db,uid,"🔴 Torneio iniciado",f"{t.title} começou. Sua Arena está pronta.","tournament_started",t.id)
    db.commit(); return True

def _advance_round(db,t,round_number):
    matches=list(db.scalars(select(TournamentMatch).where(TournamentMatch.tournament_id==t.id,TournamentMatch.round_number==round_number).order_by(TournamentMatch.match_number.asc())).all())
    if not matches or any(m.status!="finished" for m in matches): return False
    winners=[m.winner_id for m in matches if m.winner_id]
    if len(winners)==1:
        _finish_tournament(db,t,winners[0],None); return True
    next_round=round_number+1
    if db.scalar(select(TournamentMatch.id).where(TournamentMatch.tournament_id==t.id,TournamentMatch.round_number==next_round)): return True
    for i in range(0,len(winners),2):
        p1=winners[i]; p2=winners[i+1] if i+1<len(winners) else None; m=_make_match(db,t,next_round,i//2+1,p1,p2)
        if p2 is None: m.winner_id=p1; m.status="finished"; m.result_reason="bye"; m.finished_at=now()
    log_event(db,t.id,"round_started",payload={"round":next_round,"matches":len(winners)//2+len(winners)%2}); db.commit(); return True

def _attempts(db,m,user_id): return list(db.scalars(select(TournamentGuess).where(TournamentGuess.match_id==m.id,TournamentGuess.attacker_user_id==user_id).order_by(TournamentGuess.attempt_number.asc())).all())
def _score(attempts): return sum(1 for x in attempts if x.is_correct)
def _all_correct(attempts,card):
    if not card: return False
    selected=set(json.loads(card.selected_options_json or "[]")); correct={x.option_value for x in attempts if x.is_correct}
    return bool(selected) and selected.issubset(correct)

def _resolve_ready(db,m):
    if m.status!="pending" or not m.player1_id or not m.player2_id: return False
    t=db.scalar(select(Tournament).where(Tournament.id==m.tournament_id)); rules=get_card_rules(t); limit=rules["quantity_answers"]
    e1=db.scalar(select(TournamentEntry).where(TournamentEntry.tournament_id==t.id,TournamentEntry.user_id==m.player1_id)); e2=db.scalar(select(TournamentEntry).where(TournamentEntry.tournament_id==t.id,TournamentEntry.user_id==m.player2_id))
    c1=_card_for_entry(db,e1); c2=_card_for_entry(db,e2); a1=_attempts(db,m,m.player1_id); a2=_attempts(db,m,m.player2_id)
    if _all_correct(a1,c2) or _all_correct(a2,c1) or (len(a1)>=limit and len(a2)>=limit):
        s1=_score(a1); s2=_score(a2)
        if s1==s2:
            db.execute(delete(TournamentGuess).where(TournamentGuess.match_id==m.id)); m.replay_number+=1; m.result_reason="replay_empate"; m.started_at=now(); m.deadline=now()+timedelta(minutes=int(rules.get("duel_minutes",10))); return False
        m.winner_id=m.player1_id if s1>s2 else m.player2_id; m.status="finished"; m.result_reason="card_score"; m.finished_at=now(); return True
    return False

def _resolve_timeout(db,m):
    if m.status!="pending" or not m.deadline or now()<_aware(m.deadline): return False
    a1=_attempts(db,m,m.player1_id) if m.player1_id else []; a2=_attempts(db,m,m.player2_id) if m.player2_id else []
    if not a1 and not a2: m.winner_id=m.player1_id; m.result_reason="technical_no_show"
    elif not a1: m.winner_id=m.player2_id; m.result_reason="timeout_no_show"
    elif not a2: m.winner_id=m.player1_id; m.result_reason="timeout_no_show"
    else:
        s1=_score(a1); s2=_score(a2)
        if s1==s2:
            db.execute(delete(TournamentGuess).where(TournamentGuess.match_id==m.id)); m.replay_number+=1; m.result_reason="replay_empate"; m.started_at=now(); m.deadline=now()+timedelta(minutes=int(_rules(db.scalar(select(Tournament).where(Tournament.id==m.tournament_id))).get("duel_minutes",10))); return False
        m.winner_id=m.player1_id if s1>s2 else m.player2_id; m.result_reason="timeout_card_score"
    m.status="finished"; m.finished_at=now(); return True

def process_tournament(db,t):
    changed=False
    if t.status in {"finished","cancelled"}: return False
    count=len(_confirmed(db,t))
    if t.status=="open":
        current=now()
        rules=_rules(t)
        participants=rules.get("participants") or {}
        minimum=max(2,int(participants.get("minimum",participants.get("minimo",2))))
        maximum=max(minimum,int(participants.get("maximum",participants.get("maximo",t.max_players))))
        delay=max(0,int(rules.get("start_delay_after_full_minutes",30)))
        runtime=rules.setdefault("runtime",{})

        # When the maximum is reached, record the exact moment once and create
        # the start deadline from that moment. Subsequent worker/API cycles must
        # never reset the five-minute countdown.
        if count>=maximum:
            if runtime.get("phase") != "waiting_start":
                full_at=current
                t.starts_at=full_at+timedelta(minutes=delay)
                runtime["phase"]="waiting_start"
                runtime["full_at"]=full_at.isoformat()
                runtime["start_at"]=t.starts_at.isoformat()
                _save_rules(t,rules)
                log_event(db,t.id,"registration_filled",payload={"participants":count,"starts_at":t.starts_at.isoformat(),"delay_minutes":delay})
                db.commit()
            if current>=_aware(t.starts_at):
                return _start_tournament(db,t)
            return True

        if current>_aware(t.registration_deadline):
            if count>=minimum:
                # If the registration deadline expires with the minimum, the
                # edition starts immediately. Only a full edition uses the
                # post-full delay above.
                t.starts_at=current
                runtime["phase"]="starting"
                _save_rules(t,rules)
                return _start_tournament(db,t)
            cancel_tournament(db,t); return True
        return False
    if t.status=="live":
        for m in list(db.scalars(select(TournamentMatch).where(TournamentMatch.tournament_id==t.id,TournamentMatch.status=="pending")).all()):
            before=m.status
            replay_before=m.replay_number
            if _resolve_ready(db,m): changed=True
            elif _resolve_timeout(db,m): changed=True

            # Empate: o duelo continua no mesmo match, mas em uma nova tentativa.
            # O evento e a notificação são disparados somente quando o replay é criado.
            if m.replay_number > replay_before:
                changed=True
                log_event(db,t.id,"match_replay",match_id=m.id,payload={
                    "round":m.round_number,"replay":m.replay_number,"reason":"replay_empate",
                    "message":"Empate. Replay iniciado; nenhum jogador foi eliminado."
                })
                for uid in (m.player1_id,m.player2_id):
                    if uid:
                        notify(db,uid,"🤝 EMPATE — REPLAY",
                               f"Seu duelo empatou. Você não foi eliminado: o replay {m.replay_number} começou agora. Prepare-se para jogar novamente.",
                               "match_replay",t.id,m.id)

            if before=="pending" and m.status=="finished":
                log_event(db,t.id,"match_finished",match_id=m.id,payload={"round":m.round_number,"winner_id":m.winner_id,"reason":m.result_reason,"replay":m.replay_number})
                for uid in (m.player1_id,m.player2_id):
                    if not uid: continue
                    if m.winner_id==uid:
                        title="🏆 VOCÊ AVANÇOU"
                        message=f"Você venceu o duelo da rodada {m.round_number} e avançou. Acompanhe sua próxima partida na Arena."
                        kind="match_advanced"
                    else:
                        title="💥 VOCÊ FOI ELIMINADO"
                        message=f"Você perdeu o duelo da rodada {m.round_number} e foi eliminado desta edição. A classificação e o histórico continuam disponíveis na Arena."
                        kind="match_eliminated"
                    notify(db,uid,title,message,kind,t.id,m.id)
        if changed: db.commit()
        rounds=list(db.scalars(select(TournamentMatch.round_number).where(TournamentMatch.tournament_id==t.id).distinct().order_by(TournamentMatch.round_number.desc())).all())
        if rounds: _advance_round(db,t,rounds[0])
        return changed
    return False

def reconcile_all(db):
    tournaments=list(db.scalars(select(Tournament).where(Tournament.status.in_(["open","live"]))).all())
    for t in tournaments:
        try:
            process_tournament(db,t)
        except Exception as exc:
            # Never let one broken edition stop the scheduler for every other
            # tournament. Roll back only this transaction and keep the worker alive.
            db.rollback()
            print(f"[TORNEIO] erro ao reconciliar {getattr(t, 'public_id', '?')}: {exc}")

def create_card(db,user_id,public_id,selected_options):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id,Tournament.status!="deleted"))
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    if t.status!="open": raise HTTPException(409,"O card só pode ser criado enquanto as inscrições estão abertas.")
    rules=get_card_rules(t); options=[str(x).strip() for x in selected_options]
    if len(options)!=rules["quantity_options"]: raise HTTPException(400,f"Você precisa escolher exatamente {rules['quantity_options']} opções.")
    if len(set(options))!=len(options): raise HTTPException(400,"Não é permitido repetir uma opção no card.")
    allowed=set(map(str,rules["available_options"]))
    if any(x not in allowed for x in options): raise HTTPException(400,"Uma ou mais opções não pertencem a este tema.")
    card=TournamentCard(user_id=user_id,category=t.category,theme_id=rules["theme_id"],selected_options_json=json.dumps(options,ensure_ascii=False),status="available")
    db.add(card); db.flush(); log_event(db,t.id,"card_created",user_id,payload={"card_id":card.card_id,"theme_id":card.theme_id,"quantity":len(options)}); db.commit(); db.refresh(card); return card

def join_tournament(db,user_id,public_id,card_id):
    reconcile_all(db); t=db.scalar(select(Tournament).where(Tournament.public_id==public_id).with_for_update())
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    if t.status!="open": raise HTTPException(409,"Torneio não está aberto para inscrições.")
    if now()>_aware(t.registration_deadline): raise HTTPException(409,"Inscrições encerradas.")
    count=db.scalar(select(func.count(TournamentEntry.id)).where(TournamentEntry.tournament_id==t.id,TournamentEntry.status=="confirmed")) or 0
    if count>=t.max_players: raise HTTPException(409,"Torneio lotado.")
    if db.scalar(select(TournamentEntry).where(TournamentEntry.tournament_id==t.id,TournamentEntry.user_id==user_id)): raise HTTPException(409,"Você já possui inscrição neste torneio.")
    card=db.scalar(select(TournamentCard).where(TournamentCard.card_id==card_id,TournamentCard.user_id==user_id))
    if not card or card.status!="available": raise HTTPException(409,"Card indisponível.")
    rules=get_card_rules(t); selected=json.loads(card.selected_options_json or "[]")
    if card.category!=t.category or card.theme_id!=rules["theme_id"] or len(selected)!=rules["quantity_options"] or any(x not in rules["available_options"] for x in selected): raise HTTPException(409,"Este card não é compatível com o torneio.")
    fee=t.entry_fee if t.mode=="paid" else 0
    entry=TournamentEntry(tournament_id=t.id,user_id=user_id,fee_paid=fee,status="confirmed"); db.add(entry); db.flush()
    card.tournament_id=t.id; card.status="reserved"; card.reserved_at=now()
    if fee: change_balance(db,user_id,-fee,"entry_fee",f"entry:{entry.entry_id}",t.id,entry.entry_id,f"Entrada no torneio {t.public_id}")
    log_event(db,t.id,"player_joined",user_id,payload={"entry_id":entry.entry_id,"card_id":card.card_id,"paid":fee}); notify(db,user_id,"🎟️ Inscrição confirmada",f"Você entrou em {t.title}.","tournament_joined",t.id)
    db.commit(); db.refresh(entry); return entry

def cancel_tournament(db,t):
    if t.status in {"finished","cancelled"}: return
    entries=list(db.scalars(select(TournamentEntry).where(TournamentEntry.tournament_id==t.id,TournamentEntry.status=="confirmed")).all())
    for e in entries:
        card=_card_for_entry(db,e)
        if card: card.status="available"; card.tournament_id=None; card.reserved_at=None
        if e.fee_paid:
            tx=change_balance(db,e.user_id,e.fee_paid,"refund",f"refund:{e.entry_id}",t.id,e.entry_id,f"Devolução por cancelamento {t.public_id}")
            db.add(Payment(tournament_id=t.id,user_id=e.user_id,beneficiary_type="refund",amount=e.fee_paid,status="paid",ledger_transaction_id=tx.transaction_id))
        e.status="refunded"
    t.status="cancelled"; t.prize_pool=0; log_event(db,t.id,"tournament_cancelled",payload={"participants":len(entries)})
    for e in entries: notify(db,e.user_id,"↩️ Torneio cancelado",f"{t.title} foi cancelado e sua entrada foi processada.","tournament_cancelled",t.id)
    db.commit()

def _finish_tournament(db,t,winner_id,runner_up_id):
    if t.status=="finished": return
    entries=_confirmed(db,t); participants=[e.user_id for e in entries]; ordered=[winner_id]+([runner_up_id] if runner_up_id and runner_up_id!=winner_id else []); ordered += [uid for uid in participants if uid not in ordered]
    settle_tournament(db,t,[(i+1,uid) for i,uid in enumerate(ordered)])

def settle_tournament(db,t,placements):
    if t.status=="finished": return
    if t.status=="cancelled": raise HTTPException(409,"Torneio cancelado.")
    n=db.scalar(select(func.count(TournamentEntry.id)).where(TournamentEntry.tournament_id==t.id,TournamentEntry.status=="confirmed")) or 0
    if n<2: raise HTTPException(409,"Participantes insuficientes.")
    rules=_rules(t); pool=t.entry_fee*n if t.mode=="paid" else int(rules.get("prize_pool",t.prize_pool or 0)); t.prize_pool=pool
    first=int(rules["prize_first"]); second=int(rules["prize_second"]); org=int(rules["organizer_percent"]); system=int(rules["system_percent"])
    if first+second+org+system!=100: raise HTTPException(500,"Configuração de premiação inválida.")
    for pos,uid in placements:
        if db.scalar(select(TournamentResult).where(TournamentResult.tournament_id==t.id,TournamentResult.user_id==uid)): continue
        user=db.scalar(select(User).where(User.id==uid).with_for_update());
        if not user: continue
        eco=get_economy_config(); pts=eco["torneios"]["pontuacao"]; xpr=eco["torneios"]["xp"]
        points=int(pts["primeiro"] if pos==1 else pts["segundo"] if pos==2 else pts["demais"])
        xp=int(xpr["primeiro"] if pos==1 else xpr["segundo"] if pos==2 else xpr["demais"])
        user.points+=points; user.xp+=xp; user.level=1+user.xp//int(eco["progresso"]["xp_por_nivel"])
        db.add(TournamentResult(tournament_id=t.id,user_id=uid,position=pos,points_earned=points,xp_earned=xp))
        pct=first if pos==1 else second if pos==2 else 0; amount=pool*pct//100
        if amount:
            tx=change_balance(db,uid,amount,"prize",f"prize:{t.public_id}:{pos}:{uid}",t.id,t.public_id,f"Premiação {pos}º lugar — {t.title}"); db.add(Payment(tournament_id=t.id,user_id=uid,beneficiary_type="winner",position=pos,percentage=pct,amount=amount,status="paid",ledger_transaction_id=tx.transaction_id))
        card=db.scalar(select(TournamentCard).where(TournamentCard.user_id==uid,TournamentCard.tournament_id==t.id));
        if card: card.status="finalized"; card.finalized_at=now()
    for pos,uid in placements: evaluate_user(db,uid); notify(db,uid,"🏆 Resultado do torneio",f"{t.title}: você terminou em {pos}º lugar.","tournament_result",t.id)
    organizer=pool*org//100
    if organizer and not db.scalar(select(Payment).where(Payment.tournament_id==t.id,Payment.beneficiary_type=="organizer")):
        tx=change_balance(db,t.created_by,organizer,"organizer_payout",f"organizer:{t.public_id}",t.id,t.public_id,f"Pagamento do organizador — {t.title}"); db.add(Payment(tournament_id=t.id,user_id=t.created_by,beneficiary_type="organizer",percentage=org,amount=organizer,status="paid",ledger_transaction_id=tx.transaction_id))
    if pool and not db.scalar(select(Payment).where(Payment.tournament_id==t.id,Payment.beneficiary_type=="system")):
        amount=pool*system//100; last=db.scalar(select(PlatformLedgerTransaction).order_by(PlatformLedgerTransaction.id.desc())); balance=(last.balance_after if last else 0)+amount
        db.add(PlatformLedgerTransaction(tournament_id=t.id,kind="tournament_fee",amount=amount,balance_after=balance,reference_id=t.public_id,description=f"Taxa do sistema — {t.title}")); db.add(Payment(tournament_id=t.id,user_id=None,beneficiary_type="system",percentage=system,amount=amount,status="paid"))
    t.status="finished"; log_event(db,t.id,"tournament_finished",payload={"winner_id":placements[0][1] if placements else None,"placements":len(placements)}); db.commit()

def submit_guess(db,user_id,match_id,option):
    reconcile_all(db); m=db.scalar(select(TournamentMatch).where(TournamentMatch.match_id==match_id))
    if not m: raise HTTPException(404,"Duelo não encontrado.")
    if user_id not in {m.player1_id,m.player2_id}: raise HTTPException(403,"Este duelo não pertence a você.")
    if m.status!="pending": raise HTTPException(409,"Este duelo já foi encerrado.")
    if m.deadline and now()>_aware(m.deadline): process_tournament(db,db.scalar(select(Tournament).where(Tournament.id==m.tournament_id))); raise HTTPException(409,"Tempo do duelo encerrado.")
    t=db.scalar(select(Tournament).where(Tournament.id==m.tournament_id)); rules=get_card_rules(t); option=str(option).strip()
    if option not in set(map(str,rules["available_options"])): raise HTTPException(400,"Essa opção não pertence ao tema do torneio.")
    attempts=_attempts(db,m,user_id)
    if len(attempts)>=rules["quantity_answers"]: raise HTTPException(409,"Você já utilizou todas as respostas permitidas.")
    replay_before=m.replay_number
    if any(a.option_value==option for a in attempts): raise HTTPException(409,"Você já tentou esta opção.")
    target_uid=m.player2_id if user_id==m.player1_id else m.player1_id; target_entry=db.scalar(select(TournamentEntry).where(TournamentEntry.tournament_id==t.id,TournamentEntry.user_id==target_uid)); target_card=_card_for_entry(db,target_entry)
    selected=set(json.loads(target_card.selected_options_json or "[]")) if target_card else set()
    g=TournamentGuess(match_id=m.id,attacker_user_id=user_id,target_card_id=target_card.id if target_card else 0,option_value=option,is_correct=option in selected,attempt_number=len(attempts)+1)
    if not target_card: raise HTTPException(500,"Card do adversário não encontrado.")
    db.add(g); db.flush(); log_event(db,t.id,"card_guess_submitted",user_id,m.id,payload={"attempt":g.attempt_number})
    resolved=_resolve_ready(db,m)
    if m.replay_number > replay_before:
        log_event(db,t.id,"match_replay",user_id,m.id,payload={
            "round":m.round_number,"replay":m.replay_number,"reason":"replay_empate",
            "message":"Empate. Replay iniciado; nenhum jogador foi eliminado."
        })
        for uid in (m.player1_id,m.player2_id):
            if uid:
                notify(db,uid,"🤝 EMPATE — REPLAY",
                       f"Seu duelo empatou. Você não foi eliminado: o replay {m.replay_number} começou agora. Prepare-se para jogar novamente.",
                       "match_replay",t.id,m.id)
    if resolved and m.status=="finished":
        # O resultado já está decidido; não dependa do próximo ciclo do worker.
        # Flush é necessário porque a sessão usa autoflush=False.
        db.flush()
        log_event(db,t.id,"match_finished",match_id=m.id,payload={"round":m.round_number,"winner_id":m.winner_id,"reason":m.result_reason,"replay":m.replay_number})
        for uid in (m.player1_id,m.player2_id):
            if not uid: continue
            if m.winner_id==uid:
                notify(db,uid,"🏆 VOCÊ AVANÇOU",f"Você venceu o duelo da rodada {m.round_number} e avançou. Acompanhe sua próxima partida na Arena.","match_advanced",t.id,m.id)
            else:
                notify(db,uid,"💥 VOCÊ FOI ELIMINADO",f"Você perdeu o duelo da rodada {m.round_number} e foi eliminado desta edição. A classificação e o histórico continuam disponíveis na Arena.","match_eliminated",t.id,m.id)
        _advance_round(db,t,m.round_number)
    db.commit(); return m
