import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.db.session import Base,engine,SessionLocal
from app.models import User
from app.core.security import hash_password
from app.services.tournaments import reconcile_all, sincronizar_torneios_configurados
from app.services.progression import ensure_achievements
from app.services.competitive import ensure_season, ensure_market
from app.api import auth,tournaments,account,ws,player,public,security,economy_admin

async def _tournament_worker(stop):
    while not stop.is_set():
        db=SessionLocal()
        try:
            reconcile_all(db)
            sincronizar_torneios_configurados(db)
        except Exception: db.rollback()
        finally: db.close()
        try: await asyncio.wait_for(stop.wait(),timeout=2.0)
        except asyncio.TimeoutError: pass

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine); db=SessionLocal(); ensure_achievements(db); stop=asyncio.Event(); task=None
    try:
        s=get_settings()
        if not db.query(User).filter(User.email==s.admin_email.lower()).first():
            db.add(User(email=s.admin_email.lower(),username="admin",password_hash=hash_password(s.admin_password),role="admin")); db.commit()
        ensure_season(db); ensure_market(db); sincronizar_torneios_configurados(db)
        task=asyncio.create_task(_tournament_worker(stop))
        yield
    finally:
        stop.set()
        if task: await task
        db.close()

s=get_settings(); app=FastAPI(title=s.app_name,version="2.0.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=s.cors_list,allow_credentials=True,allow_methods=["GET","POST","DELETE","OPTIONS"],allow_headers=["Authorization","Content-Type"])
app.include_router(auth.router,prefix="/api"); app.include_router(tournaments.router,prefix="/api"); app.include_router(account.router,prefix="/api"); app.include_router(player.router,prefix="/api"); app.include_router(public.router,prefix="/api"); app.include_router(ws.router); app.include_router(security.router,prefix="/api"); app.include_router(economy_admin.router,prefix="/api")
@app.get("/health")
def health(): return {"status":"ok","version":"2.0.0"}
