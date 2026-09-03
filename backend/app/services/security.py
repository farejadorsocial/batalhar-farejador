
import json
import ipaddress
import re
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    ActivityLog, ConnectionLog, DeviceProfile, PermissionState,
    SecurityAccount, SecurityAction, User, UserSession, Visitor
)

def now():
    return datetime.now(timezone.utc)

def client_ip(request):
    # Only trust forwarding headers when the deployment explicitly enables it.
    settings = get_settings()
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real = request.headers.get("X-Real-IP")
        if real:
            return real.strip()
    return request.client.host if request.client else None

def ip_type(ip):
    try:
        return "IPv6" if ipaddress.ip_address(ip).version == 6 else "IPv4"
    except ValueError:
        return None

def request_headers(request):
    return {
        "user_agent": request.headers.get("user-agent"),
        "referer": request.headers.get("referer"),
        "accept_language": request.headers.get("accept-language"),
        "sec_ch_ua": request.headers.get("sec-ch-ua"),
        "sec_ch_mobile": request.headers.get("sec-ch-ua-mobile"),
        "sec_ch_platform": request.headers.get("sec-ch-ua-platform"),
    }

def safe_json(value):
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return "{}"

def get_or_create_security_account(db, user_id):
    item = db.scalar(select(SecurityAccount).where(SecurityAccount.user_id == user_id))
    if not item:
        item = SecurityAccount(user_id=user_id)
        db.add(item)
        db.flush()
    return item

def ensure_active_account(db, user):
    state = get_or_create_security_account(db, user.id)
    if state.status == "active":
        user.is_active = True
        return state
    if state.status == "suspended" and state.suspended_until and state.suspended_until <= now():
        state.status = "active"
        state.suspended_until = None
        state.reason = None
        user.is_active = True
        db.flush()
        return state
    return state

def get_visitor(db, visitor_id=None):
    if not visitor_id:
        return None
    return db.scalar(select(Visitor).where(Visitor.visitor_id == visitor_id))

def upsert_visitor(db, visitor_id, request, client_data=None):
    item = get_visitor(db, visitor_id)
    data = client_data or {}
    if not item:
        item = Visitor(visitor_id=visitor_id or uuid.uuid4().hex)
        db.add(item)
        db.flush()
        item.first_path = request.url.path
        item.referer = request.headers.get("referer")
        item.source = data.get("utm_source")
        item.medium = data.get("utm_medium")
        item.campaign = data.get("utm_campaign")
        item.term = data.get("utm_term")
        item.content = data.get("utm_content")
    item.last_seen_at = now()
    item.last_path = request.url.path
    return item

def parse_browser(ua):
    ua = ua or ""
    browser, version = "Desconhecido", ""
    patterns = [
        ("Edge", r"Edg/([\d.]+)"),
        ("Opera", r"(?:OPR|Opera)/([\d.]+)"),
        ("Chrome", r"(?:Chrome|CriOS)/([\d.]+)"),
        ("Firefox", r"(?:Firefox|FxiOS)/([\d.]+)"),
        ("Safari", r"Version/([\d.]+).*Safari/"),
    ]
    for name, pattern in patterns:
        m = re.search(pattern, ua, re.I)
        if m:
            browser, version = name, m.group(1)
            break
    if re.search(r"Windows NT", ua, re.I): os_name = "Windows"
    elif re.search(r"Android", ua, re.I): os_name = "Android"
    elif re.search(r"iPhone|iPad|iPod", ua, re.I): os_name = "iOS"
    elif re.search(r"Mac OS X", ua, re.I): os_name = "macOS"
    elif re.search(r"Linux", ua, re.I): os_name = "Linux"
    else: os_name = "Desconhecido"
    platform = "mobile" if re.search(r"Mobile|Android|iPhone|iPad", ua, re.I) else "desktop"
    return browser, version, os_name, platform

def create_session(db, user, request, visitor=None, jti=None):
    ip = client_ip(request)
    h = request_headers(request)
    jti = jti or uuid.uuid4().hex
    session = UserSession(
        user_id=user.id, visitor_id=visitor.id if visitor else None,
        current_jti=jti, ip=ip, ip_type=ip_type(ip) if ip else None,
        **h
    )
    db.add(session)
    db.flush()
    return session, jti

def touch_session(db, session, request=None):
    session.last_seen_at = now()
    if request:
        ip = client_ip(request)
        if ip:
            session.ip = ip
            session.ip_type = ip_type(ip)
    db.flush()

def log_activity(db, event_type, request=None, user_id=None, session=None, visitor=None, metadata=None):
    ip = client_ip(request) if request else None
    db.add(ActivityLog(
        user_id=user_id,
        session_id=session.id if session else None,
        visitor_id=visitor.id if visitor else None,
        event_type=event_type,
        method=request.method if request else None,
        path=request.url.path if request else None,
        ip=ip,
        user_agent=request.headers.get("user-agent") if request else None,
        metadata_json=safe_json(metadata or {})
    ))

def parse_ipinfo(data):
    if not isinstance(data, dict):
        return {}

    # O IPInfo normalmente entrega a operadora no campo `org` no formato
    # "AS26615 TIM S/A". Mantemos o ASN separado do nome da operadora para
    # que o painel de segurança consiga exibir as duas informações.
    org = str(data.get("org") or data.get("isp") or "").strip()
    asn = str(data.get("asn") or "").strip() or None
    provider = str(data.get("isp") or "").strip() or None

    if org:
        match = re.match(r"^(AS\d+)\s+(.+)$", org, re.I)
        if match:
            asn = asn or match.group(1).upper()
            provider = provider or match.group(2).strip()
        else:
            provider = provider or org

    provider = provider or data.get("organization")
    return {
        "isp": provider,
        "organization": data.get("organization") or provider,
        "asn": asn,
        "country": data.get("country"),
        "region": data.get("region"),
        "city": data.get("city"),
        "timezone": data.get("timezone"),
    }

def is_public_ip(ip):
    try:
        return bool(ip) and ipaddress.ip_address(str(ip).strip()).is_global
    except ValueError:
        return False

def resolve_visitor_ip(request, public_ip=None):
    # Em produção, headers confiáveis do proxy têm prioridade.
    request_ip = client_ip(request)
    if is_public_ip(request_ip):
        return str(request_ip).strip()

    # No localhost/rede privada, usamos o IP público observado pelo navegador.
    candidate = str(public_ip or "").strip()
    if is_public_ip(candidate):
        return candidate

    return request_ip

def query_ipinfo(ip):
    if not ip:
        return {}
    try:
        import requests
        url = f"https://ipinfo.io/{ip}/json"
        r = requests.get(url, headers={"User-Agent": "BatalhaFarejador/2.0"}, timeout=get_settings().ipinfo_timeout_seconds)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def record_connection(db, user_id, session, visitor, ip, ipinfo=None):
    if not ip:
        return None
    parsed = parse_ipinfo(ipinfo or {})
    item = ConnectionLog(
        user_id=user_id,
        session_id=session.id if session else None,
        visitor_id=visitor.id if visitor else None,
        ip=ip, ip_type=ip_type(ip),
        ipinfo_json=safe_json(ipinfo or {}),
        **parsed
    )
    db.add(item)
    return item

def upsert_device(db, user_id, visitor, data):
    ua = data.get("user_agent")
    browser, version, os_name, platform = parse_browser(ua)
    device_id = str(data.get("device_id") or "").strip()
    if not device_id:
        device_id = uuid.uuid4().hex
    item = db.scalar(select(DeviceProfile).where(DeviceProfile.device_id == device_id))
    if not item:
        item = DeviceProfile(device_id=device_id, user_id=user_id, visitor_id=visitor.id if visitor else None)
        db.add(item)
    item.user_id = user_id or item.user_id
    item.visitor_id = visitor.id if visitor else item.visitor_id
    item.user_agent = ua
    item.browser = data.get("browser") or browser
    item.browser_version = data.get("browser_version") or version
    item.os = data.get("os") or os_name
    item.platform = data.get("platform") or platform
    item.device_model = data.get("device_model")
    item.language = data.get("language")
    item.timezone = data.get("timezone")
    item.screen_width = data.get("screen_width")
    item.screen_height = data.get("screen_height")
    item.pixel_ratio = str(data.get("pixel_ratio")) if data.get("pixel_ratio") is not None else None
    item.touch_support = data.get("touch_support")
    item.last_seen_at = now()
    db.flush()
    return item

def end_session(db, session, reason="logout"):
    session.status = "ended"
    session.ended_at = now()
    session.end_reason = reason
    db.flush()

def audit_action(db, admin_user_id, action, target_user_id=None, target_session_id=None, reason=None, metadata=None):
    db.add(SecurityAction(
        admin_user_id=admin_user_id, target_user_id=target_user_id,
        target_session_id=target_session_id, action=action,
        reason=reason, metadata_json=safe_json(metadata or {})
    ))


def calcular_risco_usuario(db, user_id):
    """Calcula risco operacional explicável usando somente sinais já coletados."""
    agora = datetime.now(timezone.utc)
    motivos = []
    score = 0

    sessoes = db.scalars(
        select(UserSession).where(UserSession.user_id == user_id)
    ).all()
    ativas = [x for x in sessoes if x.status == "active"]
    ips = {x.ip for x in sessoes if x.ip}
    dispositivos = db.scalars(
        select(DeviceProfile).where(DeviceProfile.user_id == user_id)
    ).all()
    atividades_recentes = db.scalars(
        select(ActivityLog).where(
            ActivityLog.user_id == user_id,
            ActivityLog.created_at >= agora - timedelta(minutes=10)
        ).order_by(desc(ActivityLog.created_at)).limit(200)
    ).all()

    if len(ativas) >= 3:
        score += 25
        motivos.append(f"{len(ativas)} sessões ativas simultaneamente")
    elif len(ativas) == 2:
        score += 8
        motivos.append("2 sessões ativas simultaneamente")

    if len(ips) >= 5:
        score += 25
        motivos.append(f"{len(ips)} IPs registrados")
    elif len(ips) >= 3:
        score += 12
        motivos.append(f"{len(ips)} IPs registrados")

    if len(dispositivos) >= 5:
        score += 20
        motivos.append(f"{len(dispositivos)} dispositivos conhecidos")
    elif len(dispositivos) >= 3:
        score += 10
        motivos.append(f"{len(dispositivos)} dispositivos conhecidos")

    if len(atividades_recentes) >= 80:
        score += 30
        motivos.append(f"{len(atividades_recentes)} eventos em 10 minutos")
    elif len(atividades_recentes) >= 40:
        score += 15
        motivos.append(f"{len(atividades_recentes)} eventos em 10 minutos")

    # Sinal de troca muito rápida de IP dentro das sessões recentes.
    ips_recentes = []
    for x in sorted(sessoes, key=lambda v: v.last_seen_at or v.created_at or agora, reverse=True)[:10]:
        if x.ip:
            ips_recentes.append(x.ip)
    if len(set(ips_recentes[:5])) >= 4:
        score += 15
        motivos.append("mudança frequente de IP nas sessões recentes")

    return {
        "score": min(score, 100),
        "level": "alto" if score >= 70 else "medio" if score >= 35 else "baixo",
        "reasons": motivos,
        "signals": {
            "active_sessions": len(ativas),
            "known_ips": len(ips),
            "known_devices": len(dispositivos),
            "events_last_10m": len(atividades_recentes),
        }
    }
