from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session
from app.api.deps import require_admin
from app.db.session import get_db
from app.models import EconomyState, User, LedgerTransaction, PlatformLedgerTransaction, Tournament, Payment
from app.services.economy import get_economy_config, save_economy_config
from app.services.security import audit_action

router = APIRouter(prefix="/economy/admin", tags=["economy-admin"])

class EconomyConfigIn(BaseModel):
    config: dict[str, Any]

@router.get("")
def economy_overview(db: Session = Depends(get_db), admin=Depends(require_admin)):
    cfg = get_economy_config()
    state = db.scalar(select(EconomyState).where(EconomyState.id == 1))
    if not state:
        state = EconomyState(id=1, authorized_supply=int(cfg["supply"]["autorizado"]), minted_supply=0,
                             xp_rate=int(cfg["conversao"]["xp_por_farejador"]), farejador_rate=int(cfg["conversao"]["farejadores_por_conversao"]))
        db.add(state); db.commit(); db.refresh(state)
    users = int(db.scalar(select(func.count(User.id))) or 0)
    total_balance = int(db.scalar(select(func.coalesce(func.sum(User.balance), 0))) or 0)
    recent = list(db.scalars(select(LedgerTransaction).order_by(LedgerTransaction.created_at.desc()).limit(30)).all())
    platform = list(db.scalars(select(PlatformLedgerTransaction).order_by(PlatformLedgerTransaction.created_at.desc()).limit(15)).all())
    paid_entries = int(db.scalar(select(func.coalesce(func.sum(func.abs(LedgerTransaction.amount)),0)).where(LedgerTransaction.kind=="entry_fee")) or 0)
    winner_payout = int(db.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.beneficiary_type=="winner",Payment.status=="paid")) or 0) if "Payment" in globals() else 0
    organizer_revenue = int(db.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.beneficiary_type=="organizer",Payment.status=="paid")) or 0) if "Payment" in globals() else 0
    system_revenue = int(db.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.beneficiary_type=="system",Payment.status=="paid")) or 0) if "Payment" in globals() else 0
    refunds = int(db.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.beneficiary_type=="refund",Payment.status=="paid")) or 0) if "Payment" in globals() else 0
    paid_tournaments = int(db.scalar(select(func.count(Tournament.id)).where(Tournament.mode=="paid",Tournament.status!="deleted")) or 0)
    finished_paid = int(db.scalar(select(func.count(Tournament.id)).where(Tournament.mode=="paid",Tournament.status=="finished")) or 0)
    earning_rows = list(db.execute(
        select(User.id,User.username,User.balance,
               func.coalesce(func.sum(LedgerTransaction.amount),0).label("earned"))
        .join(LedgerTransaction,LedgerTransaction.user_id==User.id,isouter=True)
        .where(LedgerTransaction.kind.in_(["prize","organizer_payout"]))
        .group_by(User.id,User.username,User.balance)
        .order_by(desc("earned"))
        .limit(50)
    ).all())
    conversion_quote = {"xp_por_farejador":int(cfg["conversao"]["xp_por_farejador"]),"farejadores_por_conversao":int(cfg["conversao"]["farejadores_por_conversao"]),"xp_minimo":int(cfg["conversao"]["xp_minimo"]),"habilitada":bool(cfg["conversao"]["habilitada"])}
    return {
        "config": cfg,
        "state": {"authorized_supply": state.authorized_supply, "minted_supply": state.minted_supply,
                  "remaining_supply": max(0, state.authorized_supply - state.minted_supply),
                  "xp_rate": state.xp_rate, "farejador_rate": state.farejador_rate},
        "metrics": {"users": users, "total_balance": total_balance,
                    "minted_supply": state.minted_supply, "remaining_supply": max(0, state.authorized_supply - state.minted_supply),
                    "paid_entries": paid_entries, "winner_payout": winner_payout, "organizer_revenue": organizer_revenue,
                    "system_revenue": system_revenue, "refunds": refunds, "paid_tournaments": paid_tournaments, "finished_paid_tournaments": finished_paid},
        "cash": {"entries":paid_entries,"prizes":winner_payout,"organizer":organizer_revenue,"system":system_revenue,"refunds":refunds,"net_system":system_revenue-refunds,
                 "conversion_quote":conversion_quote},
        "user_earnings": [{"user_id":int(r.id),"username":r.username,"balance":int(r.balance or 0),"earned":int(r.earned or 0)} for r in earning_rows],
        "recent_transactions": [
            {"transaction_id": x.transaction_id, "user_id": x.user_id, "tournament_id": x.tournament_id,
             "kind": x.kind, "amount": x.amount, "balance_after": x.balance_after,
             "description": x.description, "created_at": x.created_at}
            for x in recent
        ],
        "platform_transactions": [
            {"transaction_id": x.transaction_id, "tournament_id": x.tournament_id, "kind": x.kind,
             "amount": x.amount, "balance_after": x.balance_after, "description": x.description, "created_at": x.created_at}
            for x in platform
        ]
    }

@router.post("/config")
def update_economy(data: EconomyConfigIn, db: Session = Depends(get_db), admin=Depends(require_admin)):
    current = db.scalar(select(EconomyState).where(EconomyState.id == 1))
    requested_supply = int((data.config or {}).get("supply",{}).get("autorizado", get_economy_config()["supply"]["autorizado"]))
    if current and requested_supply < int(current.minted_supply):
        raise HTTPException(409, f"O supply autorizado não pode ficar abaixo do supply já emitido ({current.minted_supply}).")
    cfg = save_economy_config(data.config)
    state = db.scalar(select(EconomyState).where(EconomyState.id == 1))
    if state:
        state.authorized_supply = int(cfg["supply"]["autorizado"])
        state.xp_rate = int(cfg["conversao"]["xp_por_farejador"])
        state.farejador_rate = int(cfg["conversao"]["farejadores_por_conversao"])
    else:
        state = EconomyState(id=1, authorized_supply=int(cfg["supply"]["autorizado"]), minted_supply=0,
                             xp_rate=int(cfg["conversao"]["xp_por_farejador"]), farejador_rate=int(cfg["conversao"]["farejadores_por_conversao"]))
        db.add(state)
    audit_action(db, admin.id, "economy_config_updated", reason="Configuração da economia alterada no painel de gestão de torneios",
                 metadata={"currency": cfg["moeda"]["nome"], "xp_rate": cfg["conversao"]["xp_por_farejador"]})
    db.commit()
    return {"ok": True, "config": cfg}
