# Teste da versão atual

## 1. Backend

Abra o CMD na pasta `backend`:

```bat
python run.py
```

O servidor deve ficar em:

`http://127.0.0.1:8010`

Teste no navegador:

`http://127.0.0.1:8010/health`

Resultado esperado:

```json
{"status":"ok","version":"2.0.0"}
```

## 2. Frontend

Em outro CMD:

```bat
cd frontend
npm install
npm run dev
```

Abra:

`http://localhost:5173`

## 3. Rotas públicas

Teste:

- `/`
- `/torneios`
- `/ranking`
- `/resultados`
- `/jogadores`
- `/temporadas`
- `/como-jogar`
- `/guias`
- `/faq`
- `/regras`
- `/sobre`
- `/contato`
- `/termos`
- `/privacidade`
- `/cookies`

## 4. Teste da área autenticada

Depois de criar/usar uma conta, confirme:

- Arena
- Torneio
- Duelo
- montagem do card
- saldo
- ranking autenticado
- perfil
- notificações
- logout

## 5. Teste de publicidade

Sem `VITE_ADSENSE_PUBLISHER_ID`, deve aparecer somente o espaço reservado e o navegador não deve carregar o script do AdSense.

Não coloque um ID fictício.

## 6. Teste de SEO

Com:

```bat
set VITE_SITE_URL=https://seu-dominio.com
npm run build
```

o build deve criar `dist/robots.txt` e `dist/sitemap.xml` usando o domínio informado.

Antes do domínio definitivo, não configure uma URL fictícia como domínio canônico.
