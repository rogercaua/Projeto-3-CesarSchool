# Segurança e Auditoria — Governança Cadastral da ESF (Recife)

Este documento atende aos requisitos técnicos de Segurança e Auditoria do Projeto 3 (unidades SR1 e SR2).

**Adaptação do case.** O enunciado fala em "55 fornecedores", "diagnóstico de sustentabilidade" e "scorecard". No nosso sistema esses conceitos correspondem a:

| Termo do enunciado | No sistema de Governança Cadastral |
|---|---|
| Fornecedores avaliados | As **65 unidades de saúde** dos 8 distritos sanitários, cujos dados são enviados pelos Editores Técnicos |
| Formulário de diagnóstico | O formulário de **solicitação de mudança cadastral** (inclusão, alteração, inativação, reativação) |
| Evidências enviadas | Os dados propostos e a justificativa de cada solicitação, conferidos contra o **CNES** |
| Scorecard de sustentabilidade | O **dashboard de indicadores** (cobertura de CNES, tempo de decisão, taxa de aprovação, `sp_relatorio_periodo`) |
| Sistema de monitoramento | A própria aplicação (FastAPI + SQLite) e a exportação de relatórios para o Amazon S3 |

---

## SR1

### 1. Alinhamento com a ISO/IEC 38500

A ISO 38500 define seis princípios que a diretoria usa para orientar e supervisionar a TI. Abaixo, como cada um orienta a supervisão da qualidade do cadastro das unidades:

| Princípio | Como a diretoria aplica | Evidência no sistema |
|---|---|---|
| **Responsabilidade** | Cada papel tem responsabilidade definida: o Editor propõe, o Gestor decide, o Admin supervisiona | Papéis `EDITOR_TECNICO`, `GESTOR_INFO`, `ADMIN`, `LEITOR` (RBAC no backend) |
| **Estratégia** | A TI apoia a meta de ter 100% das unidades com cadastro correto e CNES válido | Indicador "% com CNES" por distrito (`vw_unidades_por_distrito`) |
| **Aquisição** | Integrações e serviços externos (CNES, Keycloak/LDAP, AWS S3) são escolhidos por critérios documentados de custo, segurança e aderência ao SUS | README, seções de autenticação e nuvem |
| **Desempenho** | A diretoria acompanha tempo de decisão, volume de pendências e taxa de aprovação | `vw_desempenho_gestores`, `sp_relatorio_periodo`, dashboard |
| **Conformidade** | O sistema cumpre a LGPD e as normas internas (justificativa obrigatória, separação de funções) | Criptografia AES-256-GCM, anonimização, trilha imutável |
| **Comportamento humano** | O sistema respeita quem usa: telas por papel, mensagens claras, nenhuma decisão automática sem um gestor humano | Front-end por papel; toda aprovação exige justificativa de um gestor |

O ciclo **Avaliar → Dirigir → Monitorar** da norma corresponde a: avaliar os indicadores do dashboard, dirigir por meio de metas por distrito e monitorar pela trilha de auditoria e pelos relatórios exportados.

### 2. Mapeamento de riscos (Probabilidade × Impacto)

Escala de 1 (baixo) a 5 (alto). Criticidade = P × I: **1–6 baixa**, **8–12 média**, **15–25 alta**.

| # | Risco | Categoria | P | I | Criticidade |
|---|---|---|:-:|:-:|:-:|
| R1 | **Vazamento de dados pessoais** (nome, e-mail de servidores, justificativas) por acesso indevido ao banco | Vazamento de dados | 3 | 5 | **15 – Alta** |
| R2 | **Interrupção do servidor da aplicação** (falha de máquina, disco cheio, atualização mal feita) | Interrupção de TI | 3 | 4 | **12 – Média** |
| R3 | **Perda do banco de dados** sem cópia recente | Interrupção de TI | 2 | 5 | **10 – Média** |
| R4 | **Perda da chave de criptografia** (`CRIPTO_CHAVE`), tornando as justificativas ilegíveis | Interrupção / Integridade | 2 | 5 | **10 – Média** |
| R5 | **Credenciais comprometidas** de um Gestor, com aprovação de mudanças falsas | Vazamento / Fraude | 2 | 5 | **10 – Média** |
| R6 | **Indisponibilidade do CNES** ou do provedor de identidade (Keycloak/LDAP) | Interrupção de TI (cadeia) | 3 | 3 | **9 – Média** |
| R7 | **Exposição de relatório no S3** por bucket mal configurado | Vazamento de dados (cadeia) | 2 | 4 | **8 – Média** |
| R8 | **Dados cadastrais incorretos** enviados por uma unidade e aprovados sem conferência | Integridade | 3 | 3 | **9 – Média** |
| R9 | **Adulteração da trilha de auditoria** para esconder uma ação | Integridade | 1 | 5 | **5 – Baixa** (controles fortes) |
| R10 | Uso do **modo de login simulado** (`AUTH_MODE=dev`) em produção | Vazamento | 1 | 5 | **5 – Baixa** |

```
Impacto →      1     2     3     4     5
P 5
r 4
o 3                      R6,R8  R2    R1
b 2                             R7    R3,R4,R5
. 1                                   R9,R10
```

**Classificação das unidades por criticidade** (base do Plano de Mitigação, item 10): uma unidade é de **alta criticidade** quando cumpre pelo menos dois destes critérios: está sem CNES, tem divergência com o CNES na conciliação, tem solicitação parada há mais de 30 dias ou teve três ou mais solicitações devolvidas ou rejeitadas nos últimos 6 meses. Todos esses dados já estão em `/cnes/conciliacao`, `vw_solicitacoes_detalhadas` e `sp_cancelar_paradas`.

### 3. Matriz RACI — processo de validação cadastral das unidades

**R** = executa · **A** = aprova (responde pelo resultado) · **C** = consultado · **I** = informado

| Atividade | Editor Técnico (unidade/distrito) | Gestor de Informação | Administrador | Diretoria / Coord. de APS | Leitor |
|---|:-:|:-:|:-:|:-:|:-:|
| Coletar e enviar os dados da unidade (solicitação) | **R** | I | | | |
| Consultar o CNES para pré-preencher | **R** | C | | | |
| Conferir evidências e dados atuais × propostos | C | **R/A** | | | |
| Aprovar, devolver ou rejeitar | I | **R/A** | | I | |
| Corrigir e reenviar solicitação devolvida | **R** | A | | | |
| Conciliar a base local com o CNES | | **R** | C | I | |
| Gerir usuários, distritos e acessos | | C | **R/A** | I | |
| Revisar a trilha de auditoria | | C | **R** | **A** | |
| Definir metas e prioridades de qualidade cadastral | C | C | I | **R/A** | |
| Consultar painéis e indicadores | | I | I | I | **R** |

**Regras que o sistema garante:** a separação de funções (quem abriu uma solicitação não pode decidi-la, mesmo tendo o papel de Gestor) e, em toda atividade, um único **A**.

### 4. Framework COBIT 2019

| Objetivo COBIT | Por que apoia a estratégia de qualidade cadastral | Como o sistema atende |
|---|---|---|
| **EDM03 – Assegurar a otimização de riscos** | A diretoria define o apetite a risco e acompanha a matriz do item 2 | Matriz de riscos; revisão trimestral (item 6) |
| **APO10 – Gerenciar fornecedores** | As unidades e os serviços externos (CNES, AWS, IdP) são "fornecedores" de dados e de infraestrutura | Conciliação CNES; responsabilidade compartilhada (item 9) |
| **APO12 – Gerenciar riscos** | Identificar, analisar e tratar os riscos cadastrais e de TI | Matriz P×I e Plano de Mitigação |
| **APO13 – Gerenciar segurança** | Proteger dados e acessos | RBAC, Keycloak/LDAP, AES-256-GCM |
| **APO14 – Gerenciar dados** | Qualidade e ciclo de vida do dado cadastral | Fluxo de aprovação; o cadastro oficial só muda com aprovação |
| **BAI06 – Gerenciar mudanças de TI** | Toda mudança no cadastro passa por solicitação, análise e decisão | Módulo `solicitacoes` |
| **DSS04 – Gerenciar continuidade** | Manter o serviço e recuperar dados | Backup (`python -m app.backup`), item 10 |
| **DSS05 – Gerenciar serviços de segurança** | Proteção contra acesso indevido e registro de eventos | Login auditado, trilha imutável |
| **MEA03 – Monitorar conformidade externa** | Conformidade com a LGPD e as normas do SUS | Item 5, plano de auditoria |

### 5. Conformidade regulatória (LGPD – Lei 13.709/2018)

**Que dados pessoais o sistema trata**

| Dado | Titular | Finalidade | Base legal (art. 7º) |
|---|---|---|---|
| Nome e e-mail do servidor | Servidores da Prefeitura | Identificar quem solicita e quem decide | Execução de políticas públicas (III) e cumprimento de obrigação legal (II) |
| Usuário e IP nas tentativas de login | Servidores | Segurança e prevenção de fraude | Legítimo interesse / segurança (IX); Marco Civil, art. 15 |
| Justificativas (texto livre) | Servidores | Fundamentar a decisão administrativa | Execução de políticas públicas (III) |
| Dados das unidades (nome, CNES, localização) | Pessoa jurídica | Cadastro oficial | Não é dado pessoal |

O sistema **não trata dados de pacientes** nem dados sensíveis (art. 5º, II).

**Avaliação do formulário de solicitação ("diagnóstico")**

| Princípio (art. 6º) | Situação | Evidência |
|---|---|---|
| Finalidade e adequação | ✅ | O formulário pede só dados da unidade; o solicitante vem do token |
| Necessidade (minimização) | ✅ | Não há CPF, telefone ou endereço pessoal; o papel vem do IdP e não é guardado como cadastro |
| Livre acesso | ✅ | `GET /auth/me` mostra ao titular os dados que o sistema guarda sobre ele |
| Segurança | ✅ | Justificativas e auditoria cifradas com AES-256-GCM; RBAC no backend; tokens com expiração |
| Prevenção | ✅ | Trilha de auditoria de toda operação, inclusive de logins |
| Transparência | ⚠️ | **Falta** um aviso de privacidade na tela de login (ação recomendada) |
| Responsabilização | ✅ | Trilha imutável identifica quem fez o quê e quando |

**Direitos do titular (art. 18):** a **eliminação/anonimização** está implementada em `POST /usuarios/{id}/anonimizacao` (botão "Anonimizar" na tela de Usuários). O comando apaga nome, e-mail e login do titular e mantém solicitações e decisões, que são registros administrativos de guarda obrigatória (art. 16, I). Os eventos de auditoria antigos continuam cifrados e acessíveis só ao Administrador, pela mesma base legal.

**Recomendações pendentes:** aviso de privacidade no login; indicar o Encarregado (DPO) da Prefeitura; definir prazo de retenção da auditoria (sugestão: 5 anos, alinhado ao prazo prescricional administrativo); registrar o tratamento no inventário de dados (ROPA) da Secretaria.

---

## SR2

### 6. Plano de Auditoria das Unidades (cronograma + checklist)

Objetivo: verificar se os dados enviados pelas unidades e aprovados no sistema são **verídicos**, ou seja, se batem com o CNES e com a realidade da unidade.

**Amostragem:** todas as unidades de **alta criticidade** (item 2) e mais 20% das demais, sorteadas a cada ciclo. Com 65 unidades, isso dá cerca de 15 a 20 unidades por ciclo.

**Cronograma (ciclo trimestral)**

| Semana | Atividade | Responsável | Fonte no sistema |
|---|---|---|---|
| 1 | Extrair indicadores e lista de unidades críticas | Gestor de Informação | Dashboard, `/cnes/conciliacao`, `vw_solicitacoes_detalhadas` |
| 1 | Sortear a amostra e comunicar os distritos | Administrador | — |
| 2–3 | Conferir documentos e evidências de cada unidade da amostra | Auditor (Gestor que **não** decidiu as solicitações) | `solicitacao.html` (comparativo + histórico) |
| 3 | Visita ou videochamada nas unidades de alta criticidade | Coordenação distrital | — |
| 4 | Revisar a trilha de auditoria e os logins recusados | Administrador | `/auditoria` (filtro Logins) |
| 4 | Relatório final e plano de ação | Gestor de Informação → Diretoria | `POST /relatorios/exportar` |

**Checklist por unidade**

- [ ] O código CNES existe, tem 7 dígitos e o nome bate com o CNES (conciliação sem divergência).
- [ ] O distrito sanitário cadastrado é o correto para o endereço/coordenadas.
- [ ] As quantidades de equipamentos e serviços conferem com a última visita ou com o CNES.
- [ ] Toda alteração aprovada nos últimos 3 meses tem justificativa coerente com os dados propostos.
- [ ] O aprovador de cada solicitação é diferente do solicitante (separação de funções).
- [ ] Não há solicitação parada há mais de 30 dias sem justificativa.
- [ ] O snapshot anterior (`decisoes.snapshot_anterior`) permite reconstruir o dado antes da mudança.
- [ ] A trilha de auditoria tem um evento para cada mudança de status (comparar com `historico_status`).
- [ ] Status "inativa" condiz com a situação real da unidade.

**Resultado:** cada item vira Conforme / Não conforme / Não se aplica. Uma unidade com 2 ou mais não conformidades vira "alta criticidade" no ciclo seguinte.

### 7. Trilha de Auditoria (Audit Trail)

Como o sistema garante a integridade das respostas enviadas pelas unidades:

1. **Todo evento é registrado na mesma transação da operação** (`app/modules/auditoria/service.py::registrar`). Se a operação falhar, o evento também não é gravado, e vice-versa. Não existe mudança sem registro.
2. **O que é registrado:** quem (`usuario_id`), o quê (`acao`: `SOLICITACAO_CRIADA`, `SOLICITACAO_APROVADA`, `DISTRITO_EXCLUIDO`, `USUARIO_ANONIMIZADO`, `LOGIN`, `LOGIN_FALHOU`…), em qual registro (`entidade`, `entidade_id`), quando (`ocorrido_em`, em UTC) e os detalhes (protocolo, justificativa, IP no login).
3. **Imutabilidade em duas camadas:** o ORM recusa `UPDATE`/`DELETE` em `auditoria_eventos` e, no banco, os triggers `trg_auditoria_sem_update` e `trg_auditoria_sem_delete` abortam a operação, mesmo para quem acessa o SQLite direto.
4. **Detecção de adulteração:** os detalhes são cifrados com AES-256-GCM, que autentica o conteúdo. Qualquer byte alterado direto no arquivo faz a leitura falhar (`InvalidTag`) em vez de mostrar um dado falso.
5. **Histórico paralelo por trigger:** `historico_status` é preenchido pelo próprio banco a cada mudança de status. Como ele não depende do código da aplicação, serve de conferência cruzada com a trilha.
6. **Versão anterior preservada:** na aprovação, o estado anterior da unidade fica em `decisoes.snapshot_anterior`.
7. **Logins:** no modo LDAP, cada tentativa (aceita ou recusada) gera `LOGIN` ou `LOGIN_FALHOU` com o usuário e o IP, **nunca a senha**. No modo Keycloak, os eventos de login ficam no próprio Keycloak (Events → Login events).
8. **Consulta:** só o Administrador vê a trilha (`GET /auditoria`, tela "Trilha de Auditoria"), com filtro por entidade.

Testes que comprovam: `tests/test_fluxo.py::test_auditoria_e_imutavel`, `tests/test_banco.py`, `tests/test_cripto.py`, `tests/test_seguranca.py`.

### 8. Dilemas éticos e responsabilidade social

**Descarte inadequado de hardware.** Os computadores das unidades e o servidor da aplicação guardam dados de servidores e, nas unidades, também de pacientes, gravados por outros sistemas. Descartar um disco sem apagá-lo expõe essas pessoas, e o lixo eletrônico contamina o solo com metais pesados. Posição da equipe:
- Apagar os discos de forma segura (sobrescrita ou destruição física, conforme a NIST SP 800-88) antes de doar ou descartar, com um termo de descarte assinado.
- Como as colunas sensíveis do nosso banco estão cifradas, destruir a chave (`CRIPTO_CHAVE`) torna ilegíveis os dados que restarem em cópias antigas (*crypto-shredding*).
- Destinar os equipamentos a cooperativas de reciclagem credenciadas (Política Nacional de Resíduos Sólidos, Lei 12.305/2010), dando preferência à doação para escolas quando o equipamento ainda funciona.

**Uso de IA para analisar automaticamente o scorecard.** Seria tentador usar IA para aprovar sozinha as solicitações ou para dar uma "nota" às unidades. Riscos éticos:
- **Viés:** unidades de periferia, com menos estrutura para documentar, podem ser penalizadas e perder prioridade de investimento, o que aumenta a desigualdade no acesso à saúde.
- **Opacidade:** um gestor não consegue explicar a um distrito por que a IA rejeitou um pedido, e a LGPD (art. 20) garante o direito de pedir revisão de decisões automatizadas.
- **Responsabilização:** quando a IA erra, não há quem responda.

**Posição adotada:** o sistema **não usa IA para decidir**. Toda decisão é de um Gestor humano, com justificativa obrigatória e registrada. Se no futuro houver IA, ela deve apenas **sugerir** (por exemplo, apontar divergências), com a regra exposta, revisão humana obrigatória e auditoria periódica de viés por distrito.

### 9. Governança em nuvem e terceirização (responsabilidade compartilhada)

O sistema usa a nuvem em dois pontos: a **exportação de relatórios para o Amazon S3** e, opcionalmente, a hospedagem do servidor LDAP/aplicação em uma instância EC2 (AWS Academy).

| Camada | Responsável: **AWS** | Responsável: **equipe / Prefeitura** |
|---|---|---|
| Data center físico, energia, rede, hardware | ✅ | |
| Hypervisor e serviço S3 | ✅ | |
| Sistema operacional da EC2 e atualizações | | ✅ |
| Configuração do bucket (bloqueio de acesso público, políticas) | | ✅ |
| Identidades e credenciais IAM | | ✅ |
| Dados (o que se envia e quem pode ler) | | ✅ |
| Criptografia em repouso no S3 | Oferece (SSE-S3/SSE-KMS) | Ativar e escolher a chave |
| Criptografia em trânsito | Oferece HTTPS | Usar só HTTPS (o `boto3` já usa) |
| Registro de acessos | Oferece CloudTrail | Ativar e revisar |

**Controles definidos para a nossa parte:**
1. **Credenciais fora do código:** o projeto não guarda chaves da AWS; o `boto3` lê as credenciais do ambiente, que são temporárias no Learner Lab. ✅ implementado
2. **Menor privilégio:** a identidade da aplicação só precisa de `s3:PutObject` e `s3:ListBucket` no prefixo `relatorios/`.
3. **Block Public Access** ligado no bucket; os relatórios nunca ficam públicos.
4. **Criptografia padrão do bucket** (SSE-S3) ligada no console da AWS.
5. **CloudTrail** ligado para registrar quem acessou o bucket.
6. **Auditoria local:** cada exportação gera `RELATORIO_EXPORTADO` na trilha. ✅ implementado
7. **Saída do fornecedor:** os relatórios são CSV comuns, então trocar de provedor não perde dados.

### 10. Plano de Mitigação e Continuidade (riscos de alta e média criticidade)

| Risco | Controle | Tipo | Situação |
|---|---|---|---|
| **R1 Vazamento de dados** (alta) | Criptografia AES-256-GCM das justificativas e da auditoria | Preventivo | ✅ implementado |
| | RBAC no backend; o front só esconde botões | Preventivo | ✅ implementado |
| | Chave própria obrigatória em produção (a app não sobe com a chave de desenvolvimento) | Preventivo | ✅ implementado |
| | Anonimização de usuários (LGPD) | Corretivo | ✅ implementado |
| | Revisão trimestral dos logins recusados na trilha | Detectivo | ✅ implementado (eventos `LOGIN_FALHOU`) |
| **R2 Interrupção do servidor** | Endpoint `/health` para monitoramento externo | Detectivo | ✅ implementado |
| | Reinício automático do serviço (systemd/Docker `restart: always`) | Corretivo | Recomendado |
| **R3 Perda do banco** | Backup diário: `python -m app.backup --destino /mnt/backup --manter 7` (cron às 2h) | Corretivo | ✅ script implementado |
| | Verificação de integridade da cópia (`PRAGMA integrity_check`) | Detectivo | ✅ implementado |
| | Teste de restauração mensal | Corretivo | Recomendado |
| **R4 Perda da chave** | Guardar `CRIPTO_CHAVE` em cofre (ex.: AWS Secrets Manager) com cópia offline lacrada | Preventivo | Recomendado |
| **R5 Credenciais comprometidas** | Login centralizado (Keycloak/LDAP) com política de senha e MFA no Keycloak | Preventivo | Parcial (MFA a configurar) |
| | Separação de funções: uma credencial sozinha não aprova o próprio pedido | Preventivo | ✅ implementado |
| **R6 CNES / IdP indisponível** | Formulário funciona sem o CNES (preenchimento manual); conciliação refeita depois | Contingência | ✅ implementado |
| **R7 Exposição no S3** | Controles do item 9 | Preventivo | Parcial |
| **R8 Dados incorretos** | Aprovação humana obrigatória + conciliação CNES + plano de auditoria | Preventivo/Detectivo | ✅ implementado |

**Controles específicos para unidades de alta criticidade** (critério no item 2; controles de processo propostos, ainda não automatizados no sistema):
1. Não aceitar alteração sem conferência com o CNES: o gestor anexa na justificativa o resultado da consulta.
2. Revisão em dupla: a decisão é conferida por um segundo gestor no ciclo de auditoria (item 6).
3. Auditoria a cada ciclo trimestral, sempre incluída na amostra.
4. Alerta no dashboard para solicitações dessas unidades paradas há mais de 15 dias, que podem ser encerradas com `sp_cancelar_paradas`.

**Objetivos de recuperação:** RPO (perda máxima de dados) de **24 horas**, pelo backup diário; RTO (tempo para voltar ao ar) de **4 horas**: restaurar o último backup e subir a aplicação.

**Como restaurar:**
```bash
# 1. parar a aplicação
# 2. copiar o backup mais recente sobre o banco
cp backups/governanca_AAAAMMDD_HHMMSS.db governanca.db
# 3. subir de novo com a MESMA CRIPTO_CHAVE (sem ela as justificativas ficam ilegíveis)
uvicorn app.main:app
```
