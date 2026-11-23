<div align="center">

# GovCadastral

### Governança Cadastral da Estratégia Saúde da Família — Recife

Controle das mudanças no cadastro de unidades de saúde: **solicitação → análise do gestor → atualização do cadastro oficial**, com tudo auditado.

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy_2-D71F00?logo=sqlalchemy&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![JavaScript](https://img.shields.io/badge/JS_puro-F7DF1E?logo=javascript&logoColor=black)
![Keycloak](https://img.shields.io/badge/Keycloak_%7C_LDAP-4D4D4D?logo=keycloak&logoColor=white)
![AWS S3](https://img.shields.io/badge/AWS_S3-569A31?logo=amazons3&logoColor=white)
![pytest](https://img.shields.io/badge/testes-pytest-0A9EDC?logo=pytest&logoColor=white)

</div>

---

## Sumário

- [Visão geral](#visão-geral)
- [Como rodar](#como-rodar)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Regras de negócio](#regras-de-negócio)
- [Permissões](#permissões)
- [Endpoints](#endpoints)
- [Banco de dados](#banco-de-dados)
- [Autenticação](#autenticação)
- [Segurança e Auditoria](#segurança-e-auditoria)
- [Exportação para a nuvem (S3)](#exportação-para-a-nuvem-s3)
- [Diferenças em relação ao ER](#diferenças-em-relação-ao-er)
- [Pendências](#pendências)

---

## Visão geral

O cadastro oficial das unidades **nunca é editado diretamente**. Toda mudança nasce como uma solicitação de um Editor Técnico e só é aplicada quando um Gestor de Informação a aprova.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> PENDENTE: Editor abre
    PENDENTE --> APROVADA: Gestor aprova
    PENDENTE --> REJEITADA: Gestor rejeita
    PENDENTE --> DEVOLVIDA: Gestor devolve
    DEVOLVIDA --> PENDENTE: Editor corrige e reenvia
    PENDENTE --> CANCELADA: Solicitante cancela
    DEVOLVIDA --> CANCELADA: Solicitante cancela
    APROVADA --> [*]: cadastro atualizado
    REJEITADA --> [*]
    CANCELADA --> [*]
```

| Perfil | O que faz |
|---|---|
| **Editor Técnico** | Abre solicitações de inclusão, alteração, inativação ou reativação de unidades |
| **Gestor de Informação** | Compara dados atuais × propostos e aprova, devolve ou rejeita |
| **Administrador** | Gerencia distritos e usuários e consulta a trilha de auditoria |
| **Leitor** | Consulta o dashboard e o cadastro |

---

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                # Windows: copy .env.example .env
python -m app.seed                                  # dados de exemplo (opcional)
uvicorn app.main:app --reload
```

| Recurso | Endereço |
|---|---|
| Aplicação (front-end) | http://localhost:8000/ |
| Documentação interativa da API (Swagger) | http://localhost:8000/docs |
| Testes | `pytest` |

> [!TIP]
> No Swagger, gere um token em `POST /auth/dev-login` (e-mail, nome e papel) e clique em **Authorize**.
> Para ver o fluxo completo, abra abas anônimas diferentes com os perfis **Editor Técnico**, **Gestor de Informação** e **Administrador**.

### Dados de exemplo

`python -m app.seed` popula um banco vazio. `python -m app.seed --recriar` **apaga todas as tabelas** e popula de novo. Os dados são sempre os mesmos (semente fixa):

- 8 distritos sanitários e 65 unidades em bairros do Recife (cerca de 1/4 sem CNES, algumas inativas);
- cerca de 250 solicitações nos últimos 18 meses, dos 4 tipos, com mais pedidos nos meses recentes;
- todos os fluxos: decisão direta, devolução seguida de reenvio e nova decisão, devolvidas aguardando o editor, canceladas e pendentes;
- aprovações aplicadas ao cadastro, com snapshot na decisão;
- histórico de status (gravado pelos triggers) e trilha de auditoria com as datas de cada evento.

<details>
<summary><b>Usuários do seed</b> (o papel vem do login, não do banco)</summary>

| Papel | E-mail |
|---|---|
| `EDITOR_TECNICO` | carla.menezes@recife.pe.gov.br, bruno.albuquerque@recife.pe.gov.br, juliana.farias@recife.pe.gov.br |
| `GESTOR_INFO` | helena.cavalcanti@recife.pe.gov.br, marcos.vasconcelos@recife.pe.gov.br, patricia.lins@recife.pe.gov.br |
| `ADMIN` | rafael.siqueira@recife.pe.gov.br |
| `LEITOR` | luana.barros@recife.pe.gov.br |

</details>

---

## Estrutura do projeto

```
app/
├── main.py            monta a aplicação e inclui os routers
├── models.py          importa todos os modelos (create_all, seed, futuras migrações)
├── seed.py            dados de exemplo
├── backup.py          backup do banco SQLite
├── core/              config, banco, JWT, criptografia (AES-GCM), paginação
└── modules/
    ├── auth/          usuário local, papéis (RBAC), login dev/Keycloak/LDAP, CRUD de usuários
    ├── distritos/     cadastro de distritos sanitários
    ├── unidades/      consulta ao cadastro oficial (somente leitura)
    ├── solicitacoes/  fluxo de governança e decisões
    ├── auditoria/     trilha de eventos imutável
    ├── cnes/          consulta e conciliação com o CNES
    ├── dashboard/     totais e estatísticas (indicadores e séries dos gráficos)
    ├── relatorios/    exportação de relatórios para o S3
    └── banco/         views, triggers, funções SQL e procedimentos
frontend/              interface em HTML, CSS e JavaScript puro (sem build)
infra/                 docker-compose do Keycloak e do OpenLDAP para testes
tests/                 testes da API (pytest)
```

Cada módulo tem `models.py`, `schemas.py`, `router.py` e, quando há regra de negócio, `service.py`.
O módulo `solicitacoes` usa `unidades`, `distritos`, `auditoria` e `auth`; só o `dashboard` importa `solicitacoes`.

### Front-end

Páginas estáticas servidas pelo próprio FastAPI na raiz (`/`): sem CORS e sem build, basta subir o backend.

| Página | Conteúdo |
|---|---|
| `index.html` | Login (simulado, LDAP ou SSO, conforme o modo) |
| `dashboard.html` | Cards de resumo, painel estatístico (período, distrito, 6 gráficos) e tabela de unidades |
| `nova-solicitacao.html` | Inclusão, alteração, inativação ou reativação (também usada para corrigir e reenviar) |
| `pendencias.html` | Central de Pendências (gestor/admin) e Minhas Solicitações (editor) |
| `solicitacao.html` | Comparativo atual × proposto, histórico e decisão |
| `conciliacao.html` | Divergências com o CNES |
| `distritos.html` | Cadastro de distritos sanitários (admin) |
| `usuarios.html` | Cadastro e anonimização de usuários (admin) |
| `auditoria.html` | Trilha de auditoria (admin) |
| `banco.html` | Views com filtros e gráficos, procedimentos, funções e triggers (gestor/admin) |

<details>
<summary><b>Detalhes do front-end</b></summary>

- `css/style.css` traz as cores e fontes do Figma. Em `js/`: `api.js` (chamadas e token), `layout.js` (barra lateral por papel), `graficos.js` (Chart.js) e um arquivo por página.
- O token fica no `sessionStorage` e é enviado como `Authorization: Bearer`. Sem sessão, toda página volta ao login.
- A barra lateral e as ações mudam conforme o papel; quem autoriza de fato é sempre o backend.
- Para servir o front em outro lugar (ex.: Live Server), ajuste `API_BASE` em `frontend/js/config.js` e inclua a origem em `CORS_ORIGINS`.
- A tela de login pergunta ao backend o modo ativo (`GET /auth/config`). Ver [Login pelo Keycloak](#login-pelo-keycloak).
- O servidor manda `Cache-Control: no-cache` nos arquivos do front: o navegador nunca mistura HTML novo com JS antigo.
- Os módulos JS exigem http(s): abrir os arquivos direto do disco (`file://`) não funciona.
- Os gráficos usam Chart.js 4.4.1 do cdnjs; sem internet, as páginas funcionam e mostram um aviso no lugar dos gráficos.

</details>

---

## Regras de negócio

> [!IMPORTANT]
> **O cadastro oficial (`unidades`) não tem POST/PUT/DELETE.** Ele só muda quando um gestor aprova uma solicitação.

- **Tipos de solicitação:** `INCLUSAO`, `ALTERACAO`, `INATIVACAO`, `REATIVACAO`.
- **Inativação** só vale para unidade ativa e **reativação** só para unidade inativa. Nos dois casos muda apenas o status, e `dados_propostos` é ignorado.
- **Cancelamento:** o solicitante pode cancelar uma solicitação `PENDENTE` ou `DEVOLVIDA`. `CANCELADA` é final: o cadastro não muda e a solicitação continua no histórico.
- **Justificativa obrigatória** em toda solicitação e em toda decisão.
- **Snapshot:** ao aprovar, os dados anteriores da unidade ficam em `decisoes.snapshot_anterior`.
- **Separação de funções:** quem abriu a solicitação não pode decidi-la, mesmo tendo o papel de gestor.
- **Distritos:** não aceitam nomes repetidos (sem diferenciar maiúsculas de minúsculas) e só podem ser excluídos sem unidades vinculadas. Solicitação em aberto que aponte para um distrito excluído é recusada na aprovação.
- **Auditoria:** toda operação grava um evento em `auditoria_eventos` na mesma transação. A tabela é imutável no ORM e no banco.

---

## Permissões

| Ação | Editor | Gestor | Admin | Leitor |
|---|:-:|:-:|:-:|:-:|
| Consultar unidades, distritos e dashboard | ✅ | ✅ | ✅ | ✅ |
| Criar e reenviar solicitações | ✅ | | | |
| Ver solicitações | só as suas | todas | todas | |
| Decidir solicitações | | ✅ | | |
| Conciliação CNES | | ✅ | ✅ | |
| Consulta de estabelecimento no CNES | ✅ | ✅ | ✅ | |
| Distritos e usuários (CRUD); auditoria | | | ✅ | |
| Consultas e Banco (views, funções, relatório, triggers) | | ✅ | ✅ | |
| Exportar relatórios para o S3 | | ✅ | ✅ | |
| Executar `sp_cancelar_paradas` | | | ✅ | |

---

## Endpoints

A lista completa e testável está no Swagger (`/docs`).

<details open>
<summary><b>Autenticação</b></summary>

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/auth/config` | Público: modo de login (`dev`, `ldap` ou `keycloak`) |
| `POST` | `/auth/dev-login` | Token de teste (só com `AUTH_MODE=dev`) |
| `POST` | `/auth/ldap-login` | Login por usuário e senha no LDAP (só com `AUTH_MODE=ldap`) |
| `GET` | `/auth/me` | Usuário e papéis do token |

</details>

<details open>
<summary><b>Solicitações</b></summary>

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/solicitacoes` | Abre solicitação (editor) |
| `GET` | `/solicitacoes` | Lista com filtros `status`, `tipo`, `unidade_id` |
| `GET` | `/solicitacoes/contagem` | Totais por status (abas da Central de Pendências) |
| `GET` | `/solicitacoes/{id}` | Detalhe com comparativo atual × proposto e decisões |
| `PUT` | `/solicitacoes/{id}` | Editor reenvia uma solicitação devolvida |
| `POST` | `/solicitacoes/{id}/cancelamento` | Solicitante cancela uma solicitação em aberto |
| `POST` | `/solicitacoes/{id}/decisao` | Gestor aprova, devolve ou rejeita |

Exemplo de alteração (só os campos enviados em `dados_propostos` mudam):

```json
{"tipo": "ALTERACAO", "unidade_id": 1, "dados_propostos": {"nome": "UBS Nova", "qtd_servicos": 9}, "justificativa": "Correção cadastral"}
```

</details>

<details>
<summary><b>Unidades, distritos, CNES e dashboard</b></summary>

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/unidades` | Lista com filtros `q`, `distrito_id`, `tipo`, `status`, `sem_cnes` e paginação |
| `GET` | `/unidades/{id}` | Detalhe |
| `GET` / `POST` | `/distritos` | Lista (todos) e cria (admin) |
| `PUT` / `DELETE` | `/distritos/{id}` | Edita e exclui (admin) |
| `GET` | `/cnes/estabelecimentos/{codigo}` | Busca no CNES para o formulário |
| `GET` | `/cnes/conciliacao` | Divergências entre a base local e o CNES |
| `GET` | `/dashboard/resumo` | Cards da tela inicial |
| `GET` | `/dashboard/estatisticas` | Indicadores e séries dos gráficos (`inicio`, `fim`, `distrito_id`) |

</details>

<details>
<summary><b>Administração e auditoria</b></summary>

| Método | Rota | Descrição |
|---|---|---|
| `GET` / `POST` | `/usuarios` | Lista (filtro `q`) e cria usuário (admin) |
| `PUT` / `DELETE` | `/usuarios/{id}` | Edita e exclui usuário (admin) |
| `POST` | `/usuarios/{id}/anonimizacao` | Apaga nome, e-mail e login e mantém o histórico (LGPD, admin) |
| `GET` | `/auditoria` | Trilha de auditoria (admin) |

</details>

<details>
<summary><b>Banco e relatórios</b></summary>

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/banco/objetos` | Views, triggers, funções e procedimentos com o SQL de cada um |
| `GET` | `/banco/views/{nome}` | Consulta uma view com os filtros que ela aceita |
| `POST` | `/banco/funcoes/{nome}` | Executa uma função SQL com `{"argumentos": [...]}` |
| `GET` | `/banco/procedimentos/sp_relatorio_periodo` | Indicadores de um período |
| `POST` | `/banco/procedimentos/sp_cancelar_paradas` | Cancela solicitações paradas há mais de `dias` (admin) |
| `GET` | `/banco/historico-status` | Histórico de status gravado pelos triggers (filtro `protocolo`) |
| `POST` | `/relatorios/exportar` | Gera o relatório do período em CSV e envia ao S3 |
| `GET` | `/relatorios` | Lista os relatórios já exportados |

</details>

---

## Banco de dados

Defina `DATABASE_URL` no `.env`. O padrão é **SQLite**, para rodar sem instalar nada. O mesmo código funciona com:

| Banco | `DATABASE_URL` | Driver |
|---|---|---|
| SQLite (padrão) | `sqlite:///./governanca.db` | — |
| PostgreSQL | `postgresql+psycopg2://usuario:senha@localhost/governanca_esf` | `psycopg2-binary` |
| MySQL | `mysql+pymysql://usuario:senha@localhost/governanca_esf` | `pymysql` |

As tabelas são criadas na inicialização (`create_all`). Quando o esquema estabilizar, troque por Alembic.

### CRUD

| Tabela | Criar | Ler | Atualizar | Excluir |
|---|---|---|---|---|
| `distritos` | tela Distritos | todas as telas | tela Distritos | tela Distritos (bloqueado se houver unidades) |
| `usuarios` | tela Usuários (ou primeiro login) | tela Usuários | tela Usuários | tela Usuários (bloqueado se houver vínculos; nesse caso, anonimizar) |
| `solicitacoes` | Nova Solicitação | Pendências, detalhe | reenvio da devolvida | cancelamento (exclusão lógica) |
| `unidades` | inclusão aprovada | Dashboard | alteração aprovada | inativação aprovada (exclusão lógica) |

### Views, funções, procedimentos e triggers (SQLite)

Ficam em `app/modules/banco/` e são recriados a cada inicialização (`instalar()` em `main.py` e no seed). Tudo pode ser visto e executado na tela **Consultas e Banco**.

| Objeto | O que faz | Onde aparece |
|---|---|---|
| `vw_unidades_por_distrito` | Totais, ativas, inativas, sem CNES e % com CNES por distrito | Tela Consultas; gráficos de distrito e radar do dashboard |
| `vw_solicitacoes_detalhadas` | Solicitação + solicitante + unidade + distrito + última decisão + dias até decidir | Aba com filtros; base do dashboard |
| `vw_desempenho_gestores` | Decisões, taxa de aprovação e média de dias por gestor | Tela Consultas |
| `vw_evolucao_mensal` | Solicitações criadas por mês e situação atual | Aba com filtro de período |
| `fn_percentual(parte, total)` | Percentual com 1 casa | Views; testável na tela |
| `fn_dias_entre(inicio, fim)` | Dias entre duas datas | Views; testável na tela |
| `fn_protocolo(id, criada_em)` | Protocolo `SOL-AAAA-NNNN` | Views; testável na tela |
| `sp_relatorio_periodo` | Indicadores do período e variação sobre o anterior | Cards do dashboard; executável na tela |
| `sp_cancelar_paradas` | Cancela solicitações em aberto sem movimentação há N dias | Executável na tela (admin) |
| `trg_solicitacao_status_inicial` / `_mudou` | Gravam cada mudança de status em `historico_status` | Tabela "Efeito dos triggers" |
| `trg_distrito_bloqueia_exclusao` | Impede excluir distrito com unidades | Erro ao excluir na tela Distritos |
| `trg_auditoria_sem_update` / `_sem_delete` | Auditoria imutável também no banco | — |
| `trg_unidade_cnes_insert` / `_update` | CNES precisa ter 7 dígitos | — |

<details>
<summary><b>Como funções e procedimentos funcionam no SQLite</b></summary>

O SQLite não tem `CREATE FUNCTION` nem `CREATE PROCEDURE`:

- As **funções** são escritas em Python e registradas em cada conexão com `sqlite3.create_function` (`funcoes.py`). Depois disso são chamadas no SQL como funções nativas.
- Os **procedimentos** são blocos de SQL parametrizados executados numa única transação (`service.py`), com o mesmo papel de uma stored procedure.
- As datas são gravadas em UTC; as consultas usam `'localtime'` para agrupar e filtrar no fuso do servidor.
- Os scripts são só para SQLite. Com PostgreSQL ou MySQL, `instalar()` não faz nada e as telas de consulta e o dashboard estatístico não funcionam.

</details>

### Criptografia dos dados em repouso

As justificativas (`solicitacoes.justificativa`, `decisoes.justificativa`) e os detalhes da auditoria (`auditoria_eventos.detalhes`) são gravados cifrados com **AES-256-GCM** (`app/core/crypto.py`).

- O tipo de coluna `Cifrado` cifra ao gravar e decifra ao ler: a API e o front veem texto normal, e quem abre o arquivo do banco vê só `enc:v1:<base64>`.
- Cada valor usa um nonce aleatório de 12 bytes, então o mesmo texto gera cifras diferentes.
- O GCM autentica os dados: um valor alterado direto no banco gera erro na leitura (`InvalidTag`).
- Linhas gravadas antes da criptografia continuam legíveis e são cifradas na próxima vez em que forem salvas.
- `tests/test_cripto.py` confere que o banco não guarda texto puro, que o nonce muda e que a adulteração é detectada.

> [!WARNING]
> A chave fica em `CRIPTO_CHAVE` (32 bytes em base64, fora do banco). **Se ela for perdida, os dados cifrados não podem ser recuperados.**
> A chave padrão do código é pública e só serve para desenvolvimento: com `AUTH_MODE=keycloak`, a aplicação não inicia sem uma chave própria. Para gerar uma:
>
> ```bash
> python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
> ```

---

## Autenticação

| Modo | Como funciona | Uso |
|---|---|---|
| `AUTH_MODE=dev` | Login simulado com escolha de perfil, como o "simular perfil" do protótipo | Desenvolvimento (**nunca em produção**) |
| `AUTH_MODE=keycloak` | Valida tokens RS256 pelo JWKS do realm; papéis lidos de `realm_access.roles` | Produção com SSO |
| `AUTH_MODE=ldap` | `POST /auth/ldap-login` faz o bind no LDAP e lê os grupos `posixGroup` do usuário | Produção com diretório LDAP |

Em qualquer modo, todo login bem-sucedido grava ou atualiza as tabelas locais `grupos` e `usuario_grupo` (`app/modules/auth/service.py::sincronizar_usuario`) com os papéis daquele login. No Keycloak e no LDAP, os quatro papéis precisam existir com os mesmos nomes do enum `Papel`.

### Login pelo Keycloak

A tela de login mostra só **Entrar com o SSO da Prefeitura**. O fluxo é o OIDC Authorization Code com PKCE, sem biblioteca (`frontend/js/sso.js`):

1. O botão leva à página de login do Keycloak; a senha é digitada só lá.
2. O Keycloak volta para `index.html` com um código; o front confere o `state` e troca o código pelos tokens.
3. Quando o access token expira (401), o front usa o refresh token uma vez e repete a chamada.
4. **Sair** encerra também a sessão no Keycloak.

Variáveis: `AUTH_MODE=keycloak`, `KEYCLOAK_ISSUER`, `KEYCLOAK_CLIENT_ID` e uma `CRIPTO_CHAVE` própria (a aplicação não inicia sem elas). Veja `infra/keycloak/` para subir um servidor de teste.

<details>
<summary><b>Configuração do cliente no Keycloak</b></summary>

| Configuração | Valor |
|---|---|
| Client ID | o mesmo de `KEYCLOAK_CLIENT_ID` (ex.: `govcadastral-web`) |
| Client authentication | desligado (cliente público) |
| Standard flow | ligado; PKCE method `S256` |
| Valid redirect URIs | `http://localhost:8000/*` |
| Valid post logout redirect URIs | `http://localhost:8000/*` |
| Web origins | `http://localhost:8000` (libera o CORS da troca do código) |

Os tokens ficam no `sessionStorage` da aba (somem ao fechá-la). O front escapa todo dado vindo da API, que é a defesa contra quem tentasse lê-los por XSS.

</details>

### Login pelo LDAP

`POST /auth/ldap-login` recebe usuário e senha, faz o bind contra `LDAP_URL` (`app/modules/auth/ldap_client.py`, biblioteca `ldap3`) e lê os grupos do usuário em `LDAP_GROUP_SEARCH_BASE`. Os grupos com o mesmo nome de um `Papel` viram os papéis do token local (HS256, igual ao modo `dev`).

| Variável | Obrigatória | Padrão |
|---|:-:|---|
| `LDAP_URL` | ✅ | — |
| `LDAP_BASE_DN` | ✅ | — |
| `LDAP_USER_DN_TEMPLATE` | | `uid={username},ou=people,{base_dn}` |
| `LDAP_GROUP_SEARCH_BASE` | | `ou=groups,{base_dn}` |

Veja `infra/openldap/` para subir um servidor de teste.

---

## Segurança e Auditoria

Riscos, RACI, ISO 38500, COBIT, LGPD, plano de auditoria e continuidade estão em **[`SEGURANCA_E_AUDITORIA.md`](SEGURANCA_E_AUDITORIA.md)** (e no PDF ao lado). No código:

| Controle | Onde |
|---|---|
| Trilha de auditoria imutável (ORM + triggers), gravada na mesma transação | `app/modules/auditoria/` |
| Login LDAP aceito ou recusado vira `LOGIN` / `LOGIN_FALHOU` (usuário e IP, nunca a senha) | `app/modules/auth/router.py` |
| Anonimização de usuário (LGPD) | `POST /usuarios/{id}/anonimizacao` |
| Criptografia AES-256-GCM das justificativas e da auditoria | `app/core/crypto.py` |
| Backup do SQLite com verificação de integridade | `python -m app.backup [--destino backups] [--manter 7]` |

---

## Exportação para a nuvem (S3)

`POST /relatorios/exportar` (Gestor ou Admin) gera o mesmo relatório de indicadores do dashboard (`sp_relatorio_periodo`, com `inicio`, `fim` e `distrito_id` opcionais) em CSV e envia ao Amazon S3 via `boto3` (`app/modules/relatorios/service.py`). `GET /relatorios` lista o que já foi exportado, e cada exportação vira um evento na auditoria.

Variáveis: `AWS_REGION` e `S3_BUCKET` (o bucket precisa existir).

> [!NOTE]
> As credenciais da AWS **não** ficam nas variáveis do projeto. O `boto3` lê `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_SESSION_TOKEN` do ambiente (como nas credenciais temporárias do AWS Academy Learner Lab) ou de `~/.aws/credentials`, e assina cada chamada com AWS Signature Version 4.

---

## Diferenças em relação ao ER

| ER original | Aqui | Motivo |
|---|---|---|
| `grupo`, `papel`, `usuario_papel` | `grupos` + `usuario_grupo` | Espelho local, reescrito a cada login a partir do IdP (Keycloak ou LDAP), que continua sendo a fonte da verdade |
| `equipe`, `profissional` | Fora do escopo | Nenhuma tela ou fluxo do protótipo usa |
| `equipamento`, `servico` | `qtd_equipamentos` e `qtd_servicos` na unidade | O dashboard só exibe quantidades |
| `pendencia` | Decisão `DEVOLVIDA` com justificativa | Evita uma tabela para o mesmo conceito |
| `unidade_historico` | `decisoes.snapshot_anterior` (JSON) | Mesma informação, uma tabela a menos |
| `conciliacao_cnes` | Calculada na hora por `/cnes/conciliacao` | Não precisa de persistência |
| `valor_atual` / `valor_proposto` (texto) | `dados_atuais` / `dados_propostos` (JSON) | Permite alterar vários campos em um pedido |

---

## Pendências

- [ ] `app/modules/cnes/client.py` usa **dados simulados**.
- [ ] Migrações (Alembic), Docker da aplicação e notificações, quando forem necessários.
