
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    ActivityLog, ConnectionLog, DeviceProfile, PermissionState,
    RefreshSession, SecurityAccount, SecurityAction, User, UserSession, Visitor
)
from app.services.security import (
    audit_action, client_ip, end_session, get_visitor, log_activity,
    record_connection, upsert_device, upsert_visitor, query_ipinfo, calcular_risco_usuario, resolve_visitor_ip
)
from .deps import get_current_user, require_admin

router=APIRouter(prefix="/security",tags=["security"])

ALLOWED_PERMISSIONS={"location","camera","microphone","notifications"}
ALLOWED_ACTIONS={"ban","suspend","disable","enable","unban","terminate_sessions","flag","unflag"}

class VisitorIn(BaseModel):
    public_ip: Optional[str]=Field(default=None,max_length=128)

class ClientContextIn(BaseModel):
    device_id: Optional[str]=Field(default=None,max_length=64)
    user_agent: Optional[str]=Field(default=None,max_length=4000)
    browser: Optional[str]=Field(default=None,max_length=80)
    browser_version: Optional[str]=Field(default=None,max_length=40)
    os: Optional[str]=Field(default=None,max_length=80)
    platform: Optional[str]=Field(default=None,max_length=80)
    device_model: Optional[str]=Field(default=None,max_length=120)
    language: Optional[str]=Field(default=None,max_length=80)
    timezone: Optional[str]=Field(default=None,max_length=100)
    screen_width: Optional[int]=Field(default=None,ge=1,le=20000)
    screen_height: Optional[int]=Field(default=None,ge=1,le=20000)
    pixel_ratio: Optional[float]=Field(default=None,ge=0.1,le=20)
    touch_support: Optional[bool]=None
    utm_source: Optional[str]=Field(default=None,max_length=120)
    utm_medium: Optional[str]=Field(default=None,max_length=120)
    utm_campaign: Optional[str]=Field(default=None,max_length=200)
    utm_term: Optional[str]=Field(default=None,max_length=200)
    utm_content: Optional[str]=Field(default=None,max_length=200)

class PermissionResult(BaseModel):
    state: str
    value: Optional[dict]=None

class PermissionRequestIn(BaseModel):
    permission: str

class ModerationIn(BaseModel):
    action: str
    reason: Optional[str]=Field(default=None,max_length=500)
    suspended_until: Optional[datetime]=None

def _visitor(db, request):
    return get_visitor(db, request.cookies.get("visitor_id"))

@router.post("/visitor")
def visitor(request:Request,response:Response,data:Optional[VisitorIn]=None,db:Session=Depends(get_db)):
    vid=request.cookies.get("visitor_id")
    if not vid:
        vid=uuid.uuid4().hex
        response.set_cookie("visitor_id",vid,httponly=True,secure=False,samesite="lax",max_age=60*60*24*365,path="/")
    v=upsert_visitor(db,vid,request)
    log_activity(db,"page_visit",request,visitor=v)

    # Registra a origem de conexão do visitante sem exigir autenticação.
    # Evita duplicação excessiva para o mesmo IP em uma janela curta.
    ip=resolve_visitor_ip(request, data.public_ip if data else None)
    if ip:
        recent=db.scalar(select(ConnectionLog).where(
            ConnectionLog.visitor_id==v.id,
            ConnectionLog.ip==ip,
            ConnectionLog.created_at>=datetime.now(timezone.utc)-timedelta(minutes=5)
        ).order_by(desc(ConnectionLog.created_at)).limit(1))
        if not recent:
            record_connection(db,None,None,v,ip,query_ipinfo(ip))

    db.commit()
    return {"visitor_id":vid}

@router.post("/visitor-context")
def visitor_context(data:ClientContextIn,request:Request,db:Session=Depends(get_db)):
    v=_visitor(db,request)
    if not v:
        raise HTTPException(400,"Visitante não identificado.")
    device=upsert_device(db,None,v,data.model_dump())
    log_activity(db,"visitor_context",request,visitor=v,metadata={
        "device_id":device.device_id,
        "screen_width":data.screen_width,"screen_height":data.screen_height,
        "timezone":data.timezone
    })
    db.commit()
    return {"ok":True,"device_id":device.device_id}

@router.post("/client-context")
def client_context(data:ClientContextIn,request:Request,db:Session=Depends(get_db),user=Depends(get_current_user)):
    v=_visitor(db,request)
    device=upsert_device(db,user.id,v,data.model_dump())
    session=None
    auth=request.headers.get("Authorization","")
    if auth.startswith("Bearer "):
        try:
            import jwt
            from app.core.security import decode_token
            payload=decode_token(auth[7:])
            session=db.scalar(select(UserSession).where(UserSession.session_id==payload.get("session_id"),UserSession.user_id==user.id))
        except Exception: pass
    if session:
        session.last_seen_at=datetime.now(timezone.utc)
        if v and not session.visitor_id: session.visitor_id=v.id
    log_activity(db,"client_context",request,user.id,session,v,{
        "device_id":device.device_id,
        "screen_width":data.screen_width,"screen_height":data.screen_height,
        "timezone":data.timezone
    })
    db.commit()
    return {"ok":True,"device_id":device.device_id}

@router.get("/permissions/pending")
def permissions_pending(db:Session=Depends(get_db),user=Depends(get_current_user)):
    rows=db.scalars(select(PermissionState).where(
        PermissionState.user_id==user.id,PermissionState.state=="requested"
    ).order_by(PermissionState.requested_at.desc())).all()
    return [{"permission":x.permission,"request_id":x.request_id,"requested_at":x.requested_at} for x in rows]

@router.post("/permissions/{permission}/resolve",response_model=PermissionResult)
def resolve_permission(permission:str,data:PermissionResult,request:Request,db:Session=Depends(get_db),user=Depends(get_current_user)):
    if permission not in ALLOWED_PERMISSIONS: raise HTTPException(400,"Permissão não suportada.")
    row=db.scalar(select(PermissionState).where(PermissionState.user_id==user.id,PermissionState.permission==permission))
    if not row: raise HTTPException(404,"Solicitação não encontrada.")
    if data.state not in {"granted","denied","prompt","unknown"}: raise HTTPException(400,"Estado inválido.")
    row.state=data.state
    row.resolved_at=datetime.now(timezone.utc)
    row.value_json=json.dumps(data.value or {},ensure_ascii=False)
    log_activity(db,"permission_resolved",request,user.id,metadata={"permission":permission,"state":data.state})
    db.commit()
    return data

@router.get("/permissions")
def permissions(db:Session=Depends(get_db),user=Depends(get_current_user)):
    rows=db.scalars(select(PermissionState).where(PermissionState.user_id==user.id)).all()
    return [{"permission":x.permission,"state":x.state,"requested_at":x.requested_at,"resolved_at":x.resolved_at,
             "value":json.loads(x.value_json or "{}")} for x in rows]


@router.get("/admin/visitors")
def admin_visitors(limit:int=200,db:Session=Depends(get_db),admin=Depends(require_admin)):
    limit=max(1,min(limit,500))
    rows=db.scalars(select(Visitor).order_by(desc(Visitor.last_seen_at)).limit(limit)).all()
    out=[]
    for v in rows:
        latest=db.scalar(select(ActivityLog).where(ActivityLog.visitor_id==v.id).order_by(desc(ActivityLog.created_at)).limit(1))
        conn=db.scalar(select(ConnectionLog).where(ConnectionLog.visitor_id==v.id).order_by(desc(ConnectionLog.created_at)).limit(1))
        device=db.scalar(select(DeviceProfile).where(DeviceProfile.visitor_id==v.id).order_by(desc(DeviceProfile.last_seen_at)).limit(1))
        out.append({
            "id":v.id,"visitor_id":v.visitor_id,"first_seen_at":v.first_seen_at,"last_seen_at":v.last_seen_at,
            "first_path":v.first_path,"last_path":v.last_path,"referer":v.referer,
            "source":v.source,"medium":v.medium,"campaign":v.campaign,"term":v.term,"content":v.content,
            "ip":conn.ip if conn else (latest.ip if latest else None),
            "ip_type":conn.ip_type if conn else None,
            "isp":conn.isp if conn else None,"organization":conn.organization if conn else None,
            "asn":conn.asn if conn else None,"country":conn.country if conn else None,
            "region":conn.region if conn else None,"city":conn.city if conn else None,
            "timezone":conn.timezone if conn else None,
            "user_agent":latest.user_agent if latest else (device.user_agent if device else None),
            "browser":device.browser if device else None,"browser_version":device.browser_version if device else None,
            "os":device.os if device else None,"platform":device.platform if device else None,
            "device_model":device.device_model if device else None,
            "screen_width":device.screen_width if device else None,"screen_height":device.screen_height if device else None,
            "language":device.language if device else None
        })
    return out

@router.get("/admin/visitors/{visitor_id}")
def admin_visitor_detail(visitor_id:str,db:Session=Depends(get_db),admin=Depends(require_admin)):
    v=db.scalar(select(Visitor).where(Visitor.visitor_id==visitor_id))
    if not v: raise HTTPException(404,"Visitante não encontrado.")
    activities=db.scalars(select(ActivityLog).where(ActivityLog.visitor_id==v.id).order_by(desc(ActivityLog.created_at)).limit(300)).all()
    connections=db.scalars(select(ConnectionLog).where(ConnectionLog.visitor_id==v.id).order_by(desc(ConnectionLog.created_at)).limit(100)).all()
    devices=db.scalars(select(DeviceProfile).where(DeviceProfile.visitor_id==v.id).order_by(desc(DeviceProfile.last_seen_at))).all()
    users=db.scalars(select(User).where(User.id.in_({x.user_id for x in connections if x.user_id}))).all() if any(x.user_id for x in connections) else []
    user_map={u.id:u.username for u in users}
    return {
        "visitor":{
            "id":v.id,"visitor_id":v.visitor_id,"first_seen_at":v.first_seen_at,"last_seen_at":v.last_seen_at,
            "first_path":v.first_path,"last_path":v.last_path,"referer":v.referer,
            "source":v.source,"medium":v.medium,"campaign":v.campaign,"term":v.term,"content":v.content
        },
        "connections":[{
            "id":x.id,"ip":x.ip,"ip_type":x.ip_type,"isp":x.isp,"organization":x.organization,"asn":x.asn,
            "country":x.country,"region":x.region,"city":x.city,"timezone":x.timezone,
            "user_id":x.user_id,"username":user_map.get(x.user_id),"created_at":x.created_at
        } for x in connections],
        "devices":[{
            "id":x.id,"device_id":x.device_id,"browser":x.browser,"browser_version":x.browser_version,
            "os":x.os,"platform":x.platform,"device_model":x.device_model,"language":x.language,
            "timezone":x.timezone,"screen_width":x.screen_width,"screen_height":x.screen_height,
            "pixel_ratio":x.pixel_ratio,"touch_support":x.touch_support,
            "user_id":x.user_id,"created_at":x.first_seen_at,"last_seen_at":x.last_seen_at
        } for x in devices],
        "activities":[{
            "id":x.id,"event_type":x.event_type,"method":x.method,"path":x.path,"ip":x.ip,
            "user_agent":x.user_agent,"metadata":json.loads(x.metadata_json or "{}"),"created_at":x.created_at,
            "user_id":x.user_id,"username":user_map.get(x.user_id)
        } for x in activities],
        "latest":{
            "ip":connections[0].ip if connections else (activities[0].ip if activities else None),
            "ip_type":connections[0].ip_type if connections else None,
            "isp":connections[0].isp if connections else None,
            "organization":connections[0].organization if connections else None,
            "asn":connections[0].asn if connections else None,
            "country":connections[0].country if connections else None,
            "region":connections[0].region if connections else None,
            "city":connections[0].city if connections else None,
            "timezone":connections[0].timezone if connections else None,
            "user_agent":activities[0].user_agent if activities else None
        }
    }

@router.get("/admin/dashboard")
def admin_dashboard(db:Session=Depends(get_db),admin=Depends(require_admin)):
    """Resumo operacional para o centro de monitoramento."""
    now_utc=datetime.now(timezone.utc)
    users_total=db.scalar(select(func.count(User.id))) or 0
    online=db.scalar(select(func.count(UserSession.id)).where(UserSession.status=="active")) or 0
    visitors=db.scalar(select(func.count(Visitor.id))) or 0
    flagged=db.scalar(select(func.count(SecurityAccount.id)).where(SecurityAccount.flagged.is_(True))) or 0
    banned=db.scalar(select(func.count(SecurityAccount.id)).where(SecurityAccount.status=="banned")) or 0
    suspended=db.scalar(select(func.count(SecurityAccount.id)).where(SecurityAccount.status=="suspended")) or 0
    disabled=db.scalar(select(func.count(SecurityAccount.id)).where(SecurityAccount.status=="disabled")) or 0
    recent=db.scalars(select(ActivityLog).order_by(desc(ActivityLog.created_at)).limit(15)).all()
    active_sessions=db.scalars(select(UserSession).where(UserSession.status=="active").order_by(desc(UserSession.last_seen_at)).limit(12)).all()
    alerts=db.scalars(select(SecurityAccount).where(SecurityAccount.flagged.is_(True)).order_by(desc(SecurityAccount.updated_at)).limit(8)).all()
    # Risco é recalculado a partir dos sinais atuais; não depende de um ban automático.
    risk_users=[]
    for u in db.scalars(select(User)).all():
        risk=calcular_risco_usuario(db,u.id)
        if risk["score"] >= 35:
            risk_users.append((u,risk))
    risk_users.sort(key=lambda x:x[1]["score"], reverse=True)
    user_ids={x.user_id for x in active_sessions}
    names={}
    if user_ids:
        for u in db.scalars(select(User).where(User.id.in_(user_ids))).all(): names[u.id]=u.username
    alert_ids={x.user_id for x in alerts}
    if alert_ids:
        for u in db.scalars(select(User).where(User.id.in_(alert_ids))).all(): names[u.id]=u.username
    for u,_risk in risk_users[:8]:
        names[u.id]=u.username
    def activity_row(x):
        return {"id":x.id,"event_type":x.event_type,"user_id":x.user_id,"username":names.get(x.user_id),
                "session_id":x.session_id,"visitor_id":x.visitor_id,"ip":x.ip,"path":x.path,
                "created_at":x.created_at,"metadata":json.loads(x.metadata_json or "{}")}
    return {
        "generated_at":now_utc,
        "metrics":{"users":users_total,"online":online,"sessions":online,"visitors":visitors,
                   "flagged":flagged,"banned":banned,"suspended":suspended,"disabled":disabled},
        "health":{"status":"online","database":"online"},
        "recent_activities":[activity_row(x) for x in recent],
        "active_sessions":[{"id":x.id,"session_id":x.session_id,"user_id":x.user_id,"username":names.get(x.user_id),
                            "ip":x.ip,"ip_type":x.ip_type,"user_agent":x.user_agent,
                            "created_at":x.created_at,"last_seen_at":x.last_seen_at} for x in active_sessions],
        "alerts":[
            {"user_id":u.id,"username":u.username,"risk_score":risk["score"],
             "status":(db.scalar(select(SecurityAccount).where(SecurityAccount.user_id==u.id)).status
                       if db.scalar(select(SecurityAccount).where(SecurityAccount.user_id==u.id)) else "active"),
             "reason":"; ".join(risk["reasons"]) if risk["reasons"] else "Sinais operacionais acima do normal",
             "reasons":risk["reasons"],"signals":risk["signals"]}
            for u,risk in risk_users[:8]
        ] + [
            {"user_id":x.user_id,"username":names.get(x.user_id),"risk_score":x.risk_score,
             "status":x.status,"reason":x.reason,"reasons":[x.reason] if x.reason else [],
             "signals":{},"updated_at":x.updated_at}
            for x in alerts if x.user_id not in {u.id for u,_ in risk_users[:8]}
        ],
    }

@router.get("/admin/sessions")
def admin_sessions(db:Session=Depends(get_db),admin=Depends(require_admin)):
    rows=db.scalars(select(UserSession).order_by(desc(UserSession.last_seen_at)).limit(300)).all()
    ids={x.user_id for x in rows}
    users={u.id:u for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}
    return [{"id":x.id,"session_id":x.session_id,"user_id":x.user_id,"username":users.get(x.user_id).username if x.user_id in users else None,
             "status":x.status,"ip":x.ip,"ip_type":x.ip_type,"user_agent":x.user_agent,
             "created_at":x.created_at,"last_seen_at":x.last_seen_at,"ended_at":x.ended_at,"end_reason":x.end_reason}
            for x in rows]

@router.get("/admin/activities")
def admin_activities(limit:int=100,db:Session=Depends(get_db),admin=Depends(require_admin)):
    limit=max(1,min(limit,500))
    rows=db.scalars(select(ActivityLog).order_by(desc(ActivityLog.created_at)).limit(limit)).all()
    ids={x.user_id for x in rows if x.user_id}
    users={u.id:u.username for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}
    return [{"id":x.id,"event_type":x.event_type,"user_id":x.user_id,"username":users.get(x.user_id),
             "session_id":x.session_id,"visitor_id":x.visitor_id,"method":x.method,"path":x.path,"ip":x.ip,
             "user_agent":x.user_agent,"metadata":json.loads(x.metadata_json or "{}"),"created_at":x.created_at} for x in rows]

@router.get("/admin/connections")
def admin_connections(limit:int=150,db:Session=Depends(get_db),admin=Depends(require_admin)):
    limit=max(1,min(limit,500))
    rows=db.scalars(select(ConnectionLog).order_by(desc(ConnectionLog.created_at)).limit(limit)).all()
    ids={x.user_id for x in rows if x.user_id}
    users={u.id:u.username for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}
    return [{"id":x.id,"user_id":x.user_id,"username":users.get(x.user_id),"ip":x.ip,"ip_type":x.ip_type,
             "isp":x.isp,"organization":x.organization,"asn":x.asn,"country":x.country,"region":x.region,
             "city":x.city,"timezone":x.timezone,"created_at":x.created_at} for x in rows]

@router.get("/admin/devices")
def admin_devices(db:Session=Depends(get_db),admin=Depends(require_admin)):
    rows=db.scalars(select(DeviceProfile).order_by(desc(DeviceProfile.last_seen_at)).limit(300)).all()
    ids={x.user_id for x in rows if x.user_id}
    users={u.id:u.username for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}
    return [{"id":x.id,"device_id":x.device_id,"user_id":x.user_id,"username":users.get(x.user_id),
             "browser":x.browser,"browser_version":x.browser_version,"os":x.os,"platform":x.platform,
             "device_model":x.device_model,"language":x.language,"timezone":x.timezone,
             "screen_width":x.screen_width,"screen_height":x.screen_height,"pixel_ratio":x.pixel_ratio,
             "touch_support":x.touch_support,"first_seen_at":x.first_seen_at,"last_seen_at":x.last_seen_at} for x in rows]

@router.get("/admin/actions")
def admin_actions(limit:int=100,db:Session=Depends(get_db),admin=Depends(require_admin)):
    limit=max(1,min(limit,500))
    rows=db.scalars(select(SecurityAction).order_by(desc(SecurityAction.created_at)).limit(limit)).all()
    ids={x.admin_user_id for x in rows if x.admin_user_id}|{x.target_user_id for x in rows if x.target_user_id}
    users={u.id:u.username for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}
    return [{"id":x.id,"action":x.action,"reason":x.reason,"admin_user_id":x.admin_user_id,
             "admin_username":users.get(x.admin_user_id),"target_user_id":x.target_user_id,
             "target_username":users.get(x.target_user_id),"target_session_id":x.target_session_id,
             "metadata":json.loads(x.metadata_json or "{}"),"created_at":x.created_at} for x in rows]

@router.get("/admin/security/intelligence")
def admin_security_intelligence(db:Session=Depends(get_db),admin=Depends(require_admin)):
    """Correla IPs e dispositivos compartilhados sem transformar um sinal isolado em punição."""
    users=db.scalars(select(User).order_by(User.id)).all()
    user_map={u.id:u for u in users}
    ip_users={}
    for x in db.scalars(select(ConnectionLog).where(ConnectionLog.user_id.is_not(None)).order_by(desc(ConnectionLog.created_at)).limit(3000)).all():
        ip_users.setdefault(x.ip,set()).add(x.user_id)
    device_users={}
    for x in db.scalars(select(DeviceProfile).where(DeviceProfile.user_id.is_not(None))).all():
        device_users.setdefault(x.device_id,set()).add(x.user_id)

    shared_ips=[]
    for ip,ids in ip_users.items():
        if len(ids)>=2:
            shared_ips.append({"ip":ip,"users":[{"id":i,"username":user_map[i].username} for i in sorted(ids) if i in user_map],"user_count":len(ids)})
    shared_devices=[]
    for device,ids in device_users.items():
        if len(ids)>=2:
            shared_devices.append({"device_id":device,"users":[{"id":i,"username":user_map[i].username} for i in sorted(ids) if i in user_map],"user_count":len(ids)})
    risks=[]
    for u in users:
        r=calcular_risco_usuario(db,u.id)
        if r["score"]>=1:
            risks.append({"user_id":u.id,"username":u.username,"score":r["score"],"level":r["level"],"reasons":r["reasons"],"signals":r["signals"]})
    risks.sort(key=lambda x:x["score"],reverse=True)
    return {"generated_at":datetime.now(timezone.utc),"risk_users":risks[:50],
            "shared_ips":sorted(shared_ips,key=lambda x:x["user_count"],reverse=True)[:50],
            "shared_devices":sorted(shared_devices,key=lambda x:x["user_count"],reverse=True)[:50]}

@router.get("/admin/overview")
def admin_overview(db:Session=Depends(get_db),admin=Depends(require_admin)):
    users=db.scalar(select(__import__("sqlalchemy").func.count(User.id))) or 0
    active_sessions=db.scalar(select(__import__("sqlalchemy").func.count(UserSession.id)).where(UserSession.status=="active")) or 0
    visitors=db.scalar(select(__import__("sqlalchemy").func.count(Visitor.id))) or 0
    flagged=db.scalar(select(__import__("sqlalchemy").func.count(SecurityAccount.id)).where(SecurityAccount.flagged.is_(True))) or 0
    return {"users":users,"active_sessions":active_sessions,"visitors":visitors,"flagged_accounts":flagged}

@router.get("/admin/users")
def admin_users(db:Session=Depends(get_db),admin=Depends(require_admin)):
    rows=db.execute(select(User,SecurityAccount).outerjoin(SecurityAccount,SecurityAccount.user_id==User.id).order_by(desc(User.created_at))).all()
    out=[]
    for u,state in rows:
        risk=calcular_risco_usuario(db,u.id)
        out.append({"id":u.id,"email":u.email,"username":u.username,"role":u.role,"is_active":u.is_active,
                    "status":state.status if state else "active","reason":state.reason if state else None,
                    "risk_score":max(state.risk_score if state else 0,risk["score"]),
                    "risk_level":risk["level"],"risk_reasons":risk["reasons"],
                    "flagged":state.flagged if state else False,
                    "created_at":u.created_at})
    return out

@router.get("/admin/users/{user_id}")
def admin_user_detail(user_id:int,db:Session=Depends(get_db),admin=Depends(require_admin)):
    u=db.get(User,user_id)
    if not u: raise HTTPException(404,"Usuário não encontrado.")
    state=db.scalar(select(SecurityAccount).where(SecurityAccount.user_id==user_id))
    sessions=db.scalars(select(UserSession).where(UserSession.user_id==user_id).order_by(desc(UserSession.last_seen_at))).all()
    connections=db.scalars(select(ConnectionLog).where(ConnectionLog.user_id==user_id).order_by(desc(ConnectionLog.created_at)).limit(100)).all()
    activities=db.scalars(select(ActivityLog).where(ActivityLog.user_id==user_id).order_by(desc(ActivityLog.created_at)).limit(200)).all()
    devices=db.scalars(select(DeviceProfile).where(DeviceProfile.user_id==user_id).order_by(desc(DeviceProfile.last_seen_at))).all()
    permissions=db.scalars(select(PermissionState).where(PermissionState.user_id==user_id)).all()
    actions=db.scalars(select(SecurityAction).where(SecurityAction.target_user_id==user_id).order_by(desc(SecurityAction.created_at)).limit(100)).all()
    risk=calcular_risco_usuario(db,user_id)
    return {
        "user":{"id":u.id,"email":u.email,"username":u.username,"role":u.role,"is_active":u.is_active,"created_at":u.created_at},
        "security":{"status":state.status if state else "active","reason":state.reason if state else None,
                    "risk_score":max(state.risk_score if state else 0,risk["score"]),
                    "risk_level":risk["level"],"risk_reasons":risk["reasons"],"risk_signals":risk["signals"],
                    "flagged":state.flagged if state else False},
        "sessions":[{"id":x.id,"session_id":x.session_id,"status":x.status,"created_at":x.created_at,"last_seen_at":x.last_seen_at,
                     "ended_at":x.ended_at,"end_reason":x.end_reason,"ip":x.ip,"ip_type":x.ip_type,"user_agent":x.user_agent} for x in sessions],
        "connections":[{"id":x.id,"ip":x.ip,"ip_type":x.ip_type,"isp":x.isp,"organization":x.organization,"asn":x.asn,
                       "country":x.country,"region":x.region,"city":x.city,"timezone":x.timezone,"created_at":x.created_at} for x in connections],
        "devices":[{"device_id":x.device_id,"browser":x.browser,"browser_version":x.browser_version,"os":x.os,
                    "platform":x.platform,"device_model":x.device_model,"language":x.language,"timezone":x.timezone,
                    "screen_width":x.screen_width,"screen_height":x.screen_height,"pixel_ratio":x.pixel_ratio,
                    "touch_support":x.touch_support,"first_seen_at":x.first_seen_at,"last_seen_at":x.last_seen_at} for x in devices],
        "activities":[{"id":x.id,"event_type":x.event_type,"method":x.method,"path":x.path,"ip":x.ip,
                       "metadata":json.loads(x.metadata_json or "{}"),"created_at":x.created_at} for x in activities],
        "permissions":[{"permission":x.permission,"state":x.state,"requested_at":x.requested_at,"resolved_at":x.resolved_at,
                        "value":json.loads(x.value_json or "{}")} for x in permissions],
        "actions":[{"action":x.action,"reason":x.reason,"admin_user_id":x.admin_user_id,"created_at":x.created_at} for x in actions],
    }

@router.post("/admin/users/{user_id}/action")
def admin_action(user_id:int,data:ModerationIn,db:Session=Depends(get_db),admin=Depends(require_admin)):
    if data.action not in ALLOWED_ACTIONS: raise HTTPException(400,"Ação inválida.")
    if user_id==admin.id and data.action in {"ban","disable","suspend"}:
        raise HTTPException(400,"O administrador atual não pode desabilitar a própria conta.")
    u=db.get(User,user_id)
    if not u: raise HTTPException(404,"Usuário não encontrado.")
    state=db.scalar(select(SecurityAccount).where(SecurityAccount.user_id==user_id))
    if not state:
        state=SecurityAccount(user_id=user_id); db.add(state); db.flush()
    if data.action=="ban":
        state.status="banned"; state.reason=data.reason
        u.is_active=False
    elif data.action=="disable":
        state.status="disabled"; state.reason=data.reason
        u.is_active=False
    elif data.action=="suspend":
        state.status="suspended"; state.reason=data.reason; state.suspended_until=data.suspended_until
        u.is_active=False
    elif data.action in {"enable","unban"}:
        state.status="active"; state.reason=None; state.suspended_until=None
        u.is_active=True
    elif data.action=="flag": state.flagged=True; state.reason=data.reason
    elif data.action=="unflag": state.flagged=False
    elif data.action=="terminate_sessions":
        for session in db.scalars(select(UserSession).where(UserSession.user_id==user_id,UserSession.status=="active")).all():
            end_session(db,session,"admin_terminate")
            rs=db.scalar(select(RefreshSession).where(RefreshSession.jti==session.current_jti))
            if rs: rs.revoked=True
    audit_action(db,admin.id,data.action,target_user_id=user_id,reason=data.reason)
    log_activity(db,"admin_action",user_id=admin.id,metadata={"target_user_id":user_id,"action":data.action})
    db.commit()
    return {"ok":True,"user_id":user_id,"action":data.action}

@router.post("/admin/users/{user_id}/permission-request")
def admin_permission_request(user_id:int,data:PermissionRequestIn,db:Session=Depends(get_db),admin=Depends(require_admin)):
    if data.permission not in ALLOWED_PERMISSIONS: raise HTTPException(400,"Permissão não suportada.")
    u=db.get(User,user_id)
    if not u: raise HTTPException(404,"Usuário não encontrado.")
    row=db.scalar(select(PermissionState).where(PermissionState.user_id==user_id,PermissionState.permission==data.permission))
    if not row:
        row=PermissionState(user_id=user_id,permission=data.permission)
        db.add(row)
    row.state="requested"; row.requested_at=datetime.now(timezone.utc); row.resolved_at=None; row.request_id=uuid.uuid4().hex
    audit_action(db,admin.id,"request_permission",target_user_id=user_id,reason=data.permission)
    db.commit()
    return {"ok":True,"permission":data.permission,"request_id":row.request_id}

@router.post("/admin/sessions/{session_id}/terminate")
def admin_terminate_session(session_id:int,db:Session=Depends(get_db),admin=Depends(require_admin)):
    session=db.get(UserSession,session_id)
    if not session: raise HTTPException(404,"Sessão não encontrada.")
    if session.status=="active":
        end_session(db,session,"admin_terminate")
        rs=db.scalar(select(RefreshSession).where(RefreshSession.jti==session.current_jti))
        if rs: rs.revoked=True
    audit_action(db,admin.id,"terminate_session",target_user_id=session.user_id,target_session_id=session.id)
    db.commit()
    return {"ok":True}
