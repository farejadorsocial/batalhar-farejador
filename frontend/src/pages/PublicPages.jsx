import{useEffect,useState}from'react';
import{Link,useLocation}from'react-router-dom';
import{apiPublic}from'../api/client';
import{AdSlot}from'../components/AdSlot';

const SITE_URL=String(import.meta.env.VITE_SITE_URL||'').replace(/\/$/,'');

function setMeta(name,content,property=false){
 let el=document.querySelector(`meta[${property?'property':'name'}="${name}"]`);
 if(!el){el=document.createElement('meta');el.setAttribute(property?'property':'name',name);document.head.appendChild(el)}
 el.setAttribute('content',content);
}

function PublicShell({children,title,description,ad=false}){
 const loc=useLocation();
 useEffect(()=>{
  const fullTitle=title?`${title} · Batalha Farejador`:'Batalha Farejador';
  const desc=description||'Batalha Farejador: estratégia, descobertas, duelos e torneios.';
  document.title=fullTitle;
  setMeta('description',desc);
  setMeta('og:title',fullTitle,true);
  setMeta('og:description',desc,true);
  setMeta('og:type','website',true);
  setMeta('twitter:card','summary');
  if(SITE_URL){
   setMeta('og:url',`${SITE_URL}${loc.pathname}`,true);
   let link=document.querySelector('link[rel="canonical"]');
   if(!link){link=document.createElement('link');link.rel='canonical';document.head.appendChild(link)}
   link.href=`${SITE_URL}${loc.pathname}`;
  }
 },[title,description,loc.pathname]);

 return <div className="public-shell">
  <header className="public-header">
   <Link to="/" className="public-brand"><span className="brand-mark">⌕</span><span>BATALHA <b>FAREJADOR</b></span></Link>
   <nav aria-label="Navegação pública">
    <Link className={loc.pathname==='/torneios'?'active':''} to="/torneios">Torneios</Link>
    <Link className={loc.pathname==='/ranking'?'active':''} to="/ranking">Ranking</Link>
    <Link className={loc.pathname==='/resultados'?'active':''} to="/resultados">Resultados</Link>
    <Link className={loc.pathname==='/jogadores'?'active':''} to="/jogadores">Jogadores</Link>
    <Link className={loc.pathname==='/como-jogar'?'active':''} to="/como-jogar">Como jogar</Link>
    <Link className={loc.pathname==='/guias'?'active':''} to="/guias">Guias</Link>
   </nav>
   <div className="public-actions"><Link className="ghost-btn" to="/login">Entrar</Link><Link className="primary" to="/criar-conta">Criar conta</Link></div>
  </header>
  <main>{ad&&<div className="public-ad-top"><AdSlot/></div>}{children}</main>
  <footer className="public-footer">
   <div><b>BATALHA FAREJADOR</b><p>Uma arena de estratégia, descoberta e competição.</p></div>
   <div className="footer-links">
    <Link to="/sobre">Sobre</Link><Link to="/regras">Regras</Link><Link to="/faq">FAQ</Link><Link to="/contato">Contato</Link>
    <Link to="/temporadas">Temporadas</Link><Link to="/termos">Termos</Link><Link to="/privacidade">Privacidade</Link><Link to="/cookies">Cookies</Link>
   </div>
   <small>© {new Date().getFullYear()} Batalha Farejador. Todos os direitos reservados.</small>
  </footer>
 </div>
}

function PublicState({loading,error}){
 if(loading)return <div className="public-empty"><b>Carregando...</b><span>Buscando as informações mais recentes.</span></div>;
 if(error)return <div className="public-empty"><b>Não foi possível carregar agora.</b><span>Você pode continuar conhecendo a Arena e tentar novamente depois.</span></div>;
 return null
}

function CTA({children='Começar a jogar →',to='/criar-conta',secondary=false}){
 return <Link className={secondary?'ghost-btn':'primary big-btn'} to={to}>{children}</Link>
}

export function PublicHome(){
 const[data,setData]=useState({tournaments:[],ranking:[],loading:true});
 useEffect(()=>{
  let live=true;
  Promise.allSettled([
   apiPublic('/public/tournaments'),
   apiPublic('/public/ranking?limit=5')
  ]).then(([t,r])=>{
   if(!live)return;
   setData({
    tournaments:t.status==='fulfilled'?(t.value.items||[]).slice(0,3):[],
    ranking:r.status==='fulfilled'?r.value.slice(0,5):[],
    loading:false
   })
  }).catch(()=>live&&setData(x=>({...x,loading:false})));
  return()=>{live=false}
 },[]);
 return <PublicShell title="Jogo de estratégia e torneios" description="Descubra o Batalha Farejador: uma arena de estratégia onde você cria seu card, enfrenta adversários, disputa torneios e sobe no ranking." ad>
  <section className="public-hero public-hero-v2">
   <div className="public-hero-copy">
    <span className="eyebrow">⚡ ENTRE NA ARENA</span>
    <h1>Seu faro.<br/><span>Sua estratégia.</span><br/>Sua vitória.</h1>
    <p className="hero-lead">Um jogo de descoberta e estratégia onde você precisa pensar, observar e escolher bem. Monte seu card, enfrente adversários e tente provar que seu faro é melhor.</p>
    <div className="hero-actions"><CTA/><CTA secondary to="/como-jogar">Como funciona</CTA></div>
    <div className="hero-proof"><span>✓ Gratuito para começar</span><span>✓ Torneios competitivos</span><span>✓ Ranking de jogadores</span></div>
   </div>
   <div className="public-hero-visual">
    <div className="hero-orbit hero-orbit-a"></div><div className="hero-orbit hero-orbit-b"></div>
    <div className="public-hero-card card-back-v2"><span>?</span><b>CARD OCULTO</b><small>Você consegue descobrir?</small></div>
    <div className="hero-mini-card hero-mini-left"><span>SEU CARD</span><b>Estratégia</b><small>Pronto para o duelo</small></div>
    <div className="hero-mini-card hero-mini-right"><span>ARENA</span><b>VS</b><small>Outro jogador</small></div>
   </div>
  </section>

  <section className="public-welcome-strip">
   <div><span className="eyebrow">👃 O DESAFIO</span><h2>Não é só sorte. É saber farejar.</h2><p>Leia as informações, entenda as possibilidades e tome decisões antes que o adversário descubra o seu jogo.</p></div>
   <CTA secondary to="/criar-conta">Quero experimentar →</CTA>
  </section>

  <section className="public-section">
   <div className="section-head"><span className="eyebrow">🎮 COMO FUNCIONA</span><h2>Você entra sabendo o que fazer.</h2><p className="public-section-lead">A experiência foi pensada para ser fácil de entender e divertida de dominar.</p></div>
   <div className="public-step-grid">
    <article><span>01</span><i>🏆</i><h3>Escolha uma disputa</h3><p>Veja os torneios disponíveis e escolha uma edição que combine com você.</p></article>
    <article><span>02</span><i>🃏</i><h3>Prepare seu card</h3><p>Monte uma escolha compatível com a edição e entre preparado para o desafio.</p></article>
    <article><span>03</span><i>🔎</i><h3>Fareje o adversário</h3><p>Observe as pistas e tente descobrir as opções protegidas do outro jogador.</p></article>
    <article><span>04</span><i>⚔️</i><h3>Tome sua decisão</h3><p>Cada tentativa conta. Pense antes de agir e use sua leitura da partida.</p></article>
    <article><span>05</span><i>🏅</i><h3>Conquiste pontos</h3><p>Vença disputas, ganhe experiência e construa sua trajetória competitiva.</p></article>
   </div>
  </section>

  <section className="public-section public-battle-explainer">
   <div className="section-head"><span className="eyebrow">⚔️ UMA BATALHA POR DENTRO</span><h2>Veja a lógica do desafio.</h2><p className="public-section-lead">Você não precisa decorar tudo para começar. O jogo apresenta as informações necessárias em cada etapa.</p></div>
   <div className="battle-demo">
    <div className="demo-player"><span className="demo-avatar">VOCÊ</span><b>Seu card</b><small>Suas escolhas ficam protegidas.</small></div>
    <div className="demo-vs"><span>VS</span><small>duelo</small></div>
    <div className="demo-player opponent"><span className="demo-avatar">?</span><b>Adversário</b><small>Você tenta descobrir o que está oculto.</small></div>
    <div className="demo-line"><span>👁 Observe</span><span>🧠 Pense</span><span>🎯 Escolha</span><span>🏆 Descubra</span></div>
   </div>
  </section>

  <section className="public-section public-live-section">
   <div className="section-head inline-head"><div><span className="eyebrow">🔥 AGORA NA ARENA</span><h2>O jogo já tem história.</h2><p className="public-section-lead">Veja o que está acontecendo e imagine seu nome entre os próximos destaques.</p></div><CTA secondary to="/torneios">Ver todos os torneios →</CTA></div>
   <div className="home-live-grid">
    <div className="home-live-panel"><div className="mini-head"><b>🏆 Torneios</b><Link to="/torneios">Ver mais</Link></div>
     {data.tournaments.length?data.tournaments.map(t=><Link to="/torneios" className="live-item" key={t.public_id}><span><b>{t.title}</b><small>{t.category_label} · {t.mode==='paid'?'Entrada com Farejadores':'Entrada gratuita'}</small></span><strong>{t.participant_count}/{t.max_players}</strong></Link>):<div className="live-empty">Novas disputas podem aparecer aqui.</div>}
    </div>
    <div className="home-live-panel"><div className="mini-head"><b>👑 Ranking</b><Link to="/ranking">Ver ranking</Link></div>
     {data.ranking.length?data.ranking.slice(0,4).map(x=><Link to="/ranking" className="live-item" key={x.user_id}><span><b>#{x.position} · {x.username}</b><small>Nível {x.level}</small></span><strong>{x.points} pts</strong></Link>):<div className="live-empty">O ranking está esperando novos nomes.</div>}
    </div>
   </div>
  </section>

  <section className="public-section public-why">
   <div className="section-head"><span className="eyebrow">🌟 POR QUE ENTRAR?</span><h2>Comece simples. Evolua jogando.</h2></div>
   <div className="public-benefit-grid">
    <article><i>🧠</i><h3>Estratégia</h3><p>Aprenda a interpretar possibilidades e transformar informação em decisão.</p></article>
    <article><i>⚔️</i><h3>Competição</h3><p>Enfrente outros jogadores e descubra como seu estilo se compara aos demais.</p></article>
    <article><i>📈</i><h3>Evolução</h3><p>Construa sua carreira com pontos, XP, níveis, resultados e temporadas.</p></article>
    <article><i>🏆</i><h3>Reconhecimento</h3><p>Suba no ranking e faça seu nome aparecer entre os destaques da Arena.</p></article>
   </div>
  </section>

  <section className="public-section public-cta-section">
   <div className="final-cta">
    <span className="eyebrow">🚀 SUA VEZ</span>
    <h2>O próximo nome do ranking pode ser o seu.</h2>
    <p>Crie sua conta, conheça a Arena e descubra até onde seu faro consegue chegar.</p>
    <div className="hero-actions"><CTA>Criar minha conta →</CTA><CTA secondary to="/torneios">Explorar torneios</CTA></div>
    <small>Você pode conhecer as regras antes de começar.</small>
   </div>
  </section>
 </PublicShell>
}

export function PublicTournaments(){
 const[data,setData]=useState({items:[]}),[loading,setLoading]=useState(true),[error,setError]=useState(false);
 useEffect(()=>{let live=true;apiPublic('/public/tournaments').then(x=>{if(live)setData(x)}).catch(()=>{if(live)setError(true)}).finally(()=>{if(live)setLoading(false)});return()=>{live=false}},[]);
 return <PublicShell title="Torneios" description="Descubra as disputas do Batalha Farejador, veja vagas e escolha sua próxima competição." ad>
  <section className="public-page-head public-page-head-v2"><span className="eyebrow">🏆 ENTRE NA DISPUTA</span><h1>Qual vai ser o seu próximo desafio?</h1><p>Escolha uma edição, conheça a proposta e prepare-se para enfrentar outros jogadores.</p><div className="page-head-actions"><CTA>Quero jogar →</CTA><CTA secondary to="/como-jogar">Entender o jogo</CTA></div></section>
  <div className="public-list tournament-list-v2">
   {loading||error?<PublicState loading={loading} error={error}/>:data.items?.length?data.items.map(t=><article className="public-tournament public-tournament-v2" key={t.public_id}>
    <div className="tournament-main"><span className="public-status">{t.status==='live'?'🔴 AO VIVO':t.status==='finished'?'✓ ENCERRADO':'⏳ INSCRIÇÕES ABERTAS'}</span><h2>{t.title}</h2><p>{t.category_label} · {t.mode==='paid'?'Entrada com Farejadores':'Entrada gratuita'}</p><div className="tournament-tags"><span>👥 {t.participant_count}/{t.max_players} jogadores</span><span>🏅 {t.prize_pool||0} Farejadores</span></div></div>
    <div className="tournament-side"><span><b>{t.participant_count}</b><small>participantes</small></span><span><b>{t.max_players}</b><small>vagas</small></span><CTA>Participar →</CTA></div>
   </article>):<div className="public-empty"><b>Nenhuma disputa aberta agora.</b><span>Volte em breve para encontrar uma nova edição.</span></div>}
  </div>
  <section className="public-mini-cta"><b>Primeira vez por aqui?</b><span>Veja como funciona antes de entrar na Arena.</span><Link to="/como-jogar">Aprender a jogar →</Link></section>
 </PublicShell>
}

export function PublicRanking(){
 const[r,setR]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(false);
 useEffect(()=>{let live=true;apiPublic('/public/ranking?limit=100').then(x=>{if(live)setR(x)}).catch(()=>{if(live)setError(true)}).finally(()=>{if(live)setLoading(false)});return()=>{live=false}},[]);
 return <PublicShell title="Ranking" description="Veja quem está no topo do ranking do Batalha Farejador e descubra como construir sua própria carreira competitiva." ad>
  <section className="public-page-head public-page-head-v2"><span className="eyebrow">👑 QUEM ESTÁ NO TOPO?</span><h1>O próximo nome pode ser o seu.</h1><p>Cada disputa ajuda a construir sua reputação na Arena. Veja quem está liderando e entre para a competição.</p><div className="page-head-actions"><CTA>Quero competir →</CTA><CTA secondary to="/como-jogar">Como funciona</CTA></div></section>
  <div className="public-ranking-table ranking-v2">
   {loading||error?<PublicState loading={loading} error={error}/>:<>{r.length>=1&&<div className="ranking-podium">{r.slice(0,3).map((x,i)=><Link to="/criar-conta" className={`podium-card p${i+1}`} key={x.user_id}><span>{['🥇','🥈','🥉'][i]}</span><b>{x.username}</b><small>Nível {x.level}</small><strong>{x.points} pts</strong></Link>)}</div>}<div className="public-ranking-head"><span>#</span><span>JOGADOR</span><span>NÍVEL</span><span>PONTOS</span></div>{r.map(x=><Link to="/criar-conta" className="public-ranking-row" key={x.user_id}><strong>#{x.position}</strong><b>{x.username}</b><span>Lv. {x.level}</span><b>{x.points} pts</b></Link>)}{!r.length&&<div className="public-empty">O ranking está esperando os primeiros competidores.</div>}</>}
  </div>
  <section className="public-mini-cta"><b>Quer ver seu nome aqui?</b><span>Entre na Arena e comece a construir sua pontuação.</span><Link to="/criar-conta">Criar conta grátis →</Link></section>
 </PublicShell>
}

export function PublicResults(){
 const[r,setR]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(false);
 useEffect(()=>{let live=true;apiPublic('/public/results?limit=100').then(x=>{if(live)setR(x)}).catch(()=>{if(live)setError(true)}).finally(()=>{if(live)setLoading(false)});return()=>{live=false}},[]);
 return <PublicShell title="Resultados" description="Confira resultados e histórias das disputas do Batalha Farejador." ad>
  <section className="public-page-head public-page-head-v2"><span className="eyebrow">📊 HISTÓRIA DA ARENA</span><h1>Quem levou a melhor?</h1><p>Veja resultados registrados nas disputas e acompanhe os jogadores que já deixaram sua marca.</p></section>
  <div className="public-list">
   {loading||error?<PublicState loading={loading} error={error}/>:r.length?r.map((x,i)=><article className="public-result public-result-v2" key={`${x.tournament_id}-${x.username}-${i}`}><div><span className="public-status">RESULTADO</span><h2>{x.title}</h2><p><b>{x.username}</b> · {x.position}º lugar</p></div><div className="result-score"><span><b>{x.points}</b><small>pontos</small></span><span><b>{x.xp}</b><small>XP</small></span></div></article>):<div className="public-empty"><b>A história está começando.</b><span>Os próximos resultados podem ter o seu nome.</span></div>}
  </div>
  <section className="public-mini-cta"><b>Quer escrever seu próprio resultado?</b><span>Entre em uma disputa e comece sua trajetória.</span><Link to="/criar-conta">Começar agora →</Link></section>
 </PublicShell>
}

export function PublicPlayers(){
 const[r,setR]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(false);
 useEffect(()=>{let live=true;apiPublic('/public/players?limit=100').then(x=>{if(live)setR(x)}).catch(()=>{if(live)setError(true)}).finally(()=>{if(live)setLoading(false)});return()=>{live=false}},[]);
 return <PublicShell title="Jogadores" description="Conheça os jogadores da comunidade Batalha Farejador e veja quem está construindo sua carreira na Arena." ad>
  <section className="public-page-head public-page-head-v2"><span className="eyebrow">👤 A COMUNIDADE</span><h1>Quem está na Arena?</h1><p>Conheça os jogadores que estão construindo sua história. O próximo perfil pode ser o seu.</p></section>
  <div className="public-player-grid player-grid-v2">
   {loading||error?<PublicState loading={loading} error={error}/>:r.length?r.map(x=><Link to="/criar-conta" className="public-player-card public-player-card-v2" key={x.user_id}><span className="player-initials">{String(x.username||'?').slice(0,2).toUpperCase()}</span><b>{x.username}</b><span>Nível {x.level}</span><strong>{x.points} pts</strong><small>{x.xp} XP</small><em>Ver na Arena →</em></Link>):<div className="public-empty">Ainda não existem jogadores públicos.</div>}
  </div>
  <section className="public-mini-cta"><b>Seu nome pode aparecer aqui.</b><span>Crie sua conta e comece a construir sua carreira.</span><Link to="/criar-conta">Entrar para a Arena →</Link></section>
 </PublicShell>
}

export function PublicSeasons(){
 const[r,setR]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(false);
 useEffect(()=>{let live=true;apiPublic('/public/seasons?limit=20').then(x=>{if(live)setR(x)}).catch(()=>{if(live)setError(true)}).finally(()=>{if(live)setLoading(false)});return()=>{live=false}},[]);
 return <PublicShell title="Temporadas" description="Acompanhe as temporadas competitivas do Batalha Farejador e prepare-se para o próximo ciclo." ad>
  <section className="public-page-head public-page-head-v2"><span className="eyebrow">🔥 CICLOS DE COMPETIÇÃO</span><h1>Cada temporada é uma nova chance.</h1><p>As temporadas organizam a jornada competitiva e dão novos motivos para voltar à Arena.</p></section>
  <div className="public-season-grid season-grid-v2">
   {loading||error?<PublicState loading={loading} error={error}/>:r.length?r.map(x=><article className={`public-season-card public-season-card-v2 ${x.active?'active':''}`} key={x.public_id}><span>{x.active?'● TEMPORADA ATIVA':'TEMPORADA'}</span><h2>{x.name}</h2><p>Um novo ciclo para competir, evoluir e conquistar seu espaço.</p><small>{formatDate(x.starts_at)} → {formatDate(x.ends_at)}</small></article>):<div className="public-empty"><b>Nenhuma temporada disponível.</b><span>Uma nova fase pode começar em breve.</span></div>}
  </div>
  <section className="public-mini-cta"><b>Quer estar pronto para a próxima?</b><span>Conheça o jogo e entre na Arena.</span><Link to="/como-jogar">Aprender a jogar →</Link></section>
 </PublicShell>
}

function formatDate(value){
 if(!value)return 'Data não definida';
 const d=new Date(value);
 return Number.isNaN(d.getTime())?'Data não definida':d.toLocaleDateString('pt-BR');
}

const pages={
 '/como-jogar':['Como jogar','Descubra em poucos minutos como entrar em uma batalha e começar sua trajetória.',`O Batalha Farejador é uma disputa de estratégia e descoberta. Você escolhe uma edição, prepara seu card e entra em uma batalha contra outro jogador.

Durante o duelo, informações e possibilidades ajudam você a tomar decisões. O objetivo é interpretar o que está acontecendo, escolher bem suas ações e tentar descobrir as opções protegidas do adversário.

Você não precisa saber tudo antes de começar. Cada edição apresenta suas próprias regras, e a Arena mostra o que você precisa fazer em cada etapa.`],
 '/guias':['Guias','Aprenda as ideias que ajudam você a jogar melhor e aproveitar a Arena.',`Aqui você encontra conteúdos para entender cards, batalhas, torneios, ranking, XP e evolução.

Comece pelo básico, conheça o funcionamento de uma disputa e depois avance para estratégias. A melhor forma de aprender também é jogar: quanto mais você observa as partidas, mais fácil fica perceber padrões e tomar boas decisões.`],
 '/regras':['Regras','Entenda as regras de forma simples antes de entrar em uma disputa.',`Cada edição pode ter regras próprias. Antes de jogar, confira as condições apresentadas no torneio: número de jogadores, opções disponíveis, tentativas e tempo.

As escolhas feitas durante uma batalha seguem as regras da edição. Os resultados e a pontuação são registrados pela Arena para manter a disputa consistente entre os jogadores.`],
 '/sobre':['Sobre o Batalha Farejador','Uma arena criada para transformar descoberta em competição.',`O Batalha Farejador nasceu com uma ideia simples: criar uma experiência em que observar, pensar e decidir fazem diferença.

A plataforma reúne batalhas, torneios, ranking, temporadas, pontos, XP e uma comunidade de jogadores. A cada disputa, você tem a oportunidade de aprender, testar uma estratégia diferente e construir sua própria história na Arena.`],
 '/faq':['Perguntas frequentes','As respostas que você procura antes de entrar na Arena.',`O que é o Batalha Farejador?

É um jogo de estratégia e descoberta em que jogadores participam de batalhas e torneios.

Preciso criar uma conta?

Para jogar e participar das áreas competitivas, sim. A conta permite registrar sua evolução, seus resultados e sua posição no ranking.

É gratuito?

Existem edições com condições diferentes. Consulte cada torneio para saber como participar.

Como começo?

Crie sua conta, conheça as regras e escolha uma disputa disponível.

Posso acompanhar sem jogar?

Sim. Torneios, ranking, resultados, jogadores e temporadas podem ser acompanhados publicamente.`],
 '/contato':['Contato','Tem uma dúvida, sugestão ou quer falar com a equipe?',`O Batalha Farejador está sendo preparado para receber uma comunidade de jogadores. Sugestões, dúvidas e relatos ajudam a melhorar a experiência.

Use o canal oficial de atendimento informado no site quando a publicação definitiva estiver configurada.`],
 '/termos':['Termos de uso','As condições gerais para utilização do Batalha Farejador.',`Ao utilizar o Batalha Farejador, você concorda em respeitar as regras da plataforma e as condições específicas de cada disputa.

As regras podem evoluir para melhorar a experiência, preservar a integridade das competições e manter a plataforma segura para a comunidade.`],
 '/privacidade':['Política de privacidade','Informações sobre o tratamento de dados no Batalha Farejador.',`O Batalha Farejador utiliza informações necessárias para criar e manter contas, autenticar jogadores, proteger a plataforma, registrar partidas e oferecer recursos de progressão. Para segurança e administração, a plataforma também pode registrar dados técnicos de acesso, como IP, informações de conexão, navegador, sistema, dispositivo, idioma, fuso horário, tela, sessões, origem de acesso e atividades relacionadas à conta. Quando uma permissão do navegador for solicitada, como localização, câmera, microfone ou notificações, a decisão final é sempre do usuário e do navegador; a plataforma não deve tentar contornar essa decisão.

Alguns dados de conexão podem ser enriquecidos por um serviço de consulta de IP. A política definitiva deverá identificar o responsável, finalidades e bases legais, direitos dos titulares, retenção, compartilhamentos, medidas de segurança, canais oficiais e detalhes dos serviços de terceiros utilizados.`],
 '/cookies':['Política de cookies','Entenda como tecnologias de armazenamento podem ser utilizadas.',`O Batalha Farejador pode utilizar cookies necessários para manter sessões e identificar uma visita técnica, além de armazenamento local do navegador para uma identificação técnica do dispositivo usada na segurança. Esses mecanismos não devem armazenar senhas ou tokens de acesso em localStorage. Quando publicidade ou outros serviços de terceiros forem ativados, suas categorias, finalidades e opções de escolha deverão ser descritas conforme a configuração definitiva do site.`]
};

const guideCards=[
 ['🃏','Cards','Entenda o papel dos cards e como preparar sua escolha.'],
 ['🔎','Farejar o adversário','Aprenda a observar possibilidades e tomar decisões.'],
 ['⚔️','A batalha','Conheça o que acontece do início ao resultado.'],
 ['🏆','Torneios','Descubra como funcionam as diferentes edições.'],
 ['📈','Ranking e XP','Entenda como sua carreira pode evoluir.'],
 ['🔥','Temporadas','Veja como os ciclos competitivos organizam a Arena.']
];

export function PublicInfo({kind}){
 if(kind==='/guias')return <PublicGuides/>;
 if(kind==='/como-jogar')return <PublicHowToPlay/>;
 const p=pages[kind]||pages['/sobre'];
 const noAds=['/termos','/privacidade','/cookies'];
 const parts=p[2].split('\n\n');
 return <PublicShell title={p[0]} description={p[1]} ad={!noAds.includes(kind)}>
  <section className="public-article public-article-v2"><span className="eyebrow">{kind==='/faq'?'❓ DÚVIDAS':kind==='/sobre'?'🌟 A ARENA':'BATALHA FAREJADOR'}</span><h1>{p[0]}</h1><p className="article-intro">{p[1]}</p>{parts.map((x,i)=><p key={i}>{x}</p>)}</section>
 </PublicShell>
}

function PublicHowToPlay(){
 return <PublicShell title="Como jogar" description="Aprenda como funciona uma batalha do Batalha Farejador e veja como começar." ad>
  <section className="public-page-head public-page-head-v2"><span className="eyebrow">🎮 SEU PRIMEIRO PASSO</span><h1>Aprenda. Entre. Fareje.</h1><p>Em poucos passos você entende a ideia da Arena e já pode começar a sua jornada.</p><div className="page-head-actions"><CTA>Quero jogar →</CTA><CTA secondary to="/torneios">Ver torneios</CTA></div></section>
  <section className="public-section howto-grid-section"><div className="howto-intro"><span className="eyebrow">01 · ANTES DA BATALHA</span><h2>Escolha onde quer competir.</h2><p>Os torneios apresentam temas e condições diferentes. Leia a proposta da edição e escolha aquela que você quer enfrentar.</p></div><div className="howto-card"><b>🏆 Torneio</b><strong>Escolha sua disputa</strong><span>Veja vagas, categoria e condições antes de entrar.</span></div></section>
  <section className="public-section howto-grid-section reverse"><div className="howto-card"><b>🃏 Seu card</b><strong>Prepare sua estratégia</strong><span>Monte uma escolha compatível com a edição e entre na batalha.</span></div><div className="howto-intro"><span className="eyebrow">02 · PREPARAÇÃO</span><h2>Você entra com uma escolha.</h2><p>Seu card representa a preparação para o duelo. Pense no que faz sentido para aquela edição.</p></div></section>
  <section className="public-section howto-grid-section"><div className="howto-intro"><span className="eyebrow">03 · DURANTE O DUELO</span><h2>Observe antes de decidir.</h2><p>O desafio está em interpretar as possibilidades, testar suas hipóteses e tentar descobrir o que o adversário esconde.</p></div><div className="howto-card duel-howto"><b>🔎 Fareje</b><strong>Observe · Pense · Escolha</strong><span>Cada decisão ajuda a construir o resultado da batalha.</span></div></section>
  <section className="public-section"><div className="section-head"><span className="eyebrow">04 · DEPOIS DA BATALHA</span><h2>Seu resultado vira carreira.</h2><p className="public-section-lead">Pontos, XP, níveis, resultados e ranking dão continuidade à sua jornada.</p></div><div className="public-benefit-grid"><article><i>🏅</i><h3>Pontos</h3><p>Construa sua reputação competitiva.</p></article><article><i>⚡</i><h3>XP</h3><p>Avance na sua progressão.</p></article><article><i>👑</i><h3>Ranking</h3><p>Compare seu desempenho com a comunidade.</p></article><article><i>🔥</i><h3>Temporadas</h3><p>Volte para disputar novos ciclos.</p></article></div></section>
  <section className="public-section public-cta-section"><div className="final-cta"><span className="eyebrow">🚀 AGORA É COM VOCÊ</span><h2>Você já sabe o suficiente para começar.</h2><p>Entre na Arena e descubra na prática como funciona o seu faro.</p><CTA>Criar minha conta →</CTA></div></section>
 </PublicShell>
}

function PublicGuides(){
 return <PublicShell title="Guias" description="Guias do Batalha Farejador para aprender cards, batalhas, torneios, ranking e estratégias." ad>
  <section className="public-page-head public-page-head-v2"><span className="eyebrow">📚 APRENDA A FAREJAR</span><h1>Conheça o jogo.<br/><span className="title-accent">Jogue melhor.</span></h1><p>Conteúdo direto para você entender a Arena, preparar suas jogadas e evoluir com o tempo.</p></section>
  <section className="public-section guide-hub"><div className="guide-grid">{guideCards.map(([icon,title,text],i)=><Link to="/como-jogar" className="guide-card" key={title}><span>{String(i+1).padStart(2,'0')}</span><i>{icon}</i><h2>{title}</h2><p>{text}</p><b>Aprender →</b></Link>)}</div></section>
  <section className="public-section guide-cta"><div><span className="eyebrow">🧠 APRENDA JOGANDO</span><h2>O melhor guia é a sua primeira batalha.</h2><p>Conheça as regras, escolha uma edição e descubra seu estilo na Arena.</p></div><CTA>Entrar na Arena →</CTA></section>
 </PublicShell>
}
