"""
Teste rápido do backend da Batalha de Farejador.
Execute com a API rodando em http://127.0.0.1:8010:
    python backend/test_api.py
"""
import sys, uuid
from urllib.request import Request, urlopen
from http.cookiejar import CookieJar
import urllib.error, json

BASE="http://127.0.0.1:8010"
jar=CookieJar()
import urllib.request
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def call(path, method="GET", data=None, token=None):
    body=json.dumps(data).encode() if data is not None else None
    headers={"Content-Type":"application/json"} if data is not None else {}
    if token: headers["Authorization"]="Bearer "+token
    r=opener.open(Request(BASE+path,data=body,headers=headers,method=method))
    return r.status, json.loads(r.read().decode())

email=f"teste_{uuid.uuid4().hex[:8]}@local.test"
username=f"teste_{uuid.uuid4().hex[:8]}"
status,d=call("/api/auth/register","POST",{"email":email,"username":username,"password":"SenhaTeste12345!"})
assert status==200
token=d["access_token"]
call("/api/auth/logout","POST")
status,d=call("/api/auth/login","POST",{"email":email,"password":"SenhaTeste12345!"})
assert status==200
token=d["access_token"]
status,_=call("/api/auth/me",token=token)
assert status==200
status,_=call("/api/player/profile",token=token)
assert status==200
status,_=call("/api/player/ranking?limit=100&season=false",token=token)
assert status==200
status,_=call("/api/player/stats",token=token)
assert status==200
status,_=call("/api/player/matches?limit=20",token=token)
assert status==200
status,_=call("/api/player/season",token=token)
assert status==200
status,_=call("/api/account/farejador/quote",token=token)
assert status==200
print("API_AUTH_PLAYER_COMPETITIVE_OK")
