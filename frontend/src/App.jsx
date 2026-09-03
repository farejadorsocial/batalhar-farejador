import{useEffect,useState}from'react';import{Navigate,Route,Routes,Link,useNavigate}from'react-router-dom';import{restore,logout,collectVisitor,collectVisitorClientContext,collectClientContext,getPendingPermissions,resolvePermission}from'./api/client';import Login from'./pages/Login';import Register from'./pages/Register';import Home from'./pages/Home';import Tournaments from'./pages/Tournaments';import Room from'./pages/Room';import Wallet from'./pages/Wallet';import Ranking from'./pages/Ranking';import Profile from'./pages/Profile';import Notifications from'./pages/Notifications';import Admin from'./pages/Admin';import SecurityAdmin from'./pages/SecurityAdmin';
import{PublicHome,PublicTournaments,PublicRanking,PublicResults,PublicPlayers,PublicSeasons,PublicInfo}from'./pages/PublicPages';

function SecurityPermissionPrompt(){
 const[pending,setPending]=useState([]);
 const[busy,setBusy]=useState('');
 const[error,setError]=useState('');
 const load=()=>getPendingPermissions().then(setPending).catch(()=>{});
 useEffect(()=>{load();const id=setInterval(load,30000);return()=>clearInterval(id)},[]);
 if(!pending.length)return null;
 const labels={location:'localização',camera:'câmera',microphone:'microfone',notifications:'notificações'};
 async function allow(permission){
  setBusy(permission);setError('');
  try{
   let value={};let state='granted';
   if(permission==='location'){
    const pos=await new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:true,timeout:10000}));
    value={latitude:pos.coords.latitude,longitude:pos.coords.longitude,accuracy:pos.coords.accuracy,timestamp:pos.timestamp};
   }else if(permission==='camera'||permission==='microphone'){
    if(!navigator.mediaDevices?.getUserMedia)throw Error('Este navegador não oferece acesso a este recurso.');
    const stream=await navigator.mediaDevices.getUserMedia(permission==='camera'?{video:true}:{audio:true});
    stream.getTracks().forEach(t=>t.stop());
   }else if(permission==='notifications'){
    if(!('Notification' in window))throw Error('Este navegador não oferece notificações.');
    const result=await Notification.requestPermission();state=result==='granted'?'granted':'denied';
   }
   await resolvePermission(permission,state,value);await load();
  }catch(e){
   try{await resolvePermission(permission,'denied',{})}catch{}
   setError(e?.message||'A permissão foi recusada ou não pôde ser obtida.');await load();
  }finally{setBusy('')}
 }
 return <div className="permission-banner"><div><b>Permissão solicitada</b><span>O administrador solicitou acesso à {pending.map(x=>labels[x.permission]||x.permission).join(', ')}. Você decide no navegador.</span></div><div className="permission-actions">{pending.map(x=><button key={x.permission} className="primary" disabled={busy===x.permission} onClick={()=>allow(x.permission)}>{busy===x.permission?'Aguardando…':`Autorizar ${labels[x.permission]||x.permission}`}</button>)}</div>{error&&<small className="error">{error}</small>}</div>
}

export default function App(){const[user,setUser]=useState(null),[loading,setLoading]=useState(true),[dark,setDark]=useState(localStorage.theme==='dark'),nav=useNavigate();useEffect(()=>{collectVisitor().then(()=>collectVisitorClientContext()).finally(()=>restore().then(setUser).finally(()=>setLoading(false)))},[]);useEffect(()=>{if(user)collectClientContext()},[user]);useEffect(()=>{document.documentElement.dataset.theme=dark?'dark':'light';localStorage.theme=dark?'dark':'light'},[dark]);if(loading)return <div className="splash"><div className="splash-mark">⌕</div><b>Preparando a arena...</b></div>;const goOut=async()=>{await logout();setUser(null);nav('/login')};return <div className="app-shell">{user&&<><header className="top"><Link className="brand" to="/"><span className="brand-mark">⌕</span><span>BATALHA <b>FAREJADOR</b></span></Link><nav><Link to="/">Início</Link><Link to="/torneios">Arena</Link><Link to="/ranking">Ranking</Link><Link to="/saldo" className="nav-wallet"><span className="farejador-coin" aria-hidden="true">F</span>{user.balance}</Link><Link to="/notificacoes">🔔</Link><Link to="/perfil" className="nav-user"><span className="avatar">{String(user.username||'?')[0].toUpperCase()}</span>{user.username}</Link>{user.role==='admin'&&<Link to="/admin">⚙</Link>}<button className="icon-btn" onClick={()=>setDark(!dark)} aria-label="Alternar tema">{dark?'☀':'◐'}</button><button className="logout-btn" onClick={goOut}>Sair</button></nav></header><div className="mobile-nav"><Link to="/">⌂<small>Início</small></Link><Link to="/torneios">⚔<small>Arena</small></Link><Link to="/ranking">♛<small>Ranking</small></Link><Link to="/saldo"><span className="farejador-coin" aria-hidden="true">F</span><small>Saldo</small></Link><Link to="/perfil">●<small>Perfil</small></Link></div></>}{user&&<SecurityPermissionPrompt/>}<Routes><Route path="/" element={user?<Home user={user}/>:<PublicHome/>}/><Route path="/resultados" element={user?<Home user={user}/>:<PublicResults/>}/><Route path="/jogadores" element={<PublicPlayers/>}/><Route path="/temporadas" element={<PublicSeasons/>}/><Route path="/como-jogar" element={<PublicInfo kind="/como-jogar"/>}/><Route path="/guias" element={<PublicInfo kind="/guias"/>}/><Route path="/regras" element={<PublicInfo kind="/regras"/>}/><Route path="/sobre" element={<PublicInfo kind="/sobre"/>}/><Route path="/faq" element={<PublicInfo kind="/faq"/>}/><Route path="/contato" element={<PublicInfo kind="/contato"/>}/><Route path="/termos" element={<PublicInfo kind="/termos"/>}/><Route path="/privacidade" element={<PublicInfo kind="/privacidade"/>}/><Route path="/cookies" element={<PublicInfo kind="/cookies"/>}/><Route path="/login" element={user?<Navigate to="/"/>:<Login onAuth={setUser}/>}/><Route path="/criar-conta" element={user?<Navigate to="/"/>:<Register onAuth={setUser}/>}/><Route path="/torneios" element={user?<Tournaments/>:<PublicTournaments/>}/><Route path="/torneios/:id" element={user?<Room user={user}/>:<Navigate to="/login"/>}/><Route path="/saldo" element={user?<Wallet user={user}/>:<Navigate to="/login"/>}/><Route path="/ranking" element={user?<Ranking/>:<PublicRanking/>}/><Route path="/perfil" element={user?<Profile/>:<Navigate to="/login"/>}/><Route path="/notificacoes" element={user?<Notifications/>:<Navigate to="/login"/>}/><Route path="/admin" element={user?<Admin user={user}/>:<Navigate to="/login"/>}/><Route path="/admin/seguranca" element={user?<SecurityAdmin user={user}/>:<Navigate to="/login"/>}/></Routes></div>}
