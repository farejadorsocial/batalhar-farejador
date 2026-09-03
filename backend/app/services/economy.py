from datetime import datetime, timezone
import json
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select
from app.models import User, LedgerTransaction, EconomyState

CONFIG_FILE = Path(__file__).resolve().parents[2] / "config" / "economia.json"

DEFAULT_CONFIG = {
    "versao": 1,
    "moeda": {"nome": "Farejador", "plural": "Farejadores", "simbolo": "F", "casas_decimais": 0},
    "conversao": {"habilitada": True, "xp_por_farejador": 1000, "farejadores_por_conversao": 1, "xp_minimo": 1000},
    "supply": {"autorizado": 10000},
    "progresso": {"xp_por_nivel": 100},
    "torneios": {"pontuacao": {"primeiro": 100, "segundo": 60, "demais": 25}, "xp": {"primeiro": 250, "segundo": 150, "demais": 75}},
    "premiacoes": {"piso_minimo": 0},
}

def _deep_merge(base, extra):
    out = dict(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out

def get_economy_config():
    try:
        payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    return _deep_merge(DEFAULT_CONFIG, payload)

def save_economy_config(payload):
    cfg = _deep_merge(DEFAULT_CONFIG, payload or {})
    moeda = cfg["moeda"]; conv = cfg["conversao"]; supply = cfg["supply"]; prog = cfg["progresso"]
    if int(conv["xp_por_farejador"]) <= 0 or int(conv["farejadores_por_conversao"]) <= 0:
        raise HTTPException(400, "A conversão precisa ter valores maiores que zero.")
    if int(conv["xp_minimo"]) < int(conv["xp_por_farejador"]):
        raise HTTPException(400, "O XP mínimo não pode ser menor que o XP por Farejador.")
    if int(supply["autorizado"]) < 0:
        raise HTTPException(400, "Supply autorizado inválido.")
    if int(prog["xp_por_nivel"]) <= 0:
        raise HTTPException(400, "XP por nível precisa ser maior que zero.")
    p = cfg["torneios"]["pontuacao"]; x = cfg["torneios"]["xp"]
    for group in (p, x):
        if any(int(v) < 0 for v in group.values()):
            raise HTTPException(400, "Recompensas de torneio não podem ser negativas.")
    if not moeda["nome"] or not moeda["plural"] or not moeda["simbolo"]:
        raise HTTPException(400, "Preencha os dados da moeda.")
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(CONFIG_FILE)
    return cfg

def change_balance(db, user_id, amount, kind, idempotency_key, tournament_id=None, reference_id=None, description=""):
    if amount == 0: raise HTTPException(400, "Movimento de saldo não pode ser zero.")
    old = db.scalar(select(LedgerTransaction).where(LedgerTransaction.idempotency_key == idempotency_key))
    if old: return old
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user: raise HTTPException(404, "Usuário não encontrado.")
    new = user.balance + amount
    if new < 0: raise HTTPException(409, "Saldo de Farejadores insuficiente.")
    user.balance = new
    tx = LedgerTransaction(user_id=user_id, tournament_id=tournament_id, kind=kind, amount=amount, balance_after=new,
                           idempotency_key=idempotency_key, reference_id=reference_id, description=description)
    db.add(tx); db.flush(); return tx

def get_economy(db):
    cfg = get_economy_config()
    state = db.scalar(select(EconomyState).where(EconomyState.id == 1))
    if not state:
        state = EconomyState(id=1, authorized_supply=int(cfg["supply"]["autorizado"]), minted_supply=0,
                             xp_rate=int(cfg["conversao"]["xp_por_farejador"]),
                             farejador_rate=int(cfg["conversao"]["farejadores_por_conversao"]))
        db.add(state); db.commit(); db.refresh(state)
    else:
        state.authorized_supply = int(cfg["supply"]["autorizado"])
        state.xp_rate = int(cfg["conversao"]["xp_por_farejador"])
        state.farejador_rate = int(cfg["conversao"]["farejadores_por_conversao"])
        state.updated_at = datetime.now(timezone.utc)
        db.commit()
    return state

def convert_xp(db, user_id, xp_amount):
    if xp_amount <= 0: raise HTTPException(400, "Informe uma quantidade de XP maior que zero.")
    cfg = get_economy_config()
    conv = cfg["conversao"]
    if not conv["habilitada"]: raise HTTPException(409, "A conversão de XP está desabilitada.")
    xp_rate = int(conv["xp_por_farejador"]); fare_rate = int(conv["farejadores_por_conversao"])
    if xp_amount < int(conv["xp_minimo"]) or xp_amount % xp_rate != 0:
        raise HTTPException(400, f"A conversão deve começar em {conv['xp_minimo']} XP e usar múltiplos de {xp_rate} XP.")
    state = get_economy(db)
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user: raise HTTPException(404, "Usuário não encontrado.")
    if user.xp < xp_amount: raise HTTPException(409, "XP insuficiente.")
    fare = (xp_amount // xp_rate) * fare_rate
    if state.minted_supply + fare > state.authorized_supply: raise HTTPException(409, "Supply autorizado de Farejadores insuficiente.")
    user.xp -= xp_amount; user.balance += fare; state.minted_supply += fare; state.updated_at = datetime.now(timezone.utc)
    tx = LedgerTransaction(user_id=user_id, kind="xp_conversion", amount=fare, balance_after=user.balance,
                           idempotency_key=f"xp-conversion:{user_id}:{user.xp}:{xp_amount}:{state.minted_supply}",
                           reference_id="xp", description=f"Conversão de {xp_amount} XP em {fare} Farejador(es)")
    db.add(tx); db.commit(); db.refresh(user); db.refresh(state)
    return user
