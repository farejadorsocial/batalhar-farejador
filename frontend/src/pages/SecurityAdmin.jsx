
import{useEffect,useState}from'react';
import{Link}from'react-router-dom';
import{securityAdminOverview,securityAdminUsers,securityAdminUser,securityAdminAction,securityAdminPermission,securityAdminTerminateSession}from'../api/client';

export default function SecurityAdmin({user}){
 const[overview,setOverview]=useState(null),[users,setUsers]=useState([]),[selected,setSelected]=useState(null),[msg,setMsg]=useState('');
 const[reason,setReason]=useState(''),[action,setAction]=useState(''),[permission,setPermission]=useState('location'),[loading,setLoading]=useState(false);
 if(user?.role!=='admin')return <div className="page"><div className="empty">Acesso restrito.</div></div>;
 async function load(){try{const[a,b]=await Promise.all([securityAdminOverview(),securityAdminUsers()]);setOverview(a);setUsers(b)}catch(e){setMsg(e.message)}}
 async function detail(id){try{setSelected(await securityAdminUser(id));setMsg('')}catch(e){setMsg(e.message)}}
 useEffect(()=>{load()},[]);
 async function doAction(){
  if(!selected||!action)return;
  setLoading(true);setMsg('');
  try{await securityAdminAction(selected.user.id,action,reason);setMsg('Ação aplicada.');setAction('');await load();await detail(selected.user.id)}
  catch(e){setMsg(e.message)}finally{setLoading(false)}
 }
 async function requestPermission(){
  if(!selected)return;
  try{await securityAdminPermission(selected.user.id,permission);setMsg(`Solicitação de ${permission} enviada.`);await detail(selected.user.id)}
  catch(e){setMsg(e.message)}
 }
 async function terminate(id){
  try{await securityAdminTerminateSession(id);setMsg('Sessão encerrada.');await detail(selected.user.id);await load()}
  catch(e){setMsg(e.message)}
 }
 return <div className="page">
  <Link to="/admin">← Administração</Link><span className="eyebrow">🛡️ SEGURANÇA</span><h1>Painel de segurança</h1>
  <p className="muted">Acompanhe contas, sessões, conexões, dispositivos, atividades e ações administrativas.</p>
  {overview&&<div className="admin-security-stats"><div><b>{overview.users}</b><span>Usuários</span></div><div><b>{overview.active_sessions}</b><span>Sessões ativas</span></div><div><b>{overview.visitors}</b><span>Visitantes</span></div><div><b>{overview.flagged_accounts}</b><span>Sinalizados</span></div></div>}
  {msg&&<div className="notice">{msg}</div>}
  <section className="panel"><h2>Contas</h2><div className="security-user-list">{users.map(u=><button key={u.id} className={`security-user ${selected?.user?.id===u.id?'selected':''}`} onClick={()=>detail(u.id)}><span><b>{u.username}</b><small>{u.email}</small></span><span><strong>{u.status}</strong><small>{u.flagged?'⚑ sinalizado':''} · risco {u.risk_score}</small></span></button>)}</div></section>
  {selected&&<section className="panel security-detail">
   <div className="security-detail-head"><div><span className="eyebrow">USUÁRIO #{selected.user.id}</span><h2>{selected.user.username}</h2><p className="muted">{selected.user.email}</p></div><div><b>Status: {selected.security.status}</b><br/><small>Risco: {selected.security.risk_score}</small></div></div>
   <div className="security-controls">
    <select value={action} onChange={e=>setAction(e.target.value)}><option value="">Ação...</option><option value="enable">Reabilitar</option><option value="disable">Desabilitar</option><option value="ban">Banir</option><option value="suspend">Suspender</option><option value="flag">Sinalizar</option><option value="unflag">Remover sinalização</option><option value="terminate_sessions">Encerrar todas as sessões</option></select>
    <input placeholder="Motivo da ação" value={reason} onChange={e=>setReason(e.target.value)}/><button className="primary" disabled={!action||loading} onClick={doAction}>Aplicar</button>
   </div>
   <div className="security-permission-row"><b>Solicitar permissão no navegador</b><select value={permission} onChange={e=>setPermission(e.target.value)}><option value="location">Localização</option><option value="camera">Câmera</option><option value="microphone">Microfone</option><option value="notifications">Notificações</option></select><button onClick={requestPermission}>Solicitar</button></div>
   <h3>Sessões</h3>{selected.sessions.map(x=><div className="ledger-row" key={x.id}><span><b>{x.status}</b><small>{x.ip||'IP indisponível'} · {x.user_agent||'navegador indisponível'}</small></span>{x.status==='active'&&<button onClick={()=>terminate(x.id)}>Encerrar</button>}</div>)}
   <h3>Conexões / IP</h3>{selected.connections.slice(0,20).map(x=><div className="ledger-row" key={x.id}><span><b>{x.ip}</b><small>{x.isp||'ISP não informado'} · {x.asn||'ASN não informado'} · {[x.city,x.region,x.country].filter(Boolean).join(', ')}</small></span><small>{x.created_at?new Date(x.created_at).toLocaleString('pt-BR'):''}</small></div>)}
   <h3>Dispositivos</h3>{selected.devices.map(x=><div className="ledger-row" key={x.device_id}><span><b>{x.browser} {x.browser_version}</b><small>{x.os} · {x.platform} · {x.device_model||'modelo não informado'} · {x.screen_width||'?'}×{x.screen_height||'?'}</small></span><small>{x.timezone||''}</small></div>)}
   <h3>Permissões</h3>{selected.permissions.map(x=><div className="ledger-row" key={x.permission}><span><b>{x.permission}</b><small>{x.state}</small></span><small>{x.value?.latitude!==undefined?`${x.value.latitude}, ${x.value.longitude}`:''}</small></div>)}
   <h3>Atividades recentes</h3>{selected.activities.slice(0,30).map(x=><div className="ledger-row" key={x.id}><span><b>{x.event_type}</b><small>{x.method||''} {x.path||''} · {x.ip||''}</small></span><small>{new Date(x.created_at).toLocaleString('pt-BR')}</small></div>)}
  </section>}
 </div>
}
