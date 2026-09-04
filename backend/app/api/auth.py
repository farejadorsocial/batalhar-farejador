
from typing import Optional
from datetime import datetime,timedelta,timezone
import jwt
import uuid
from fastapi import APIRouter,Cookie,Depends,HTTPException,Request,Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import *
from app.db.session import get_db
from app.models import RefreshSession,User,UserSession
from app.schemas.auth import *
from app.services.security import (
    client_ip, create_session, end_session, get_visitor, log_activity,
    query_ipinfo, record_connection, ensure_active_account, upsert_visitor
)
from .deps import get_current_user

router=APIRouter(prefix="/auth",tags=["auth"])

def _aware(dt):
    if dt is None: return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def cookie(response,token):
    s=get_settings()
    # O frontend e a API usam subdomínios diferentes do Render. Em produção,
    # o cookie de refresh precisa aceitar requisições autenticadas entre essas
    # origens. Em desenvolvimento, mantemos Lax para não quebrar HTTP local.
    same_site="none" if s.cookie_secure else "lax"
    response.set_cookie("refresh_token",token,httponly=True,secure=s.cookie_secure,
                        samesite=same_site,max_age=s.refresh_token_days*86400,path="/api/auth")

def _visitor_from_cookie(db, request):
    return get_visitor(db, request.cookies.get("visitor_id"))

def _ensure_visitor(db, request, response):
    vid=request.cookies.get("visitor_id")
    if not vid:
        vid=uuid.uuid4().hex
        response.set_cookie("visitor_id",vid,httponly=True,secure=get_settings().cookie_secure,
                            samesite="lax",max_age=60*60*24*365,path="/")
    return upsert_visitor(db,vid,request)

def _open_session(db, user, request, visitor):
    refresh,jti=create_refresh_token(user.id)
    session,_=create_session(db,user,request,visitor,jti=jti)
    db.add(RefreshSession(jti=jti,user_id=user.id,
        expires_at=datetime.now(timezone.utc)+timedelta(days=get_settings().refresh_token_days)))
    ip=client_ip(request)
    ipinfo=query_ipinfo(ip) if ip else {}
    record_connection(db,user.id,session,visitor,ip,ipinfo)
    return refresh,session

@router.post("/register",response_model=TokenOut)
def register(data:RegisterIn,response:Response,request:Request,db:Session=Depends(get_db)):
    email=data.email.lower().strip(); username=data.username.strip()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,"E-mail já cadastrado.")
    if db.scalar(select(User).where(User.username==username)): raise HTTPException(409,"Nome de usuário já cadastrado.")
    u=User(email=email,username=username,password_hash=hash_password(data.password))
    db.add(u); db.flush()
    ensure_active_account(db,u)
    visitor=_ensure_visitor(db,request,response)
    refresh,session=_open_session(db,u,request,visitor)
    log_activity(db,"register",request,u.id,session,visitor)
    db.commit()
    cookie(response,refresh)
    return TokenOut(access_token=create_access_token(u.id,session.session_id),user=u)

@router.post("/login",response_model=TokenOut)
def login(data:LoginIn,response:Response,request:Request,db:Session=Depends(get_db)):
    email=str(data.email).strip().lower()
    u=db.scalar(select(User).where(User.email==email))
    if not u or not verify_password(data.password,u.password_hash): raise HTTPException(401,"E-mail ou senha inválidos.")
    state=ensure_active_account(db,u)
    if not u.is_active or state.status!="active":
        db.commit()
        raise HTTPException(403,f"Conta {state.status}.")
    visitor=_ensure_visitor(db,request,response)
    refresh,session=_open_session(db,u,request,visitor)
    log_activity(db,"login",request,u.id,session,visitor)
    db.commit()
    cookie(response,refresh)
    return TokenOut(access_token=create_access_token(u.id,session.session_id),user=u)

@router.post("/refresh",response_model=TokenOut)
def refresh(request:Request,response:Response,refresh_token:Optional[str]=Cookie(None),db:Session=Depends(get_db)):
    if not refresh_token: raise HTTPException(401,"Sessão ausente.")
    try:
        p=decode_token(refresh_token); assert p.get("type")=="refresh"; uid=int(p["sub"]); jti=p["jti"]
    except Exception: raise HTTPException(401,"Refresh token inválido.")
    s=db.scalar(select(RefreshSession).where(RefreshSession.jti==jti,RefreshSession.user_id==uid))
    session=db.scalar(select(UserSession).where(UserSession.current_jti==jti,UserSession.user_id==uid))
    u=db.scalar(select(User).where(User.id==uid))
    if not s or s.revoked or _aware(s.expires_at)<datetime.now(timezone.utc) or not session or session.status!="active" or not u:
        raise HTTPException(401,"Sessão expirada.")
    state=ensure_active_account(db,u)
    if not u.is_active or state.status!="active":
        db.commit(); raise HTTPException(403,f"Conta {state.status}.")
    s.revoked=True
    r,njti=create_refresh_token(uid)
    db.add(RefreshSession(jti=njti,user_id=uid,
        expires_at=datetime.now(timezone.utc)+timedelta(days=get_settings().refresh_token_days)))
    session.current_jti=njti
    session.last_seen_at=datetime.now(timezone.utc)
    log_activity(db,"session_refresh",request,uid,session)
    db.commit()
    cookie(response,r)
    return TokenOut(access_token=create_access_token(uid,session.session_id),user=u)

@router.post("/logout")
def logout(request:Request,response:Response,refresh_token:Optional[str]=Cookie(None),db:Session=Depends(get_db)):
    if refresh_token:
        try:
            p=decode_token(refresh_token)
            s=db.scalar(select(RefreshSession).where(RefreshSession.jti==p.get("jti")))
            session=db.scalar(select(UserSession).where(UserSession.current_jti==p.get("jti")))
            if s: s.revoked=True
            if session:
                end_session(db,session,"logout")
                log_activity(db,"logout",request,session.user_id,session)
            db.commit()
        except jwt.PyJWTError: pass
    response.delete_cookie("refresh_token",path="/api/auth")
    return {"message":"Sessão encerrada."}

@router.get("/me",response_model=UserOut)
def me(user=Depends(get_current_user)): return user
