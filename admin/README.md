# Batalha Farejador — Centro de Monitoramento

Interface administrativa independente do sistema do jogador, usando o **mesmo backend FastAPI**.

## Criar/redefinir o administrador

Na pasta `backend`, execute:

```cmd
python criar_admin.py
```

O script pede e-mail, nome de usuário e uma nova senha. Ele cria a conta se não existir ou transforma/redefine uma conta existente como administrador.

Isso evita depender de uma senha fixa no código.

### Conta local que já vem no banco desta versão

- E-mail: `admin@farejador.local`
- Senha inicial: `ChangeThisPassword123!`

**Recomendação:** use `python criar_admin.py` para trocar essa senha antes de colocar o sistema na internet.

## Executar o painel

1. Abra o backend FastAPI normalmente na porta `8010`.
2. Entre na pasta `admin`.
3. Execute `npm install`.
4. Execute `npm run dev`.
5. Abra `http://127.0.0.1:5174`.

Para outro endereço da API, crie `admin/.env` com:

`VITE_API_URL=http://127.0.0.1:8010/api`

O acesso usa o mesmo endpoint de autenticação do Batalha Farejador, mas somente contas com `role=admin` entram no centro.

## Evolução desta versão

O painel agora inclui uma camada de inteligência operacional:
- score de risco explicável por usuário;
- sinais de sessões simultâneas, quantidade de IPs/dispositivos e volume de eventos;
- correlação de IP compartilhado entre contas;
- correlação de dispositivo compartilhado entre contas;
- dossiê individual com sessões, conexões, dispositivos, atividades, permissões e auditoria;
- ações administrativas continuam registradas em auditoria;
- correlações são sinais para investigação, não punição automática.

O painel é `noindex/nofollow` e não contém anúncios.


## Evolução visual e visitantes

- nova área **Visitantes** com histórico anônimo e técnico;
- IP, tipo de IP, ISP, organização, ASN, país, região, cidade e fuso quando disponíveis;
- User-Agent completo acessível por tooltip, com leitura resumida na tabela;
- navegador, sistema, plataforma, tela, idioma e outros dados técnicos fornecidos pelo navegador;
- origem/referer e parâmetros UTM;
- dossiê individual do visitante com conexões e atividades;
- horários do Centro de Monitoramento são exibidos explicitamente no fuso **America/Sao_Paulo (Brasília)**;
- confirmações administrativas usam janela interna do painel, em vez das caixas nativas do navegador;
- botões possuem estados visuais de hover, foco, clique e processamento;
- quando o usuário concede localização, o dossiê mostra latitude, longitude, precisão e horário da obtenção, com opção de abrir o ponto em mapa;
- câmera e microfone continuam sendo solicitados somente por ação explícita do usuário, e as faixas de mídia são encerradas imediatamente após a verificação.
