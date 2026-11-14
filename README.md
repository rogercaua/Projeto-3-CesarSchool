# Backend: Governança Cadastral da ESF (Recife)

API em **FastAPI + SQLAlchemy 2** para o fluxo de mudança do cadastro de unidades de saúde:
solicitação → análise do gestor (aprovar, devolver ou rejeitar) → atualização do cadastro oficial, tudo auditado.

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                   # Windows: copy .env.example .env
python -m app.seed                                     # dados de exemplo (opcional; use --recriar para apagar e refazer)
uvicorn app.main:app --reload
```

- **Aplicação (front-end):** http://localhost:8000/
- Documentação interativa da API: http://localhost:8000/docs
- Testes do backend: `pytest`
- No Swagger, obtenha um token em `POST /auth/dev-login` (informe e-mail, nome e papel) e clique em **Authorize**.

Para ver o fluxo completo, entre em abas anônimas diferentes com os perfis **Editor Técnico** (abre a solicitação), **Gestor de Informação** (aprova, devolve ou rejeita) e **Administrador** (auditoria).

### Dados de exemplo

`python -m app.seed` popula um banco vazio; `python -m app.seed --recriar` **apaga todas as tabelas** e popula de novo. Os dados são sempre os mesmos (semente fixa):

- 8 distritos sanitários e unidades em bairros de Recife (cerca de 1/4 sem CNES, algumas inativas);
- cerca de 250 solicitações nos últimos 18 meses, com mais pedidos nos meses recentes, dos 4 tipos;
- todos os fluxos: decisão direta, devolução seguida de reenvio e nova decisão, devolvidas aguardando o editor, canceladas pelo solicitante e pendentes recentes;
- aprovações aplicadas ao cadastro (inclusões viram unidades, inativações mudam o status), com snapshot na decisão;
- histórico de status (gravado pelos triggers) e trilha de auditoria com as datas de cada evento.

Para entrar como um dos usuários do seed, use no login o e-mail e o papel abaixo (o papel vem do login, não do banco):

| Papel | E-mail |
|---|---|
| EDITOR_TECNICO | carla.menezes@recife.pe.gov.br, bruno.albuquerque@recife.pe.gov.br, juliana.farias@recife.pe.gov.br |
| GESTOR_INFO | helena.cavalcanti@recife.pe.gov.br, marcos.vasconcelos@recife.pe.gov.br, patricia.lins@recife.pe.gov.br |
| ADMIN | rafael.siqueira@recife.pe.gov.br |
| LEITOR | luana.barros@recife.pe.gov.br |

## Estrutura

```
app/
  main.py            monta a aplicação e inclui os routers
  models.py          importa todos os modelos (create_all, seed, futuras migrações)
  seed.py            dados de exemplo (65 unidades de Recife, 8 usuários, 250 solicitações em 18 meses)
  core/              config, banco, JWT, criptografia (AES-GCM), schema de paginação
  modules/
    auth/            usuário local, papéis (RBAC), dependências de segurança e CRUD de usuários
    distritos/       cadastro de distritos sanitários
    unidades/        consulta ao cadastro oficial (somente leitura)
    solicitacoes/    fluxo de governança e decisões
    auditoria/       trilha de eventos imutável
    cnes/            consulta e conciliação com o CNES
    dashboard/       totais e estatísticas (indicadores e séries dos gráficos)
    banco/           views, triggers, funções SQL e procedimentos (sql/views.sql, sql/triggers.sql)
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
  dashboard.html           cards de resumo, painel estatístico (período, distrito, 6 gráficos) e tabela de unidades
  nova-solicitacao.html    inclusão, alteração, inativação ou reativação (também usada para corrigir e reenviar)
  pendencias.html          Central de Pendências (gestor/admin) e Minhas Solicitações (editor)
  solicitacao.html         comparativo atual × proposto, histórico e decisão
  conciliacao.html         divergências com o CNES
  distritos.html           cadastro de distritos sanitários (admin)
  auditoria.html           trilha de auditoria (admin)
  usuarios.html            cadastro de usuários (admin)
  banco.html               views com filtros e gráficos, procedimentos, funções e triggers (gestor/admin)
  css/style.css            estilos, com as cores e fontes do Figma
  js/                      api.js (chamadas e token), layout.js (barra lateral por papel), graficos.js (Chart.js), uma página por arquivo
```

- O token fica no `sessionStorage` e é enviado como `Authorization: Bearer`. Sem sessão, toda página volta ao login.
- A barra lateral e as ações mudam conforme o papel; o backend continua sendo quem autoriza de fato.
- Para servir o front em outro lugar (ex.: Live Server), ajuste `API_BASE` em `frontend/js/config.js` e inclua a origem em `CORS_ORIGINS`.
- A tela de login pergunta ao backend o modo ativo (`GET /auth/config`). Em `AUTH_MODE=dev` mostra o login simulado com escolha de perfil; em `AUTH_MODE=keycloak` mostra só o botão do SSO (ver [Login pelo Keycloak](#login-pelo-keycloak)).
- O servidor manda `Cache-Control: no-cache` nos arquivos do front: depois de atualizar o código, o navegador nunca mistura HTML novo com JS antigo.
- Os módulos JS exigem http(s): abrir os arquivos direto pelo disco (`file://`) não funciona.
- Os gráficos usam Chart.js 4.4.1 carregado do cdnjs; sem internet, as páginas funcionam e mostram um aviso no lugar dos gráficos.

## Regras de negócio

- **O cadastro oficial (`unidades`) não tem POST/PUT/DELETE.** Ele só muda quando um gestor aprova uma solicitação.
- Tipos de solicitação: `INCLUSAO`, `ALTERACAO`, `INATIVACAO`, `REATIVACAO`.
- Inativação só vale para unidade ativa, e reativação só para unidade inativa. Nos dois casos muda apenas o status, e `dados_propostos` é ignorado.
- Status: `PENDENTE` → `APROVADA` | `REJEITADA` | `DEVOLVIDA`; a devolvida volta a `PENDENTE` quando o editor reenvia (`PUT`).
- O solicitante pode cancelar uma solicitação `PENDENTE` ou `DEVOLVIDA`. `CANCELADA` é um estado final: o cadastro não muda, a solicitação continua no histórico e a justificativa fica na trilha de auditoria.
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
| Criar, editar e excluir distritos e usuários; ver auditoria | | | ✔ | |
| Consultas e Banco (views, funções, relatório por período, triggers) | | ✔ | ✔ | |
| Executar `sp_cancelar_paradas` | | | ✔ | |

## Endpoints

| Método e rota | Descrição |
|---|---|
| `GET /auth/config` | Público: modo de login (`dev` ou `keycloak`, com issuer e client_id) |
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
| `POST /solicitacoes/{id}/cancelamento` | Solicitante cancela uma solicitação em aberto |
| `POST /solicitacoes/{id}/decisao` | Gestor aprova, devolve ou rejeita |
| `GET /cnes/estabelecimentos/{codigo}` | Busca no CNES para o formulário |
| `GET /cnes/conciliacao` | Divergências entre a base local e o CNES |
| `GET/POST /distritos` | Lista (todos) e cria (admin) |
| `PUT/DELETE /distritos/{id}` | Edita e exclui (admin) |
| `GET /auditoria` | Trilha de auditoria (admin) |
| `GET /dashboard/estatisticas` | Indicadores e séries dos gráficos, filtros `inicio`, `fim`, `distrito_id` |
| `GET/POST /usuarios` | Lista (filtro `q`) e cria usuário (admin) |
| `PUT/DELETE /usuarios/{id}` | Edita e exclui usuário (admin) |
| `GET /banco/objetos` | Views, triggers, funções e procedimentos com o SQL de cada um |
| `GET /banco/views/{nome}` | Consulta uma view com os filtros que ela aceita |
| `POST /banco/funcoes/{nome}` | Executa uma função SQL com `{"argumentos": [...]}` |
| `GET /banco/procedimentos/sp_relatorio_periodo` | Indicadores de um período |
| `POST /banco/procedimentos/sp_cancelar_paradas` | Cancela solicitações paradas há mais de `dias` (admin) |
| `GET /banco/historico-status` | Histórico de status gravado pelos triggers (filtro `protocolo`) |

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

### CRUD

| Tabela | Criar | Ler | Atualizar | Excluir |
|---|---|---|---|---|
| `distritos` | tela Distritos | todas as telas | tela Distritos | tela Distritos (bloqueado se houver unidades) |
| `usuarios` | tela Usuários (ou primeiro login) | tela Usuários | tela Usuários | tela Usuários (bloqueado se houver vínculos) |
| `solicitacoes` | Nova Solicitação | Pendências, detalhe | reenvio da devolvida | cancelamento (exclusão lógica) |
| `unidades` | inclusão aprovada | Dashboard | alteração aprovada | inativação aprovada (exclusão lógica) |

As unidades só mudam pelo fluxo de aprovação (regra de negócio); por isso não há tela de edição direta.

### Views, funções, procedimentos e triggers (SQLite)

Ficam em `app/modules/banco/` e são recriados a cada inicialização (`instalar()` em `main.py` e no seed). Tudo pode ser visto e executado na tela **Consultas e Banco**.

| Objeto | O que faz | Onde aparece na interface |
|---|---|---|
| `vw_unidades_por_distrito` | totais, ativas, inativas, sem CNES e % com CNES por distrito | aba da tela Consultas; gráficos de distrito e radar do dashboard |
| `vw_solicitacoes_detalhadas` | solicitação + solicitante + unidade + distrito + última decisão + dias até decidir | aba com filtros de status, tipo, distrito e período; base do dashboard |
| `vw_desempenho_gestores` | decisões, aprovadas, devolvidas, rejeitadas, taxa de aprovação e média de dias por gestor | aba da tela Consultas |
| `vw_evolucao_mensal` | solicitações criadas por mês e situação atual | aba com filtro de período |
| `fn_percentual(parte, total)` | percentual com 1 casa | views; testável na tela |
| `fn_dias_entre(inicio, fim)` | dias entre duas datas | views; testável na tela |
| `fn_protocolo(id, criada_em)` | protocolo `SOL-AAAA-NNNN` | views; testável na tela |
| `sp_relatorio_periodo` | indicadores do período e variação sobre o período anterior | cards do dashboard; executável na tela |
| `sp_cancelar_paradas` | cancela solicitações em aberto sem movimentação há N dias | executável na tela (admin) |
| `trg_solicitacao_status_inicial` / `_mudou` | gravam cada mudança de status em `historico_status` | tabela "Efeito dos triggers" |
| `trg_distrito_bloqueia_exclusao` | impede excluir distrito com unidades | erro ao excluir na tela Distritos |
| `trg_auditoria_sem_update` / `_sem_delete` | auditoria imutável também no banco | — |
| `trg_unidade_cnes_insert` / `_update` | CNES precisa ter 7 dígitos | — |

O SQLite não tem `CREATE FUNCTION` nem `CREATE PROCEDURE`:

- As **funções** são escritas em Python e registradas em cada conexão com `sqlite3.create_function` (`funcoes.py`). Depois disso são chamadas no SQL como funções nativas.
- Os **procedimentos** são blocos de SQL parametrizados executados numa única transação (`service.py`), com o mesmo papel de uma stored procedure.
- As datas são gravadas em UTC; as consultas usam `'localtime'` para agrupar e filtrar no fuso do servidor.
- Os scripts são só para SQLite. Com PostgreSQL ou MySQL, `instalar()` não faz nada e as telas de consulta e o dashboard estatístico não funcionam.

### Criptografia simétrica (dados em repouso)

As justificativas (`solicitacoes.justificativa`, `decisoes.justificativa`) e os detalhes da auditoria (`auditoria_eventos.detalhes`, que repetem as justificativas) são gravados cifrados com **AES-256-GCM** (`app/core/crypto.py`, biblioteca `cryptography`).

- O tipo de coluna `Cifrado` cifra ao gravar e decifra ao ler: a API e o front continuam vendo texto normal, e quem abre o arquivo do banco vê só `enc:v1:<base64>`.
- Cada valor usa um nonce aleatório de 12 bytes, então o mesmo texto gera cifras diferentes.
- O GCM autentica os dados: um valor alterado direto no banco gera erro na leitura (`InvalidTag`) em vez de ser aceito.
- A chave fica em `CRIPTO_CHAVE` (32 bytes em base64, fora do banco). Gere uma com `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"`. Se a chave for perdida, os dados cifrados não podem ser recuperados.
- A chave padrão do código é pública e só vale para desenvolvimento: com `AUTH_MODE=keycloak`, a aplicação não inicia sem uma `CRIPTO_CHAVE` própria.
- Linhas gravadas antes da criptografia continuam legíveis e são cifradas na próxima vez em que forem salvas.
- Testes: `tests/test_cripto.py` confere que o banco não guarda o texto puro, que o nonce muda e que a adulteração é detectada.

## Autenticação

- `AUTH_MODE=dev`: login simulado, equivalente ao "simular perfil" do protótipo. Não use em produção.
- `AUTH_MODE=keycloak`: valida tokens RS256 pelo JWKS do realm (`KEYCLOAK_ISSUER`). Os papéis são lidos de `realm_access.roles`, então crie no Keycloak os quatro papéis com os mesmos nomes. O usuário local é criado no primeiro acesso.

### Login pelo Keycloak

Com `AUTH_MODE=keycloak`, a tela de login esconde o e-mail e os perfis simulados e mostra só **Entrar com o SSO da Prefeitura**. O fluxo é o OIDC Authorization Code com PKCE, sem biblioteca (`frontend/js/sso.js`):

1. O botão leva à página de login do Keycloak; a senha é digitada só lá.
2. O Keycloak volta para `index.html` com um código; o front confere o `state` e troca o código pelos tokens.
3. Quando o access token expira (401), o front usa o refresh token uma vez e repete a chamada.
4. **Sair** encerra também a sessão no Keycloak.

Variáveis: `AUTH_MODE=keycloak`, `KEYCLOAK_ISSUER`, `KEYCLOAK_CLIENT_ID` e uma `CRIPTO_CHAVE` própria (a aplicação não inicia sem elas).

No Keycloak, crie o cliente do front assim:

| Configuração | Valor |
|---|---|
| Client ID | o mesmo de `KEYCLOAK_CLIENT_ID` (ex.: `govcadastral-web`) |
| Client authentication | desligado (cliente público) |
| Standard flow | ligado; PKCE method `S256` |
| Valid redirect URIs | `http://localhost:8000/*` |
| Valid post logout redirect URIs | `http://localhost:8000/*` |
| Web origins | `http://localhost:8000` (libera o CORS da troca do código) |

Os tokens ficam no `sessionStorage` da aba (somem ao fechá-la). O refresh token fica ali também; o front escapa todo dado vindo da API, que é a defesa contra quem tentasse lê-lo por XSS.

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
- Telas do Figma sem endpoint: a parte de "Perfis" da tela "Usuários e Perfis" (os papéis são geridos no Keycloak; o cadastro de usuários existe) e o botão "Criar solicitação" da conciliação (só o editor cria solicitações, e o editor não acessa a conciliação).
- Sem migrações (Alembic), sem Docker e sem notificações; entram quando forem necessários.
