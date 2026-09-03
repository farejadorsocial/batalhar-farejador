# Batalha Farejador — preparação para Google AdSense

Esta versão mantém a Arena autenticada separada da camada pública e deixa a primeira edição preparada para receber anúncios depois que o domínio e a conta do AdSense estiverem configurados.

## Camada pública

Rotas públicas preparadas:

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

As páginas públicas não exigem login. A Arena, duelos, saldo, perfil, notificações e administração continuam protegidos pela autenticação existente.

## Anúncios

O componente central é `frontend/src/components/AdSlot.jsx`.

Enquanto `VITE_ADSENSE_PUBLISHER_ID` estiver vazio, ele mostra apenas um placeholder e **não carrega o script do Google**.

Quando o ID real for configurado, o componente passa a criar o bloco do AdSense.

### Áreas preparadas para publicidade

- Home pública
- Torneios
- Ranking
- Resultados
- Jogadores
- Temporadas
- Como jogar
- Guias
- FAQ
- Sobre
- Regras
- Contato

### Áreas sem publicidade

- Arena autenticada
- Duelo
- Escolha/montagem do card durante o jogo
- Confirmação de entrada
- Saldo
- Login
- Cadastro
- Perfil
- Notificações
- Administração
- Termos
- Privacidade
- Cookies

A separação existe para preservar a experiência do jogo e reduzir a possibilidade de publicidade ficar próxima de ações interativas.

## Segurança da camada pública

Os endpoints públicos retornam somente dados destinados à exibição pública.

O ranking público, por exemplo, não devolve saldo, e-mail, senha, token ou outros dados privados da conta.

## SEO

O build executa `npm run seo` antes do Vite.

Se `VITE_SITE_URL` estiver configurado, o build gera:

- `robots.txt`
- `sitemap.xml`

com URLs absolutas do domínio informado.

Sem domínio configurado, somente o `robots.txt` básico é gerado e o sitemap não é criado com endereço fictício.

As páginas públicas também atualizam:

- `<title>`
- `description`
- Open Graph
- Twitter Card
- canonical, quando `VITE_SITE_URL` existe

## Antes da publicação

1. Defina o domínio real.
2. Publique frontend e backend em HTTPS.
3. Configure `VITE_SITE_URL`.
4. Configure `VITE_API_URL`.
5. Teste todas as rotas públicas e a área autenticada.
6. Complete Termos, Privacidade, Cookies e Contato com os dados oficiais do responsável.
7. Crie o `ads.txt` usando exatamente a informação fornecida pelo Google depois da configuração do AdSense.
8. Configure `VITE_ADSENSE_PUBLISHER_ID` somente com o ID real fornecido pelo Google.
9. Faça uma revisão visual em computador e celular.
10. Solicite a avaliação do site no AdSense.

## Importante

Não existe garantia de aprovação do AdSense. A preparação técnica não substitui conteúdo original, qualidade, conformidade com as políticas, dados legais corretos e revisão do Google.

Não devem ser usados cliques próprios, tráfego artificial, incentivo a cliques ou qualquer técnica para manipular impressões/receita.
