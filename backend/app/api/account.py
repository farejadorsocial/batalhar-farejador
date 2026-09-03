from pydantic import BaseModel,Field
from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import LedgerTransaction,PlatformLedgerTransaction
from app.services.economy import convert_xp,get_economy
from app.services.competitive import market_quote, ensure_market
router=APIRouter(prefix="/account",tags=["account"])
class ConvertIn(BaseModel): xp:int=Field(gt=0)
@router.get("/wallet")
def wallet(db:Session=Depends(get_db),user=Depends(get_current_user)):
    state=get_economy(db)
    return {"balance":user.balance,"points":user.points,"xp":user.xp,"level":user.level,"economy":{"authorized_supply":state.authorized_supply,"minted_supply":state.minted_supply,"available_supply":state.authorized_supply-state.minted_supply,"xp_rate":state.xp_rate,"farejador_rate":state.farejador_rate}}
@router.get("/ledger")
def ledger(db:Session=Depends(get_db),user=Depends(get_current_user)):
    return db.scalars(select(LedgerTransaction).where(LedgerTransaction.user_id==user.id).order_by(LedgerTransaction.created_at.desc()).limit(100)).all()
@router.post("/convert-xp")
def convert(data:ConvertIn,db:Session=Depends(get_db),user=Depends(get_current_user)):
    u=convert_xp(db,user.id,data.xp); state=get_economy(db)
    return {"balance":u.balance,"points":u.points,"xp":u.xp,"level":u.level,"economy":{"authorized_supply":state.authorized_supply,"minted_supply":state.minted_supply,"available_supply":state.authorized_supply-state.minted_supply,"xp_rate":state.xp_rate,"farejador_rate":state.farejador_rate}}

@router.get("/platform-ledger")
def platform_ledger(db:Session=Depends(get_db),user=Depends(get_current_user)):
    if user.role!="admin":
        from fastapi import HTTPException
        raise HTTPException(403,"Apenas administradores.")
    rows=db.scalars(select(PlatformLedgerTransaction).order_by(PlatformLedgerTransaction.id.desc()).limit(100)).all()
    return rows


@router.get("/farejador/quote")
def farejador_quote(db:Session=Depends(get_db), user=Depends(get_current_user)):
    return market_quote(db)

class MarketConfigIn(BaseModel):
    dynamic_pricing_enabled: bool = False
    min_xp_rate: int = Field(default=1000, ge=1, le=1000000)
    max_xp_rate: int = Field(default=1000000, ge=1, le=1000000)

@router.get("/market")
def market(db:Session=Depends(get_db), user=Depends(get_current_user)):
    return market_quote(db)

@router.post("/market/config")
def market_config(data:MarketConfigIn, db:Session=Depends(get_db), user=Depends(get_current_user)):
    if user.role!="admin":
        from fastapi import HTTPException
        raise HTTPException(403,"Apenas administradores.")
    if data.min_xp_rate > data.max_xp_rate:
        from fastapi import HTTPException
        raise HTTPException(400,"Limite mínimo não pode ser maior que o máximo.")
    m=ensure_market(db)
    m.dynamic_pricing_enabled=data.dynamic_pricing_enabled
    m.min_xp_rate=data.min_xp_rate
    m.max_xp_rate=data.max_xp_rate
    db.commit()
    return market_quote(db)
