
import jwt
from fastapi import Depends,HTTPException,Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import decode_token
from app.db.session import get_db
from app.models import User, UserSession
from app.services.security import ensure_active_account, touch_session

def get_current_user(request:Request,db:Session=Depends(get_db)):
    auth=request.headers.get("Authorization","")
    if not auth.startswith("Bearer "): raise HTTPException(401,"Autenticação necessária.")
    try:
        p=decode_token(auth[7:]); assert p.get("type")=="access"; uid=int(p["sub"])
    except (jwt.PyJWTError,ValueError,KeyError,AssertionError): raise HTTPException(401,"Token inválido ou expirado.")
    user=db.scalar(select(User).where(User.id==uid))
    if not user: raise HTTPException(401,"Usuário inválido ou desabilitado.")
    state=ensure_active_account(db,user)
    if state.status!="active":
        db.commit()
        raise HTTPException(403,f"Conta {state.status}.")
    sid=p.get("session_id")
    if sid:
        session=db.scalar(select(UserSession).where(UserSession.session_id==sid,UserSession.user_id==uid))
        if not session or session.status!="active":
            raise HTTPException(401,"Sessão encerrada.")
        touch_session(db,session,request)
    db.commit()
    return user

def require_admin(user=Depends(get_current_user)):
    if user.role!="admin": raise HTTPException(403,"Apenas administradores.")
    return user
