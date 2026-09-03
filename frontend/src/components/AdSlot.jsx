import{useEffect,useRef}from'react';

const publisher=String(import.meta.env.VITE_ADSENSE_PUBLISHER_ID||'').trim();

export function AdSlot({slot='',format='auto',responsive=true}){
 const adRef=useRef(null);
 useEffect(()=>{
  if(!publisher||!adRef.current)return;
  window.adsbygoogle=window.adsbygoogle||[];
  let script=document.querySelector('script[data-bf-adsense]');
  if(!script){
   script=document.createElement('script');
   script.async=true;
   script.src=`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-${publisher}`;
   script.crossOrigin='anonymous';
   script.dataset.bfAdsense='true';
   document.head.appendChild(script);
  }
  const ad=adRef.current;
  if(!ad.dataset.bfAdReady){
   ad.dataset.bfAdReady='true';
   try{window.adsbygoogle.push({})}catch{}
  }
 },[]);

 if(!publisher)return <div className="ad-slot-placeholder" aria-hidden="true"><span>Espaço publicitário</span></div>;
 return <div className="ad-slot" aria-label="Publicidade">
  <ins ref={adRef} className="adsbygoogle" style={{display:'block'}} data-ad-client={`ca-${publisher}`} data-ad-slot={slot||undefined} data-ad-format={format} data-full-width-responsive={responsive?'true':'false'} />
 </div>;
}
