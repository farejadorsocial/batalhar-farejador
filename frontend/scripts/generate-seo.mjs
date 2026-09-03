import fs from "node:fs";
import path from "node:path";

const root=process.cwd();
const publicDir=path.join(root,"public");
const siteUrl=String(process.env.VITE_SITE_URL||"").trim().replace(/\/$/,"");

fs.mkdirSync(publicDir,{recursive:true});

const routes=[
 "/",
 "/torneios",
 "/ranking",
 "/resultados",
 "/jogadores",
 "/temporadas",
 "/como-jogar",
 "/guias",
 "/faq",
 "/regras",
 "/sobre",
 "/contato",
 "/termos",
 "/privacidade",
 "/cookies"
];

let robots="User-agent: *\\nAllow: /\\n";
if(siteUrl)robots+=`Sitemap: ${siteUrl}/sitemap.xml\\n`;
fs.writeFileSync(path.join(publicDir,"robots.txt"),robots,"utf8");

if(siteUrl){
 const urls=routes.map(route=>`  <url><loc>${siteUrl}${route}</loc></url>`).join("\\n");
 const xml=`<?xml version="1.0" encoding="UTF-8"?>\\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\\n${urls}\\n</urlset>\\n`;
 fs.writeFileSync(path.join(publicDir,"sitemap.xml"),xml,"utf8");
}else{
 const sitemap=path.join(publicDir,"sitemap.xml");
 if(fs.existsSync(sitemap))fs.unlinkSync(sitemap);
}
