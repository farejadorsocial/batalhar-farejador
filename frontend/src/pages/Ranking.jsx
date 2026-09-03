import{useEffect,useState}from'react';import{Link}from'react-router-dom';import{api}from'../api/client';
function initials(name=''){return String(name).slice(0,2).toUpperCase()}
export default function Ranking(){
 const[r,setR]=useState([]),[season,setSeason]=useState(false),[s,setS]=useState(),[prog,setProg]=useState();
 async function load(){try{setR(await api(`/player/ranking?limit=100&season=${season}`));if(!s)setS(await api('/player/season'));setProg(await api('/player/progression'))}catch{}}
 useEffect(()=>{load()},[season]);
 const top=r.slice(0,3),rest=r.slice(3),me=prog? r.find(x=>String(x.user_id)===String(prog.user_id)):null;
 return <div className="page ranking-page">
  <div className="ranking-head"><div><span className="eyebrow">👑 RANKING COMPETITIVO</span><h1>{season&&s?s.name:'Os melhores da Arena'}</h1><p className="muted">Pontos medem sua reputação. XP e cadastro entram como desempate.</p></div><Link className="ghost-btn" to="/perfil">Ver minha carreira →</Link></div>
  <div className="arena-tabs ranking-tabs"><button className={!season?'active':''} onClick={()=>setSeason(false)}>🌎 Geral</button><button className={season?'active':''} onClick={()=>setSeason(true)}>🔥 Temporada</button></div>
  {top.length>0&&<section className="podium">{top.map((x,i)=><article className={`podium-card p${i+1}`} key={x.user_id}><div className="podium-medal">{i===0?'🥇':i===1?'🥈':'🥉'}</div><div className="podium-avatar">{initials(x.username)}</div><b>{x.username}</b><span>Nível {x.level}</span><strong>{x.points}</strong><small>PONTOS</small><em>#{x.position}</em></article>)}</section>}
  <section className="ranking-panel"><div className="ranking-table-head"><span>POSIÇÃO</span><span>JOGADOR</span><span>NÍVEL</span><span>PONTOS</span></div>{rest.map(x=><article key={x.user_id} className="ranking-row"><strong>#{x.position}</strong><div className="rank-user"><span>{initials(x.username)}</span><b>{x.username}</b></div><span>Lv. {x.level}</span><b>{x.points} pts</b></article>)}{!r.length&&<div className="empty">Ainda não há jogadores no ranking.</div>}</section>
  {prog&&<section className="my-rank-card"><div><span className="eyebrow">🔥 SUA CARREIRA</span><h2>Continue subindo</h2><p>Você tem <b>{prog.current_streak}</b> vitória(s) consecutiva(s) e <b>{prog.xp}</b> XP.</p></div><Link className="primary" to="/torneios">Jogar agora ⚔️</Link></section>}
 </div>
}
