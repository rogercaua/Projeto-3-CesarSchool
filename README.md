# Backend: Governança Cadastral da ESF (Recife)

API em **FastAPI + SQLAlchemy 2** para o fluxo de mudança do cadastro de unidades de saúde:
solicitação → análise do gestor (aprovar, devolver ou rejeitar) → atualização do cadastro oficial, tudo auditado.

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                   # Windows: copy .env.example .env
python -m app.seed                                     # dados de exemplo (opcional)
uvicorn app.main:app --reload
```

- **Aplicação (front-end):** http://localhost:8000/
- Documentação interativa da API: http://localhost:8000/docs
- Testes do backend: `pytest`
- No Swagger, obtenha um token em `POST /auth/dev-login` (informe e-mail, nome e papel) e clique em **Authorize**.

Para ver o fluxo completo, entre em abas anônimas diferentes com os perfis **Editor Técnico** (abre a solicitação), **Gestor de Informação** (aprova, devolve ou rejeita) e **Administrador** (auditoria).

## Estrutura

```
app/
  main.py            monta a aplicação e inclui os routers
  models.py          importa todos os modelos (create_all, seed, futuras migrações)
  seed.py            dados de exemplo
  core/              config, banco, JWT, schema de paginação
  modules/
    auth/            usuário local, papéis (RBAC) e dependências de segurança
    distritos/       cadastro de distritos sanitários
    unidades/        consulta ao cadastro oficial (somente leitura)
    solicitacoes/    fluxo de governança e decisões
    auditoria/       trilha de eventos imutável
    cnes/            consulta e conciliação com o CNES
    dashboard/       totais da tela inicial
tests/               testes do fluxo completo (API)
frontend/            interface em HTML, CSS e JavaScript puro (sem build)
```

Cada módulo tem `models.py`, `schemas.py`, `router.py` e, quando há regra de negócio, `service.py`.
O módulo `solicitacoes` usa `unidades`, `distritos`, `auditoria` e `auth`; só o `dashboard` importa `solicitacoes`.

## Front-end

Páginas estáticas em `frontend/`, servidas pelo próprio FastAPI na raiz (`/`), então não há CORS nem build: basta subir o backend.

```
frontend/
  index.html               login
  dashboard.html           cards de resumo, filtros e tabela de unidades
  nova-solicitacao.html    inclusão, alteração, inativação ou reativação (também usada para corrigir e reenviar)
  pendencias.html          Central de Pendências (gestor/admin) e Minhas Solicitações (editor)
  solicitacao.html         comparativo atual × proposto, histórico e decisão
  conciliacao.html         divergências com o CNES
  distritos.html           cadastro de distritos sanitários (admin)
  auditoria.html           trilha de auditoria (admin)
  css/style.css            estilos, com as cores e fontes do Figma
  js/                      api.js (chamadas e token), layout.js (barra lateral por papel), uma página por arquivo
```

- O token fica no `sessionStorage` e é enviado como `Authorization: Bearer`. Sem sessão, toda página volta ao login.
- A barra lateral e as ações mudam conforme o papel; o backend continua sendo quem autoriza de fato.
- Para servir o front em outro lugar (ex.: Live Server), ajuste `API_BASE` em `frontend/js/config.js` e inclua a origem em `CORS_ORIGINS`.
- O login do front usa `POST /auth/dev-login`. Com `AUTH_MODE=keycloak` essa rota não existe; o login real exigiria o fluxo OIDC do Keycloak (por exemplo, `keycloak-js`), que ainda não foi implementado.
- Os módulos JS exigem http(s): abrir os arquivos direto pelo disco (`file://`) não funciona.

## Regras de negócio

- **O cadastro oficial (`unidades`) não tem POST/PUT/DELETE.** Ele só muda quando um gestor aprova uma solicitação.
- Tipos de solicitação: `INCLUSAO`, `ALTERACAO`, `INATIVACAO`, `REATIVACAO`.
- Inativação só vale para unidade ativa, e reativação só para unidade inativa. Nos dois casos muda apenas o status, e `dados_propostos` é ignorado.
- Status: `PENDENTE` → `APROVADA` | `REJEITADA` | `DEVOLVIDA`; a devolvida volta a `PENDENTE` quando o editor reenvia (`PUT`).
- A justificativa é obrigatória em toda solicitação e em toda decisão.
- Ao aprovar, os dados anteriores da unidade ficam em `decisoes.snapshot_anterior`.
- Separação de funções: quem abriu a solicitação não pode decidi-la, mesmo que também tenha o papel de gestor.
- Distritos não aceitam nomes repetidos (sem diferenciar maiúsculas de minúsculas) e só podem ser excluídos se não tiverem unidades vinculadas. Solicitação em aberto que aponte para um distrito excluído é recusada na aprovação.
- Toda operação grava um evento em `auditoria_eventos` na mesma transação. A tabela é imutável (updates e deletes são bloqueados pelo SQLAlchemy).

## Permissões

| Ação | EDITOR_TECNICO | GESTOR_INFO | ADMIN | LEITOR |
|---|:-:|:-:|:-:|:-:|
| Consultar unidades, distritos e dashboard | ✔ | ✔ | ✔ | ✔ |
| Criar e reenviar solicitações | ✔ | | | |
| Ver solicitações | só as suas | todas | todas | |
| Decidir solicitações | | ✔ | | |
| Conciliação CNES | | ✔ | ✔ | |
| Consulta de estabelecimento no CNES | ✔ | ✔ | ✔ | |
| Criar, editar e excluir distritos; ver auditoria | | | ✔ | |

## Endpoints

| Método e rota | Descrição |
|---|---|
| `POST /auth/dev-login` | Token de teste (só com `AUTH_MODE=dev`) |
| `GET /auth/me` | Usuário e papéis do token |
| `GET /dashboard/resumo` | Cards da tela inicial |
| `GET /unidades` | Lista com filtros `q`, `distrito_id`, `tipo`, `status`, `sem_cnes` e paginação |
| `GET /unidades/{id}` | Detalhe |
| `POST /solicitacoes` | Abre solicitação (editor) |
| `GET /solicitacoes` | Lista com filtros `status`, `tipo`, `unidade_id` |
| `GET /solicitacoes/contagem` | Totais por status (abas da Central de Pendências) |
| `GET /solicitacoes/{id}` | Detalhe com comparativo atual × proposto e decisões |
| `PUT /solicitacoes/{id}` | Editor reenvia uma solicitação devolvida |
| `POST /solicitacoes/{id}/decisao` | Gestor aprova, devolve ou rejeita |
| `GET /cnes/estabelecimentos/{codigo}` | Busca no CNES para o formulário |
| `GET /cnes/conciliacao` | Divergências entre a base local e o CNES |
| `GET/POST /distritos` | Lista (todos) e cria (admin) |
| `PUT/DELETE /distritos/{id}` | Edita e exclui (admin) |
| `GET /auditoria` | Trilha de auditoria (admin) |

Exemplo de alteração:

```json
{"tipo": "ALTERACAO", "unidade_id": 1, "dados_propostos": {"nome": "UBS Nova", "qtd_servicos": 9}, "justificativa": "Correção cadastral"}
```

Só os campos enviados em `dados_propostos` são alterados.

## Banco de dados

Defina `DATABASE_URL` no `.env`. O padrão é SQLite, para rodar sem instalar nada. O código é o mesmo para os três bancos do projeto:

- PostgreSQL: `postgresql+psycopg2://usuario:senha@localhost/governanca_esf` (instale `psycopg2-binary`)
- MySQL: `mysql+pymysql://usuario:senha@localhost/governanca_esf` (instale `pymysql`)

As tabelas são criadas na inicialização (`create_all`). Quando o esquema estabilizar, troque por Alembic.

## Autenticação

- `AUTH_MODE=dev`: login simulado, equivalente ao "simular perfil" do protótipo. Não use em produção.
- `AUTH_MODE=keycloak`: valida tokens RS256 pelo JWKS do realm (`KEYCLOAK_ISSUER`). Os papéis são lidos de `realm_access.roles`, então crie no Keycloak os quatro papéis com os mesmos nomes. O usuário local é criado no primeiro acesso.

## O que foi simplificado em relação ao ER

| ER original | Aqui | Motivo |
|---|---|---|
| `grupo`, `papel`, `usuario_papel` | Papéis vêm do token; `usuarios` guarda só o espelho do Keycloak | O Keycloak já é a fonte dos papéis |
| `equipe`, `profissional` | Fora do escopo | Nenhuma tela ou fluxo do protótipo usa |
| `equipamento`, `servico` | `qtd_equipamentos` e `qtd_servicos` na unidade | O dashboard só exibe quantidades |
| `pendencia` | A decisão `DEVOLVIDA` e sua justificativa fazem esse papel | Evita uma tabela para o mesmo conceito |
| `unidade_historico` | `decisoes.snapshot_anterior` (JSON) | Mesma informação, uma tabela a menos |
| `conciliacao_cnes` | Calculada na hora por `/cnes/conciliacao` | Não precisa de persistência |
| `valor_atual` / `valor_proposto` (texto) | `dados_atuais` / `dados_propostos` (JSON) | Permite alterar vários campos em um pedido |

## Pendência

- `app/modules/cnes/client.py` usa **dados simulados**. Troque o método `buscar` pela chamada real à API do CNES.
- O login do front é o simulado (dev). A integração com o SSO do Keycloak no navegador ainda não existe.
- Telas do Figma sem endpoint: "Usuários e Perfis" (os papéis são geridos no Keycloak) e o botão "Criar solicitação" da conciliação (só o editor cria solicitações, e o editor não acessa a conciliação).
- Sem migrações (Alembic), sem Docker e sem notificações; entram quando forem necessários.
