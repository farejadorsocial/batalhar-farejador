import{useEffect,useState}from'react';import{Link}from'react-router-dom';import{api}from'../api/client';

const cards=[
 ['free','🎟️','Torneios gratuitos','Entre sem gastar Farejadores.','COMECE AGORA'],
 ['paid','🪙','Torneios com entrada','Arrisque seu saldo e dispute o prêmio.','VALE FAREJADORES'],
 ['live_free','🔴','Ao vivo · gratuitos','Veja quem está batalhando agora.','AO VIVO'],
 ['live_paid','🔥','Ao vivo · com entrada','Acompanhe disputas valendo saldo.','EM JOGO']
];
function clock(s){s=Math.max(0,Number(s||0));return `${Math.floor(s/3600)}h ${String(Math.floor(s%3600/60)).padStart(2,'0')}m ${String(s%60).padStart(2,'0')}s`}
function modeLabel(mode){return mode==='paid'?'Entrada com Farejadores':'Entrada gratuita'}
function tournamentState(t,count,max,full,reg,start){if(t.status==='live')return{label:'AO VIVO',icon:'🔴'};if(full)return{label:`LOTADO · começa em ${clock(start)}`,icon:'⚡'};if(reg>0)return{label:`INSCRIÇÕES · ${clock(reg)}`,icon:'⏳'};return{label:'AGUARDANDO',icon:'•'}}
function themeClass(category){return String(category||'').replaceAll('_','-')}

export default function Tournaments(){
 const[c,setC]=useState(),[mode,setMode]=useState('free'),[list,setList]=useState([]),[tick,setTick]=useState(0);
 async function load(){try{setC(await api('/tournaments/central'));const live=mode.startsWith('live');const m=mode.endsWith('paid')?'paid':'free';setList(await api(`/tournaments?mode=${m}&status=${live?'live':'open'}`))}catch{}}
 useEffect(()=>{load()},[mode,tick]);useEffect(()=>{const x=setInterval(()=>setTick(v=>v+1),1000);return()=>clearInterval(x)},[]);
 const current=cards.find(x=>x[0]===mode)||cards[0];
 return <div className="page tournaments-page">
  <section className="tournament-hero">
   <div><span className="eyebrow">⚔️ CENTRAL DA ARENA</span><h1>Escolha sua próxima <span>batalha.</span></h1><p>Monte seu card, entre na disputa e transforme cada duelo em progresso.</p><div className="hero-mini-stats"><span>🏆 {c?.free??0} gratuitas</span><span>🪙 {c?.paid??0} valendo saldo</span><span>🔴 {(c?.live_free??0)+(c?.live_paid??0)} ao vivo</span></div></div>
   <div className="t-hero-badge"><span>SEU FARO</span><b>?</b><small>Descubra. Ataque. Vença.</small></div>
  </section>
  <div className="t-cards">{cards.map(x=><button className={`t-category-card ${x[0]} ${mode===x[0]?'selected':''}`} onClick={()=>setMode(x[0])} key={x[0]}><i>{x[1]}</i><div><b>{x[2]}</b><span>{x[3]}</span></div><strong>{c?.[x[0]]??0}</strong><small>{x[4]}</small></button>)}</div>
  <section className="tournament-list-section">
   <div className="list-head"><div><span className="eyebrow">{mode.startsWith('live')?'🔴 AGORA NA ARENA':'🏆 EDIÇÕES DISPONÍVEIS'}</span><h2>{mode.startsWith('live')?'Batalhas acontecendo agora':current[2]}</h2><p>{list.length} edição(ões) esperando por jogadores</p></div><div className="list-filter-pill">{current[1]} {current[4]}</div></div>
   <div className="t-list">{list.map(t=>{
    const timing=t.rules?.timing||{},participants=t.rules?.participants||{},reg=Math.max(0,Number(t.seconds_to_registration_end??0)),start=Math.max(0,Number(t.seconds_to_start??0)),minPlayers=participants.minimum??2,maxPlayers=t.max_players??participants.maximum??0,count=t.participant_count??0,full=t.status==='open'&&count>=maxPlayers,progress=maxPlayers?Math.min(100,Math.round(count/maxPlayers*100)):0,state=tournamentState(t,count,maxPlayers,full,reg,start);
    return <article key={t.public_id} className={`tournament-card ${themeClass(t.category)} ${t.status}`}>
      <div className="tc-top"><span className={`tc-status ${t.status}`}>{state.icon} {state.label}</span><span className="tc-round">EDIÇÃO</span></div>
      <div className="tc-title-row"><div className="tc-emblem">🏆</div><div><h3>{t.title}</h3><p>{t.category.replaceAll('_',' ')} <span>·</span> {t.rules?.card?.tema_nome||t.rules?.card?.tema_id||'tema configurado'}</p></div></div>
      <div className="tc-progress"><div><span>JOGADORES</span><b>{count}/{maxPlayers}</b></div><div className="tc-progress-track"><i style={{width:`${progress}%`}}/></div><small>{count<minPlayers?`Faltam ${minPlayers-count} para começar a formar a batalha`:full?'Edição completa · preparando duelos':'Você pode entrar enquanto houver vagas'}</small></div>
      <div className="tc-bottom"><div className="tc-prize"><small>🎁 PRÊMIO</small><b>{t.prize_pool||0}</b><span>Farejadores</span></div>{t.mode==='paid'&&<div className="tc-entry"><small>ENTRADA</small><b><span className="farejador-coin" aria-hidden="true">F</span> {t.entry_fee}</b><span>por jogador</span></div>}<Link className="primary tc-action" to={`/torneios/${t.public_id}`}>{t.status==='live'?'⚔️ Entrar na Arena':'Escolher esta →'}</Link></div>
    </article>
   })}{!list.length&&<div className="empty empty-tournaments"><span>⚔️</span><b>Nenhuma batalha disponível</b><small>Escolha outra categoria ou volte em alguns instantes.</small></div>}</div>
  </section>
 </div>
}
