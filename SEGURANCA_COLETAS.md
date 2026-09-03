# Segurança e coleta de dados — Batalha Farejador

Esta etapa adiciona a infraestrutura de observabilidade e moderação necessária para o futuro painel administrativo.

## O que passa a ser registrado

- visitante anônimo e origem inicial (referer/UTM);
- sessões autenticadas e encerramento de sessão;
- IP e tipo IPv4/IPv6;
- enriquecimento do IP pelo IPInfo no backend;
- ISP/organização/ASN/país/região/cidade/fuso quando o IPInfo retornar esses dados;
- user-agent, navegador/versão, sistema, plataforma e modelo quando disponível;
- idioma, fuso horário, resolução da tela, pixel ratio e suporte a toque;
- atividades de autenticação e contexto do cliente;
- estado de permissões do navegador;
- ações administrativas e seus motivos;
- status da conta: ativa, suspensa, desabilitada ou banida;
- sinalização e campo de risco preparados para a camada de análise.

Senhas, access tokens e refresh tokens não são gravados nos logs de atividade.

## IPInfo

A consulta é feita exclusivamente no backend:

`https://ipinfo.io/{ip}/json`

A falha ou indisponibilidade do IPInfo não impede cadastro ou login. O projeto usa timeout e trata exceções.

Configure no ambiente:

- `IPINFO_TIMEOUT_SECONDS` — timeout da consulta;
- `TRUST_PROXY_HEADERS=true` somente quando a aplicação estiver atrás de um proxy/reverse proxy realmente confiável.

Não habilite `TRUST_PROXY_HEADERS` em uma instalação direta na internet sem proxy confiável, pois cabeçalhos de encaminhamento podem ser falsificados.

## Permissões do navegador

O administrador pode criar uma solicitação para:

- localização;
- câmera;
- microfone;
- notificações.

A plataforma **não força** nenhuma permissão. O usuário recebe uma solicitação visível e precisa clicar para iniciar a solicitação do navegador.

Quando concedida:

- localização: são enviados latitude, longitude, precisão e timestamp;
- câmera/microfone: o navegador é consultado e as faixas são imediatamente encerradas; nenhum áudio ou vídeo é armazenado;
- notificações: somente o estado de autorização é registrado.

## Endpoints principais

Autenticados:

- `POST /api/security/client-context`
- `GET /api/security/permissions/pending`
- `GET /api/security/permissions`
- `POST /api/security/permissions/{permission}/resolve`

Administrativos:

- `GET /api/security/admin/overview`
- `GET /api/security/admin/users`
- `GET /api/security/admin/users/{user_id}`
- `POST /api/security/admin/users/{user_id}/action`
- `POST /api/security/admin/users/{user_id}/permission-request`
- `POST /api/security/admin/sessions/{session_id}/terminate`

## Moderação

As ações administrativas já suportadas são:

- `ban`
- `suspend`
- `disable`
- `enable`
- `unban`
- `terminate_sessions`
- `flag`
- `unflag`

Cada ação gera registro de auditoria com administrador, alvo, ação, motivo e data.

O bloqueio não depende somente de IP ou dispositivo. A estrutura foi preparada para que a futura camada de risco combine sinais antes de uma decisão automática.

## Próxima camada

A coleta agora funciona como a base de dados do futuro painel. A próxima evolução natural é ampliar o painel administrativo com filtros, linha do tempo, busca por IP/dispositivo, visão de sessões, detalhes de risco e regras de detecção de comportamento suspeito.
