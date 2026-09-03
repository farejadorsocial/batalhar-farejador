# V10 — Estado competitivo e montagem do card

## O que foi corrigido

### 1. Empate agora é um estado visível
- O servidor mantém o mesmo duelo como `pending` e incrementa `replay_number`.
- Os ataques do empate são limpos para iniciar o replay corretamente.
- É criado evento `match_replay` no histórico.
- Os dois jogadores recebem notificação de empate/replay.
- A Arena mostra `REPLAY ATIVO` e explica: ninguém foi eliminado e o jogador deve aguardar/jogar novamente.
- A chave identifica o replay.

### 2. Eliminação agora é explícita
- Quando um duelo termina com vencedor, o vencedor recebe estado de avanço e o perdedor recebe estado de eliminação.
- A Arena mostra `VOCÊ FOI ELIMINADO` para quem perdeu.
- A mensagem explica a próxima ação: acompanhar classificação ou voltar para a próxima edição.
- O histórico também registra o encerramento.

### 3. Vitória/avanço
- O jogador que venceu recebe `VOCÊ AVANÇOU` quando ainda não existe uma próxima partida disponível.
- A Arena orienta a acompanhar a chave enquanto a próxima rodada é preparada.
- Quando a próxima partida já existe, a Arena mostra o duelo ativo normalmente.

### 4. Montagem do card mais informativa
- Contador `1/2`, `2/2` etc.
- Cada slot mostra se está preenchido.
- O botão informa exatamente quantas opções faltam.
- Depois de criar o card, aparece `SEU CARD ESTÁ PRONTO`.
- Entrada gratuita/paga fica explícita antes de participar.
- A interface explica o que acontece depois de bloquear o card.
- Após entrar, o builder é substituído por `INSCRIÇÃO CONFIRMADA`.
- O usuário recebe indicação clara de que não precisa fazer mais nada até o duelo.

## Testes
- `10 passed` nos testes de configuração, cards e lifecycle.
- Foram adicionados testes específicos para replay de empate e eliminação/avanço.
- Backend passou em `compileall`.

## Observação
O build do frontend pode exigir `npm install`/`npm ci` na máquina local porque este ZIP não inclui `node_modules`.
