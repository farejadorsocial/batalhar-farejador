from typing import Optional
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.api.deps import get_current_user,require_admin
from app.db.session import get_db
from app.models import Tournament,TournamentEntry,TournamentMatch,User,Payment,TournamentResult,TournamentCard,TournamentGuess,LedgerTransaction,PlatformLedgerTransaction
from app.schemas.tournament import *
from app.services.tournaments import reconcile_all, count_tournaments, list_tournaments, create_tournament, join_tournament, cancel_tournament, settle_tournament, submit_guess, create_card, get_card_rules, _rules, _aware, now, _config_id, _load_themes, sincronizar_torneios_configurados, CONFIG_FILE, _load_tournament_configs, _theme_config
from app.services.competitive import tournament_events, log_event
router=APIRouter(prefix="/tournaments",tags=["tournaments"])

def _detail(db,t,user_id=None):
    reconcile_all(db)
    entries=list(db.scalars(select(TournamentEntry).where(TournamentEntry.tournament_id==t.id).order_by(TournamentEntry.joined_at.asc())).all())
    ids=[e.user_id for e in entries]; users={u.id:u.username for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}
    card_rules=get_card_rules(t)
    matches=list(db.scalars(select(TournamentMatch).where(TournamentMatch.tournament_id==t.id).order_by(TournamentMatch.round_number.asc(),TournamentMatch.match_number.asc(),TournamentMatch.replay_number.asc())).all())
    def mrow(m):
        mine=user_id in {m.player1_id,m.player2_id}
        row={"match_id":m.match_id,"round":m.round_number,"match_number":m.match_number,"player1_id":m.player1_id,"player1":users.get(m.player1_id),"player2_id":m.player2_id,"player2":users.get(m.player2_id),"winner_id":m.winner_id,"winner":users.get(m.winner_id),"status":m.status,"result_reason":m.result_reason,"deadline":_aware(m.deadline),"replay_number":m.replay_number,"is_my_match":mine}
        if mine:
            own_attempts=list(db.scalars(select(TournamentGuess).where(TournamentGuess.match_id==m.id,TournamentGuess.attacker_user_id==user_id).order_by(TournamentGuess.attempt_number.asc())).all())
            row["my_attempts"]=[{"option":g.option_value,"correct":g.is_correct,"attempt":g.attempt_number} for g in own_attempts]
            row["my_attempts_used"]=len(own_attempts); row["my_attempts_remaining"]=max(0,card_rules["quantity_answers"]-len(own_attempts))
        if m.status=="finished" and mine:
            target_uid=m.player2_id if user_id==m.player1_id else m.player1_id
            target_entry=next((e for e in entries if e.user_id==target_uid),None)
            card=db.scalar(select(TournamentCard).where(TournamentCard.tournament_id==t.id,TournamentCard.user_id==target_uid)) if target_entry else None
            row["revealed_opponent_card"]=json.loads(card.selected_options_json or "[]") if card else []
        return row
    my=[mrow(m) for m in matches if user_id in {m.player1_id,m.player2_id} and m.status=="pending"] if user_id else []
    my_history=[mrow(m) for m in matches if user_id in {m.player1_id,m.player2_id}] if user_id else []
    my_latest_match=my_history[-1] if my_history else None
    my_pending=my[0] if my else None
    my_state="spectator"
    my_state_message="Escolha um card e participe para entrar na batalha."
    my_state_action="CRIAR CARD"
    if user_id:
        my_entry=next((e for e in entries if e.user_id==user_id),None)
        if my_entry:
            my_state="registered"
            my_state_message="Sua inscrição está confirmada. Aguarde o início dos duelos."
            my_state_action="AGUARDAR BATALHA"
            if my_pending:
                if int(my_pending.get("replay_number") or 0)>0 or my_pending.get("result_reason")=="replay_empate":
                    my_state="replay"
                    my_state_message=f"Empate no duelo. Replay {int(my_pending.get('replay_number') or 0)} em andamento: você continua na disputa. Jogue novamente quando sua vez aparecer."
                    my_state_action="JOGAR REPLAY"
                else:
                    my_state="duel"
                    my_state_message="Seu duelo está ativo. Descubra o card do adversário antes que seus ataques acabem."
                    my_state_action="JOGAR DUELO"
            elif my_latest_match and my_latest_match.get("status")=="finished":
                reason=my_latest_match.get("result_reason")
                if my_latest_match.get("winner_id")==user_id:
                    my_state="advanced"
                    my_state_message="Você venceu este duelo e avançou. Aguarde a próxima rodada ou acompanhe a chave."
                    my_state_action="VER CHAVE"
                elif my_latest_match.get("winner_id") is not None:
                    my_state="eliminated"
                    my_state_message="Você perdeu este duelo e foi eliminado desta edição. Acompanhe a classificação e prepare-se para a próxima batalha."
                    my_state_action="VER RESULTADO"
                elif reason in {"draw","replay","replay_empate"}:
                    my_state="replay"
                    my_state_message="Empate no duelo. Você não foi eliminado: o servidor iniciou um replay para decidir quem avança."
                    my_state_action="AGUARDAR REPLAY"
    results=list(db.scalars(select(TournamentResult).where(TournamentResult.tournament_id==t.id).order_by(TournamentResult.position.asc())).all())
    if user_id and t.status=="finished":
        my_result=next((r for r in results if r.user_id==user_id),None)
        if my_result:
            my_state="finished"
            my_state_message=f"Torneio encerrado. Sua classificação oficial foi {my_result.position}º lugar."
            my_state_action="VER PREMIAÇÃO"
    result_rows=[{"position":r.position,"user_id":r.user_id,"username":users.get(r.user_id),"points":r.points_earned,"xp":r.xp_earned} for r in results]
    my_card=db.scalar(select(TournamentCard).where(TournamentCard.user_id==user_id,TournamentCard.tournament_id==t.id)) if user_id else None
    my_available_cards=list(db.scalars(select(TournamentCard).where(TournamentCard.user_id==user_id,TournamentCard.status=="available",TournamentCard.tournament_id.is_(None),TournamentCard.category==t.category,TournamentCard.theme_id==card_rules["theme_id"]).order_by(TournamentCard.created_at.desc()).limit(20)).all()) if user_id else []
    my_payments=[]
    if user_id:
        my_payments=[{"payment_id":p.payment_id,"type":p.beneficiary_type,"position":p.position,"percentage":p.percentage,"amount":p.amount,"status":p.status,"created_at":_aware(p.created_at)} for p in db.scalars(select(Payment).where(Payment.tournament_id==t.id,Payment.user_id==user_id).order_by(Payment.created_at.asc())).all()]
    return {"public_id":t.public_id,"title":t.title,"category":t.category,"mode":t.mode,"status":t.status,"entry_fee":t.entry_fee,"max_players":t.max_players,"participant_count":len(entries),"prize_pool":t.prize_pool,"registration_deadline":_aware(t.registration_deadline),"starts_at":_aware(t.starts_at),"rules":_rules(t),"card_rules":card_rules,
            "my_card":{"card_id":my_card.card_id,"options":json.loads(my_card.selected_options_json or "[]"),"status":my_card.status} if my_card else None,
            "available_cards":[{"card_id":c.card_id,"options":json.loads(c.selected_options_json or "[]"),"status":c.status} for c in my_available_cards],
            "participants":[{"entry_id":e.entry_id,"user_id":e.user_id,"username":users.get(e.user_id),"status":e.status,"joined_at":_aware(e.joined_at)} for e in entries],"matches":[mrow(m) for m in matches],"my_matches":my,"my_latest_match":my_latest_match,"my_tournament_state":{"state":my_state,"message":my_state_message,"action":my_state_action},"results":result_rows,"winner":result_rows[0] if result_rows else None,"my_payments":my_payments,
            "seconds_to_registration_end":max(0,int((_aware(t.registration_deadline)-now()).total_seconds())) if t.status=="open" else 0,"seconds_to_start":max(0,int((_aware(t.starts_at)-now()).total_seconds())) if t.status=="open" else 0}

@router.get("/admin/config-data")
def admin_config_data(db:Session=Depends(get_db),admin=Depends(require_admin)):
    from pathlib import Path
    config_dir=CONFIG_FILE.parent
    def load(path, default):
        try: return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): return default
    return {
        "categorias": load(config_dir/"categorias.json",{}).get("categorias",[]),
        "premiacoes": load(config_dir/"premiacoes.json",{}).get("modelos",[]),
        "tempos": load(config_dir/"tempos.json",{}).get("padrao",{}),
        "temas": _load_themes()
    }


def _slug_id(value):
    value=str(value or "").strip().lower()
    value=re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value[:80]

def _write_json_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)

def _categories_payload():
    path=CONFIG_FILE.parent/"categorias.json"
    try: payload=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): payload={"categorias":[]}
    return payload if isinstance(payload,dict) else {"categorias":[]}

def _save_categories(items):
    _write_json_atomic(CONFIG_FILE.parent/"categorias.json",{"categorias":items})

def _theme_path(category): return CONFIG_FILE.parent/"temas"/f"{category}.json"

def _theme_list(category):
    path=_theme_path(category)
    try: payload=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): payload={"categoria":category,"temas":[]}
    return payload.get("temas",[]) if isinstance(payload,dict) else []

def _save_theme_list(category,items):
    _write_json_atomic(_theme_path(category),{"categoria":category,"temas":items})

def _catalog_snapshot():
    cats=_categories_payload().get("categorias",[])
    return {"categorias":cats,"temas":_load_themes(),"total_categorias":len(cats),"categorias_ativas":sum(bool(x.get("ativa",True)) for x in cats)}

@router.get("/admin/catalog")
def admin_catalog(db:Session=Depends(get_db),admin=Depends(require_admin)):
    return _catalog_snapshot()

@router.post("/admin/catalog/categories")
def create_category(data:dict,db:Session=Depends(get_db),admin=Depends(require_admin)):
    name=str(data.get("nome") or "").strip()
    cid=_slug_id(data.get("id") or name)
    if len(name)<2 or not cid: raise HTTPException(400,"Informe um nome de categoria válido.")
    if not re.fullmatch(r"[a-z0-9_]{2,80}",cid): raise HTTPException(400,"ID da categoria inválido.")
    payload=_categories_payload(); items=payload.get("categorias",[])
    if any(str(x.get("id"))==cid for x in items): raise HTTPException(409,"Já existe uma categoria com este ID.")
    items.append({"id":cid,"nome":name,"ativa":bool(data.get("ativa",True))}); _save_categories(items); _save_theme_list(cid,[])
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_category_created",reason=f"Categoria {cid} criada",metadata={"id":cid,"nome":name}); db.commit()
    return {"ok":True,"category":{"id":cid,"nome":name,"ativa":bool(data.get("ativa",True))}}

@router.post("/admin/catalog/categories/{category_id}")
def update_category(category_id:str,data:dict,db:Session=Depends(get_db),admin=Depends(require_admin)):
    payload=_categories_payload(); items=payload.get("categorias",[]); item=next((x for x in items if str(x.get("id"))==str(category_id)),None)
    if not item: raise HTTPException(404,"Categoria não encontrada.")
    name=str(data.get("nome",item.get("nome")) or "").strip()
    if len(name)<2: raise HTTPException(400,"Informe um nome de categoria válido.")
    item["nome"]=name; item["ativa"]=bool(data.get("ativa",item.get("ativa",True))); _save_categories(items)
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_category_updated",reason=f"Categoria {category_id} alterada",metadata={"id":category_id,"nome":name,"ativa":item["ativa"]}); db.commit()
    return {"ok":True,"category":item}

@router.delete("/admin/catalog/categories/{category_id}")
def delete_category(category_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    configs=_load_json_configs()
    if any(str(c.get("categoria"))==str(category_id) for c in configs):
        raise HTTPException(409,"Categoria está vinculada a configurações de torneio. Desative ou remova essas configurações antes de excluir.")
    payload=_categories_payload(); items=payload.get("categorias",[]); new=[x for x in items if str(x.get("id"))!=str(category_id)]
    if len(new)==len(items): raise HTTPException(404,"Categoria não encontrada.")
    _save_categories(new); path=_theme_path(category_id)
    try: path.unlink()
    except FileNotFoundError: pass
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_category_deleted",reason=f"Categoria {category_id} excluída",metadata={"id":category_id}); db.commit()
    return {"ok":True}

@router.post("/admin/catalog/categories/{category_id}/themes")
def create_theme(category_id:str,data:dict,db:Session=Depends(get_db),admin=Depends(require_admin)):
    cats=_categories_payload().get("categorias",[]); cat=next((x for x in cats if str(x.get("id"))==str(category_id)),None)
    if not cat: raise HTTPException(404,"Categoria não encontrada.")
    name=str(data.get("nome") or "").strip(); tid=_slug_id(data.get("id") or name)
    if len(name)<2 or not tid: raise HTTPException(400,"Informe um nome de tema válido.")
    if not re.fullmatch(r"[a-z0-9_]{2,80}",tid): raise HTTPException(400,"ID do tema inválido.")
    items=_theme_list(category_id)
    if any(str(x.get("id"))==tid for x in items): raise HTTPException(409,"Já existe um tema com este ID nesta categoria.")
    options=[str(x).strip() for x in (data.get("opcoes") or []) if str(x).strip()]
    if len(set(options))!=len(options): raise HTTPException(400,"Existem opções repetidas.")
    item={"id":tid,"nome":name,"opcoes":options}; items.append(item); _save_theme_list(category_id,items)
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_theme_created",reason=f"Tema {category_id}/{tid} criado",metadata={"categoria":category_id,"tema":tid,"opcoes":len(options)}); db.commit()
    return {"ok":True,"theme":item}

@router.post("/admin/catalog/categories/{category_id}/themes/{theme_id}")
def update_theme(category_id:str,theme_id:str,data:dict,db:Session=Depends(get_db),admin=Depends(require_admin)):
    items=_theme_list(category_id); item=next((x for x in items if str(x.get("id"))==str(theme_id)),None)
    if not item: raise HTTPException(404,"Tema não encontrado.")
    name=str(data.get("nome",item.get("nome")) or "").strip()
    options=[str(x).strip() for x in (data.get("opcoes",item.get("opcoes",[])) or []) if str(x).strip()]
    if len(name)<2: raise HTTPException(400,"Informe um nome de tema válido.")
    if not options: raise HTTPException(400,"O tema precisa ter pelo menos uma opção.")
    if len(set(options))!=len(options): raise HTTPException(400,"Existem opções repetidas.")
    item["nome"]=name; item["opcoes"]=options; _save_theme_list(category_id,items)
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_theme_updated",reason=f"Tema {category_id}/{theme_id} alterado",metadata={"categoria":category_id,"tema":theme_id,"opcoes":len(options)}); db.commit()
    return {"ok":True,"theme":item}

@router.delete("/admin/catalog/categories/{category_id}/themes/{theme_id}")
def delete_theme(category_id:str,theme_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    configs=_load_json_configs()
    if any(str(c.get("categoria"))==str(category_id) and str(c.get("tema_id"))==str(theme_id) for c in configs):
        raise HTTPException(409,"Tema está vinculado a uma configuração de torneio. Remova ou altere a configuração antes de excluir.")
    items=_theme_list(category_id); new=[x for x in items if str(x.get("id"))!=str(theme_id)]
    if len(new)==len(items): raise HTTPException(404,"Tema não encontrado.")
    _save_theme_list(category_id,new)
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_theme_deleted",reason=f"Tema {category_id}/{theme_id} excluído",metadata={"categoria":category_id,"tema":theme_id}); db.commit()
    return {"ok":True}

def _validate_config(data):
    cid=str(data.get("id_config") or "").strip()
    if not cid: raise HTTPException(400,"Informe um ID de configuração.")
    name=str(data.get("nome") or "").strip()
    if len(name)<3: raise HTTPException(400,"Informe um nome válido.")
    minimo=max(2,int(data.get("participantes_minimo",2))); maximo=int(data.get("participantes_maximo",2))
    if maximo<minimo: raise HTTPException(400,"Máximo de participantes não pode ser menor que o mínimo.")
    qty=max(1,int(data.get("quantidade_opcoes",1))); answers=max(1,int(data.get("quantidade_respostas",1)))
    if answers>qty: raise HTTPException(400,"Quantidade de respostas não pode ser maior que as opções do card.")
    modalidade=str(data.get("modalidade","gratuito")).lower()
    entrada_tipo="farejador" if modalidade=="pago" else "gratuita"
    entry_value=int(data.get("entrada_valor",0))
    if modalidade=="pago" and entry_value<=0: raise HTTPException(400,"Torneio pago precisa de entrada maior que zero.")
    if modalidade!="pago": entry_value=0
    parts=[int(data.get("primeiro",50)),int(data.get("segundo",35)),int(data.get("organizador",10)),int(data.get("sistema",5))]
    if sum(parts)!=100: raise HTTPException(400,"A distribuição da premiação deve somar 100%.")
    category=str(data.get("categoria") or "").strip(); theme_id=str(data.get("tema_id") or "").strip()
    theme=_theme_config(category,theme_id)
    if not theme: raise HTTPException(400,"Tema não encontrado para a categoria selecionada.")
    options=list(theme.get("opcoes",[]))
    if qty>len(options): raise HTTPException(400,f"O tema escolhido possui apenas {len(options)} opções.")
    return {
        "id_config":cid,"ativo":bool(data.get("ativo",True)),"nome":name,"categoria":category,"tema_id":theme_id,
        "modalidade":modalidade,
        "participantes":{"minimo":minimo,"maximo":maximo},
        "tempo":{"inscricao_minutos":max(1,int(data.get("inscricao_minutos",60))),
                 "inicio_apos_lotacao_minutos":max(0,int(data.get("inicio_apos_lotacao_minutos",30))),
                 "duelo_minutos":max(1,int(data.get("duelo_minutos",10)))},
        "card":{"quantidade_opcoes":qty},
        "duelo":{"quantidade_respostas":answers},
        "entrada":{"tipo":entrada_tipo,"valor":entry_value},
        "premiacao":{"tipo":str(data.get("premiacao_tipo","fixa")),"valor":max(0,int(data.get("premiacao_valor",0))),
                     "primeiro":parts[0],"segundo":parts[1],"organizador":parts[2],"sistema":parts[3]}
    }

def _save_configs(configs):
    payload={"versao":2,"descricao":"Configuração das edições automáticas. Cada edição grava um snapshot das regras e do card; alterações futuras não mudam torneios já abertos ou em andamento.","torneios":configs}
    tmp=CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(CONFIG_FILE)

@router.get("/admin/configs")
def configured_tournaments(db:Session=Depends(get_db),admin=Depends(require_admin)):
    configs=_load_json_configs()
    open_rows=list(db.scalars(select(Tournament).where(Tournament.status.in_(["open","live"]))).all())
    by_id={_config_id(x) for x in open_rows}
    return {"arquivo":str(CONFIG_FILE),"configs":[{**c,"edicao_ativa":str(c.get("id_config")) in by_id} for c in configs],"total":len(configs)}

def _load_json_configs():
    try: payload=json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): payload={}
    return [c for c in payload.get("torneios",[]) if isinstance(c,dict)]

@router.get("/admin/configs/detail")
def config_detail(config_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    c=next((x for x in _load_json_configs() if str(x.get("id_config"))==str(config_id)),None)
    if not c: raise HTTPException(404,"Configuração não encontrada.")
    active=any(_config_id(t)==str(config_id) and t.status in {"open","live"} for t in db.scalars(select(Tournament).where(Tournament.status.in_(["open","live"]))).all())
    return {"config":c,"edicao_ativa":active}

@router.post("/admin/configs")
def create_config(data:dict,db:Session=Depends(get_db),admin=Depends(require_admin)):
    cfg=_validate_config(data)
    configs=_load_json_configs()
    if any(str(x.get("id_config"))==cfg["id_config"] for x in configs): raise HTTPException(409,"Já existe uma configuração com este ID.")
    configs.append(cfg); _save_configs(configs)
    created=sincronizar_torneios_configurados(db) if cfg["ativo"] else []
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_config_created",reason=f"Configuração {cfg['id_config']} criada",metadata={"id_config":cfg["id_config"]})
    db.commit()
    return {"ok":True,"config":cfg,"edicoes_criadas":[x.public_id for x in created]}

@router.post("/admin/configs/{config_id}")
def update_config(config_id:str,data:dict,db:Session=Depends(get_db),admin=Depends(require_admin)):
    cfg=_validate_config({**data,"id_config":config_id})
    configs=_load_json_configs()
    idx=next((i for i,x in enumerate(configs) if str(x.get("id_config"))==str(config_id)),None)
    if idx is None: raise HTTPException(404,"Configuração não encontrada.")
    configs[idx]=cfg; _save_configs(configs)
    created=sincronizar_torneios_configurados(db) if cfg["ativo"] else []
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_config_updated",reason=f"Configuração {config_id} alterada",metadata={"id_config":config_id})
    db.commit()
    return {"ok":True,"config":cfg,"edicoes_criadas":[x.public_id for x in created]}


@router.delete("/admin/configs/{config_id}")
def delete_config(config_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    configs=_load_json_configs(); cfg=next((x for x in configs if str(x.get("id_config"))==str(config_id)),None)
    if not cfg: raise HTTPException(404,"Configuração não encontrada.")
    active=any(_config_id(t)==str(config_id) and t.status in {"open","live"} for t in db.scalars(select(Tournament).where(Tournament.status.in_(["open","live"]))).all())
    if active: raise HTTPException(409,"Esta configuração possui uma edição ativa. Desative a configuração e aguarde/cancele a edição antes de excluir.")
    _save_configs([x for x in configs if str(x.get("id_config"))!=str(config_id)])
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_config_deleted",reason=f"Configuração {config_id} excluída",metadata={"id_config":config_id}); db.commit()
    return {"ok":True}

@router.get("/admin/editions/{public_id}")
def admin_edition_detail(public_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t or t.status=="deleted": raise HTTPException(404,"Edição não encontrada.")
    entries=list(db.scalars(select(TournamentEntry).where(TournamentEntry.tournament_id==t.id).order_by(TournamentEntry.joined_at.asc())).all())
    user_ids=list({e.user_id for e in entries}); users={u.id:u.username for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    matches=list(db.scalars(select(TournamentMatch).where(TournamentMatch.tournament_id==t.id).order_by(TournamentMatch.round_number.asc(),TournamentMatch.match_number.asc(),TournamentMatch.replay_number.asc())).all())
    pays=list(db.scalars(select(Payment).where(Payment.tournament_id==t.id).order_by(Payment.created_at.asc())).all())
    events=tournament_events(db,t.id,100)
    return {"tournament":{"public_id":t.public_id,"title":t.title,"category":t.category,"mode":t.mode,"status":t.status,"entry_fee":t.entry_fee,"max_players":t.max_players,"prize_pool":t.prize_pool,"registration_deadline":_aware(t.registration_deadline),"starts_at":_aware(t.starts_at),"config_id":_config_id(t),"rules":_rules(t)},
            "participants":[{"entry_id":e.entry_id,"user_id":e.user_id,"username":users.get(e.user_id),"fee_paid":e.fee_paid,"status":e.status,"joined_at":_aware(e.joined_at)} for e in entries],
            "matches":[{"match_id":m.match_id,"round":m.round_number,"match_number":m.match_number,"player1":users.get(m.player1_id,m.player1_id),"player2":users.get(m.player2_id,m.player2_id),"winner":users.get(m.winner_id,m.winner_id),"status":m.status,"reason":m.result_reason,"replay":m.replay_number,"deadline":_aware(m.deadline)} for m in matches],
            "payments":[{"payment_id":p.payment_id,"user_id":p.user_id,"beneficiary_type":p.beneficiary_type,"position":p.position,"percentage":p.percentage,"amount":p.amount,"status":p.status,"created_at":_aware(p.created_at)} for p in pays],"events":events,
            "financial":{"entry_volume":sum(int(e.fee_paid or 0) for e in entries),"winner_payout":sum(int(p.amount or 0) for p in pays if p.beneficiary_type=="winner"),"organizer_payout":sum(int(p.amount or 0) for p in pays if p.beneficiary_type=="organizer"),"system_revenue":sum(int(p.amount or 0) for p in pays if p.beneficiary_type=="system"),"refunds":sum(int(p.amount or 0) for p in pays if p.beneficiary_type=="refund")}}

@router.post("/admin/editions/{public_id}")
def update_admin_edition(public_id:str,data:dict,db:Session=Depends(get_db),admin=Depends(require_admin)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t or t.status=="deleted": raise HTTPException(404,"Edição não encontrada.")
    if t.status!="open": raise HTTPException(409,"Somente edições abertas podem ser editadas. Edições ao vivo ou encerradas preservam o snapshot.")
    entries_count=int(db.scalar(select(func.count(TournamentEntry.id)).where(TournamentEntry.tournament_id==t.id,TournamentEntry.status=="confirmed")) or 0)
    title=str(data.get("title",t.title) or "").strip()
    if len(title)<3: raise HTTPException(400,"Nome do torneio inválido.")
    max_players=int(data.get("max_players",t.max_players)); min_players=max(2,int((_rules(t).get("participants") or {}).get("minimum",2)))
    if max_players<min_players or max_players>128 or max_players<entries_count: raise HTTPException(400,"Limite de participantes inválido.")
    if "entry_fee" in data and entries_count: raise HTTPException(409,"A entrada não pode ser alterada depois que existem participantes.")
    entry_fee=int(data.get("entry_fee",t.entry_fee)); mode=str(data.get("mode",t.mode))
    if mode not in {"free","paid"}: raise HTTPException(400,"Modalidade inválida.")
    if mode=="free": entry_fee=0
    if mode=="paid" and entry_fee<=0: raise HTTPException(400,"Torneio pago precisa de entrada maior que zero.")
    reg=t.registration_deadline; starts=t.starts_at
    for key in ("registration_deadline","starts_at"):
        if key in data and data[key]:
            raw=str(data[key]); value=datetime.fromisoformat(raw.replace("Z","+00:00")); value=_aware(value)
            if key=="registration_deadline": reg=value
            else: starts=value
    if reg<=now() or starts<reg: raise HTTPException(400,"Datas inválidas.")
    rules=_rules(t); rules["duel_minutes"]=max(1,int(data.get("duel_minutes",rules.get("duel_minutes",10))))
    rules["prize_pool"]=max(0,int(data.get("prize_pool",rules.get("prize_pool",t.prize_pool))))
    for key in ("prize_first","prize_second","organizer_percent","system_percent"):
        rules[key]=max(0,min(100,int(data.get(key,rules.get(key,0)))))
    if sum(rules[k] for k in ("prize_first","prize_second","organizer_percent","system_percent"))!=100: raise HTTPException(400,"A distribuição da premiação deve somar 100%.")
    card=rules.setdefault("card",{}); duel=rules.setdefault("duel",{})
    if "quantidade_opcoes" in data: card["quantidade_opcoes"]=max(1,int(data["quantidade_opcoes"]))
    if "quantidade_respostas" in data: duel["quantidade_respostas"]=max(1,int(data["quantidade_respostas"]))
    theme=_theme_config(t.category,card.get("tema_id"))
    if theme:
        allowed=list(theme.get("opcoes",[])); card["opcoes_disponiveis"]=allowed; card["tema_nome"]=theme.get("nome",card.get("tema_id"));
        if int(card.get("quantidade_opcoes",1))>len(allowed): raise HTTPException(400,"Quantidade de opções do card supera o tema atual.")
        if int(duel.get("quantidade_respostas",1))>int(card.get("quantidade_opcoes",1)): raise HTTPException(400,"Respostas não podem superar as opções do card.")
    rules["participants"]={"minimum":min_players,"maximum":max_players}; rules.setdefault("runtime",{}).clear()
    t.title=title; t.mode=mode; t.entry_fee=entry_fee; t.max_players=max_players; t.prize_pool=entry_fee*max_players if mode=="paid" else rules["prize_pool"]; t.registration_deadline=reg; t.starts_at=starts; _save_rules(t,rules)
    log_event(db,t.id,"tournament_admin_updated",admin.id,payload={"fields":list(data.keys())}); db.commit(); db.refresh(t)
    return {"ok":True,"public_id":t.public_id}

@router.post("/admin/editions/{public_id}/cancel")
def admin_cancel_edition(public_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t or t.status=="deleted": raise HTTPException(404,"Edição não encontrada.")
    if t.status in {"finished","cancelled"}: return {"ok":True,"status":t.status}
    cancel_tournament(db,t)
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_edition_cancelled",reason=f"Edição {public_id} cancelada",metadata={"public_id":public_id}); db.commit()
    return {"ok":True,"status":"cancelled"}

def _delete_admin_edition(public_id:str,db:Session,admin):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t or t.status=="deleted": raise HTTPException(404,"Edição não encontrada.")
    if t.status in {"open","live"}: raise HTTPException(409,"Uma edição ativa não pode ser excluída. Cancele primeiro para devolver as entradas e preservar o caixa.")
    previous_status=t.status
    t.status="deleted"
    log_event(db,t.id,"tournament_archived",admin.id,payload={"reason":"exclusao_administrativa","status_anterior":previous_status})
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_edition_deleted",reason=f"Edição {public_id} excluída/arquivada",metadata={"public_id":public_id,"status_anterior":previous_status})
    db.commit()
    return {"ok":True,"status":"deleted"}

@router.post("/admin/editions/{public_id}/delete")
def delete_admin_edition_action(public_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    return _delete_admin_edition(public_id,db,admin)

@router.delete("/admin/editions/{public_id}")
def delete_admin_edition(public_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    return _delete_admin_edition(public_id,db,admin)

@router.post("/admin/configs/{config_id}/toggle")
def toggle_config(config_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    configs=_load_json_configs()
    idx=next((i for i,x in enumerate(configs) if str(x.get("id_config"))==str(config_id)),None)
    if idx is None: raise HTTPException(404,"Configuração não encontrada.")
    configs[idx]["ativo"]=not bool(configs[idx].get("ativo",True)); _save_configs(configs)
    created=sincronizar_torneios_configurados(db) if configs[idx]["ativo"] else []
    from app.services.security import audit_action
    audit_action(db,admin.id,"tournament_config_toggled",reason=f"Configuração {config_id} {'ativada' if configs[idx]['ativo'] else 'desativada'}",metadata={"id_config":config_id,"ativo":configs[idx]["ativo"]})
    db.commit()
    return {"ok":True,"ativo":configs[idx]["ativo"],"edicoes_criadas":[x.public_id for x in created]}

@router.get("/admin/overview")
def admin_overview(db:Session=Depends(get_db),admin=Depends(require_admin)):
    reconcile_all(db); sincronizar_torneios_configurados(db)
    rows=list(db.scalars(select(Tournament).where(Tournament.status!="deleted").order_by(Tournament.starts_at.asc()).limit(100)).all())
    configs=_load_json_configs()
    counts={}
    for status in ("open","live","finished","cancelled","deleted"):
        counts[status]=int(db.scalar(select(func.count(Tournament.id)).where(Tournament.status==status)) or 0)
    return {"metrics":{
        "configuracoes":len(configs),"configuracoes_ativas":sum(bool(c.get("ativo",True)) for c in configs),
        "abertos":counts["open"],"ao_vivo":counts["live"],
        "encerrados":counts["finished"],"cancelados":counts["cancelled"],"excluidos":counts["deleted"]
    },"edicoes":[
        {"public_id":t.public_id,"title":t.title,"category":t.category,"mode":t.mode,"status":t.status,"entry_fee":t.entry_fee,
         "max_players":t.max_players,"participant_count":int(db.scalar(select(func.count(TournamentEntry.id)).where(TournamentEntry.tournament_id==t.id,TournamentEntry.status=="confirmed")) or 0),
         "prize_pool":t.prize_pool,"registration_deadline":_aware(t.registration_deadline),"starts_at":_aware(t.starts_at),"config_id":_config_id(t)}
        for t in rows]}

@router.get("/central")
def central(db:Session=Depends(get_db),user=Depends(get_current_user)):
    return {"free":count_tournaments(db,"free"),"paid":count_tournaments(db,"paid"),"live_free":count_tournaments(db,"free",True),"live_paid":count_tournaments(db,"paid",True)}

@router.get("",response_model=list[TournamentOut])
def tournaments(mode:Optional[str]=None,status:Optional[str]=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    rows=list_tournaments(db,mode,status)
    return [{
        "public_id":t.public_id,"title":t.title,"category":t.category,"mode":t.mode,
        "status":t.status,"entry_fee":t.entry_fee,"max_players":t.max_players,
        "prize_pool":t.prize_pool,"participant_count":int(db.scalar(select(func.count(TournamentEntry.id)).where(TournamentEntry.tournament_id==t.id,TournamentEntry.status=="confirmed")) or 0),"registration_deadline":_aware(t.registration_deadline),
        "starts_at":_aware(t.starts_at),"seconds_to_registration_end":max(0,int((_aware(t.registration_deadline)-now()).total_seconds())) if t.status=="open" else 0,"seconds_to_start":max(0,int((_aware(t.starts_at)-now()).total_seconds())) if t.status=="open" else 0,"rules":_rules(t)
    } for t in rows]

@router.post("",response_model=TournamentOut)
def create(data:TournamentCreateIn,db:Session=Depends(get_db),admin=Depends(require_admin)): return create_tournament(db,admin.id,data)

@router.get("/{public_id}")
def detail(public_id:str,db:Session=Depends(get_db),user=Depends(get_current_user)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    return _detail(db,t,user.id)

@router.post("/{public_id}/join",response_model=JoinOut)
def join(public_id:str,data:JoinIn,db:Session=Depends(get_db),user=Depends(get_current_user)):
    e=join_tournament(db,user.id,public_id,data.card_id); t=db.scalar(select(Tournament).where(Tournament.id==e.tournament_id)); db.refresh(user); return JoinOut(ok=True,entry_id=e.entry_id,balance=user.balance,tournament=t,card_id=data.card_id)

@router.get("/{public_id}/entries")
def entries(public_id:str,db:Session=Depends(get_db),user=Depends(get_current_user)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    return _detail(db,t,user.id)["participants"]

@router.get("/{public_id}/my-match")
def my_match(public_id:str,db:Session=Depends(get_db),user=Depends(get_current_user)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    d=_detail(db,t,user.id); return d["my_matches"][0] if d["my_matches"] else None

@router.post("/{public_id}/cards")
def card(public_id:str,data:CardCreateIn,db:Session=Depends(get_db),user=Depends(get_current_user)):
    c=create_card(db,user.id,public_id,data.selected_options)
    return {"card_id":c.card_id,"category":c.category,"theme_id":c.theme_id,"options":json.loads(c.selected_options_json or "[]"),"status":c.status}

@router.get("/{public_id}/card-config")
def card_config(public_id:str,db:Session=Depends(get_db),user=Depends(get_current_user)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    return get_card_rules(t)

@router.post("/{public_id}/matches/{match_id}/guess")
def guess(public_id:str,match_id:str,data:GuessIn,db:Session=Depends(get_db),user=Depends(get_current_user)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    m=submit_guess(db,user.id,match_id,data.option)
    return _detail(db,t,user.id)

@router.post("/{public_id}/cancel")
def cancel(public_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    cancel_tournament(db,t); return {"ok":True,"status":"cancelled"}

@router.post("/{public_id}/settle")
def settle(public_id:str,placements:list[dict],db:Session=Depends(get_db),admin=Depends(require_admin)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    settle_tournament(db,t,[(int(x["position"]),int(x["user_id"])) for x in placements]); return {"ok":True,"status":"finished"}

@router.get("/{public_id}/payments")
def payments(public_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    return db.scalars(select(Payment).where(Payment.tournament_id==t.id).order_by(Payment.created_at.asc())).all()

@router.get("/{public_id}/config")
def config(public_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    return {"public_id":t.public_id,"title":t.title,"category":t.category,"mode":t.mode,"entry_fee":t.entry_fee,"max_players":t.max_players,"registration_deadline":_aware(t.registration_deadline),"starts_at":_aware(t.starts_at),"rules":_rules(t)}


@router.get("/{public_id}/events")
def events(public_id:str, limit:int=100, db:Session=Depends(get_db), user=Depends(get_current_user)):
    t=db.scalar(select(Tournament).where(Tournament.public_id==public_id))
    if not t: raise HTTPException(404,"Torneio não encontrado.")
    return tournament_events(db,t.id,limit)
