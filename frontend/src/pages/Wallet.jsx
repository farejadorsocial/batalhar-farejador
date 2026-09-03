import{useEffect,useState}from'react';import{api}from'../api/client';

const coin=<span className="farejador-coin" aria-hidden="true">F</span>;

function money(value){return Number(value||0).toLocaleString('pt-BR')}
function movementInfo(item){
 const kind=item.kind;
 if(kind==='prize')return{icon:'🏆',label:'Premiação conquistada',tone:'positive',description:item.description.replace(/^Premiação\s+/i,'')};
 if(kind==='entry_fee')return{icon:'🎟️',label:'Entrada no torneio',tone:'negative',description:item.description.replace(/^Entrada no torneio\s*/i,'')};
 if(kind==='refund')return{icon:'↩️',label:'Entrada devolvida',tone:'positive',description:item.description.replace(/^Devolução por cancelamento\s*/i,'')};
 if(kind==='organizer_payout')return{icon:'💼',label:'Receita do organizador',tone:'positive',description:item.description.replace(/^Pagamento do organizador\s*[—-]?\s*/i,'')};
 return{icon:item.amount>=0?'↗':'↘',label:item.amount>=0?'Crédito':'Débito',tone:item.amount>=0?'positive':'negative',description:item.description||'Movimentação de saldo'};
}

export default function Wallet({user}){
 const[w,setW]=useState(),[l,setL]=useState([]),[quote,setQuote]=useState(),[conv,setConv]=useState(''),[busy,setBusy]=useState(false);
 async function load(){try{const[a,b,c]=await Promise.all([api('/account/wallet'),api('/account/ledger'),api('/account/farejador/quote')]);setW(a);setL(b);setQuote(c)}catch{}}
 useEffect(()=>{load()},[]);
 async function convert(){try{setBusy(true);const r=await api('/account/convert-xp',{method:'POST',body:JSON.stringify({xp:Number(conv)})});setConv('');setW(r);await load()}catch(e){alert(e.message)}finally{setBusy(false)}}
 const balance=w?.balance??user.balance??0,xp=w?.xp??user.xp??0,level=w?.level??user.level??1,points=w?.points??user.points??0;
 const credits=l.filter(x=>Number(x.amount)>0).reduce((s,x)=>s+Number(x.amount),0),debits=Math.abs(l.filter(x=>Number(x.amount)<0).reduce((s,x)=>s+Number(x.amount),0));
 return <div className="page wallet-page">
  <section className="wallet-hero-v7"><div><span className="eyebrow">{coin} SUA CARTEIRA</span><h1>Seu poder de jogo.</h1><p>Farejadores são sua moeda principal. XP alimenta sua evolução e pontos constroem sua reputação.</p></div><div className="wallet-balance-v7"><span>FAREJADORES DISPONÍVEIS</span><b className="wallet-balance-number">{coin}{money(balance)}</b><small>Saldo confirmado pelo servidor</small></div></section>
  <section className="wallet-metrics-v7"><div><span>⭐</span><b>{money(xp)}</b><small>XP TOTAL</small></div><div><span>⚡</span><b>{level}</b><small>NÍVEL</small></div><div><span>🏆</span><b>{money(points)}</b><small>PONTOS</small></div></section>
  <section className="panel convert convert-v7"><div className="convert-title"><div><span className="eyebrow">🔄 CONVERSÃO</span><h2>Transforme XP em Farejadores</h2><p>Taxa atual: <b>{quote?.xp_per_farejador?.toLocaleString('pt-BR')||'1.000'} XP = 1 Farejador</b>.</p></div><div className="conversion-rate"><b>1.000</b><span>XP</span><strong>→</strong><span className="conversion-coin">{coin}</span><b>1</b></div></div><small>O preço dinâmico permanece desativado até existir um mercado real de compra/venda. Isso evita criar Farejadores ou alterar o preço pelo frontend.</small><div className="convert-row"><input type="number" min="1000" step="1000" value={conv} onChange={e=>setConv(e.target.value)} placeholder="Quantidade de XP"/><button className="primary" disabled={busy||!conv||Number(conv)<1000} onClick={convert}>{busy?'Convertendo...':'Converter XP → Farejador'}</button></div></section>
  <section className="panel ledger premium-panel wallet-ledger-v10">
   <div className="section-head wallet-ledger-head"><div><span className="eyebrow">📒 HISTÓRICO DA CARTEIRA</span><h2>Movimentações</h2><p>Veja de onde veio cada crédito e para onde foi cada gasto.</p></div><span className="ledger-count">{l.length} {l.length===1?'registro':'registros'}</span></div>
   {l.length>0&&<div className="ledger-summary-v10"><div><span>↗</span><b>+{money(credits)}</b><small>ENTRADAS</small></div><div><span>↘</span><b>-{money(debits)}</b><small>SAÍDAS</small></div><div><span>●</span><b>{money(balance)}</b><small>SALDO ATUAL</small></div></div>}
   <div className="wallet-ledger-list-v10">{l.map(x=>{const m=movementInfo(x);return <article className={`wallet-movement-v10 ${m.tone}`} key={x.transaction_id}><div className="movement-icon-v10">{m.icon}</div><div className="movement-main-v10"><div><b>{m.label}</b><span className="movement-kind-v10">{x.kind==='prize'?'RECOMPENSA':x.kind==='entry_fee'?'PARTICIPAÇÃO':x.kind==='refund'?'DEVOLUÇÃO':x.kind==='organizer_payout'?'ORGANIZADOR':'MOVIMENTO'}</span></div><p>{m.description}</p><small>{new Date(x.created_at).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'})}</small></div><div className="movement-value-v10"><strong>{Number(x.amount)>0?'+':''}{money(x.amount)} {coin}</strong><small>Saldo após: {money(x.balance_after)} {coin}</small></div></article>})}</div>
   {!l.length&&<div className="wallet-empty-v10"><span>📒</span><b>Nenhuma movimentação ainda</b><small>Quando você entrar em um torneio, receber uma premiação ou receber uma devolução, tudo aparecerá aqui.</small></div>}
  </section>
 </div>
}
