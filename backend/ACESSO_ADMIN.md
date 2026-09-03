# Acesso ao Centro de Monitoramento

O Centro de Monitoramento usa o mesmo backend FastAPI do Batalha Farejador e uma interface React separada em `admin/`.

## Credencial local inicial

- E-mail: `admin@farejador.local`
- Senha: `ChangeThisPassword123!`

Essa senha existe apenas para facilitar o primeiro teste local. Altere-a imediatamente usando `criar_admin.py`.

## Criar ou redefinir administrador

Dentro de `backend`:

```cmd
python criar_admin.py
```

O script usa o mesmo banco do servidor, mesmo quando o backend é iniciado a partir da raiz do projeto.

## Inicialização

Backend:

```cmd
cd backend
python run.py
```

Admin:

```cmd
cd admin
npm install
npm run dev
```

Painel: `http://127.0.0.1:5174`

Backend: `http://127.0.0.1:8010`
