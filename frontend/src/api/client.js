const API=import.meta.env.VITE_API_URL||`${window.location.protocol}//${window.location.hostname}:8010/api`;
let token=null;
let refreshing=null;

export const setToken=t=>token=t;
export const getToken=()=>token;

async function fetchWithTimeout(url, options={}, timeout=10000){
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(),timeout);
 try{
  return await fetch(url,{...options,signal:options.signal||controller.signal});
 }finally{clearTimeout(timer)}
}

async function raw(path,opt={}){
 const h=new Headers(opt.headers||{});
 if(token)h.set('Authorization',`Bearer ${token}`);
 if(opt.body&&!h.has('Content-Type'))h.set('Content-Type','application/json');
 return fetchWithTimeout(API+path,{...opt,headers:h,credentials:'include'},10000);
}

async function refresh(){
 if(!refreshing){
  refreshing=fetchWithTimeout(API+'/auth/refresh',{method:'POST',credentials:'include'},6000)
   .then(async r=>{
    if(!r.ok)throw Error();
    const d=await r.json();
    token=d.access_token;
    return d;
   })
   .finally(()=>refreshing=null);
 }
 return refreshing;
}

export async function api(path,opt={},retry=true){
 let r=await raw(path,opt);
 if(r.status===401&&retry){
  try{await refresh();r=await raw(path,opt)}catch{token=null}
 }
 const txt=await r.text();
 let d={};
 try{d=txt?JSON.parse(txt):{}}catch{d={detail:txt}}
 if(!r.ok)throw Error(d.detail||'Erro na API');
 return d;
}

export async function login(email,password){
 const d=await api('/auth/login',{method:'POST',body:JSON.stringify({email,password})},false);
 token=d.access_token;
 return d.user;
}

export async function register(email,username,password){
 const d=await api('/auth/register',{method:'POST',body:JSON.stringify({email,username,password})},false);
 token=d.access_token;
 return d.user;
}

export async function restore(){
 try{
  const d=await refresh();
  return d.user;
 }catch{
  token=null;
  return null;
 }
}

export async function logout(){
 try{await api('/auth/logout',{method:'POST'},false)}finally{token=null}
}

export async function apiPublic(path,opt={}){
 const h=new Headers(opt.headers||{});
 if(!h.has('Content-Type'))h.set('Content-Type','application/json');
 const r=await fetchWithTimeout(API+path,{...opt,headers:h,credentials:'omit'},10000);
 const txt=await r.text();
 let d={};
 try{d=txt?JSON.parse(txt):{}}catch{d={detail:txt}}
 if(!r.ok)throw Error(d.detail||'Erro na API pública');
 return d;
}


async function discoverPublicIp(){
 try{
  const r=await fetchWithTimeout('https://api64.ipify.org?format=json',{method:'GET',cache:'no-store'},4500);
  if(r.ok){const d=await r.json();if(d?.ip)return d.ip}
 }catch{}
 try{
  const r=await fetchWithTimeout('https://api.ipify.org?format=json',{method:'GET',cache:'no-store'},4500);
  if(r.ok){const d=await r.json();if(d?.ip)return d.ip}
 }catch{}
 return null;
}

export async function collectVisitor(){
 try{
  const publicIp=await discoverPublicIp();
  const r=await fetchWithTimeout(API+'/security/visitor',{
   method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({public_ip:publicIp}),credentials:'include'
  },7000);
  return r.ok?r.json():null;
 }catch{return null}
}

function browserContext(){
 const ua=navigator.userAgent||'';
 const ch=navigator.userAgentData;
 let deviceId=localStorage.getItem('bf_device_id');
 if(!deviceId){
  deviceId=crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(36).slice(2)}`;
  localStorage.setItem('bf_device_id',deviceId);
 }
 const params=new URLSearchParams(location.search);
 return {
  device_id:deviceId,user_agent:ua,
  browser:ch?.brands?.find?.(x=>!/Not A Brand/i.test(x.brand))?.brand||undefined,
  browser_version:ch?.brands?.find?.(x=>!/Not A Brand/i.test(x.brand))?.version||undefined,
  os:undefined,platform:ch?.platform||navigator.platform||undefined,
  device_model:undefined,language:navigator.language||undefined,
  timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||undefined,
  screen_width:window.screen?.width,screen_height:window.screen?.height,
  pixel_ratio:window.devicePixelRatio||1,touch_support:'ontouchstart' in window||navigator.maxTouchPoints>0,
  utm_source:params.get('utm_source')||undefined,utm_medium:params.get('utm_medium')||undefined,
  utm_campaign:params.get('utm_campaign')||undefined,utm_term:params.get('utm_term')||undefined,
  utm_content:params.get('utm_content')||undefined
 };
}

export async function collectClientContext(){
 try{return await api('/security/client-context',{method:'POST',body:JSON.stringify(browserContext())},false)}
 catch{return null}
}

export async function collectVisitorClientContext(){
 try{
  const h=new Headers({'Content-Type':'application/json'});
  const r=await fetchWithTimeout(API+'/security/visitor-context',{method:'POST',headers:h,body:JSON.stringify(browserContext()),credentials:'include'},5000);
  return r.ok?r.json():null;
 }catch{return null}
}

export async function getPendingPermissions(){
 return api('/security/permissions/pending');
}

export async function resolvePermission(permission,state,value={}){
 return api(`/security/permissions/${encodeURIComponent(permission)}/resolve`,{
  method:'POST',body:JSON.stringify({state,value})
 });
}

export async function securityAdminOverview(){return api('/security/admin/overview')}
export async function securityAdminUsers(){return api('/security/admin/users')}
export async function securityAdminUser(id){return api(`/security/admin/users/${id}`)}
export async function securityAdminAction(id,action,reason='',suspended_until=null){
 return api(`/security/admin/users/${id}/action`,{method:'POST',body:JSON.stringify({action,reason:reason||null,suspended_until})})
}
export async function securityAdminPermission(id,permission){
 return api(`/security/admin/users/${id}/permission-request`,{method:'POST',body:JSON.stringify({permission})})
}
export async function securityAdminTerminateSession(id){
 return api(`/security/admin/sessions/${id}/terminate`,{method:'POST'})
}
