# Painel de Gestão de Torneios

Interface separada do Centro de Monitoramento de Segurança.

- Backend: `http://127.0.0.1:8010`
- Painel: `http://127.0.0.1:5175`
- Usa as mesmas credenciais de administrador.
- Execute `npm install` e depois `npm run dev`.

O painel administra as configurações automáticas de `backend/config/torneios/torneios.json`, acompanha as edições criadas no banco e configura a economia em `backend/config/economia.json`.

As alterações de uma configuração são aplicadas às próximas edições. Uma edição já aberta/em andamento mantém seu snapshot de regras.
