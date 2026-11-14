-- Views (SQLite). Recriadas a cada inicialização da aplicação.
-- Datas são gravadas em UTC; 'localtime' converte para o fuso do servidor antes de agrupar ou filtrar.
-- fn_percentual, fn_dias_entre e fn_protocolo são funções registradas na conexão (ver funcoes.py).

-- 1. Situação do cadastro por distrito
DROP VIEW IF EXISTS vw_unidades_por_distrito;
CREATE VIEW vw_unidades_por_distrito AS
SELECT d.id                                                              AS distrito_id,
       d.nome                                                            AS distrito,
       COUNT(u.id)                                                       AS total_unidades,
       SUM(CASE WHEN u.status = 'ATIVO' THEN 1 ELSE 0 END)               AS ativas,
       SUM(CASE WHEN u.status = 'INATIVO' THEN 1 ELSE 0 END)             AS inativas,
       SUM(CASE WHEN u.status = 'ATIVO' AND u.codigo_cnes IS NULL THEN 1 ELSE 0 END) AS sem_cnes,
       fn_percentual(SUM(CASE WHEN u.codigo_cnes IS NOT NULL THEN 1 ELSE 0 END), COUNT(u.id)) AS pct_com_cnes,
       COALESCE(SUM(u.qtd_equipamentos), 0)                              AS equipamentos,
       COALESCE(SUM(u.qtd_servicos), 0)                                  AS servicos
FROM distritos d
LEFT JOIN unidades u ON u.distrito_id = d.id
GROUP BY d.id, d.nome;

-- 2. Solicitações com solicitante, unidade, distrito, última decisão e tempo até a decisão
DROP VIEW IF EXISTS vw_solicitacoes_detalhadas;
CREATE VIEW vw_solicitacoes_detalhadas AS
SELECT s.id                                                   AS solicitacao_id,
       fn_protocolo(s.id, s.criada_em)                        AS protocolo,
       s.tipo,
       s.status,
       us.nome                                                AS solicitante,
       COALESCE(un.nome, json_extract(s.dados_propostos, '$.nome')) AS unidade,
       d.id                                                   AS distrito_id,
       d.nome                                                 AS distrito,
       s.criada_em,
       dc.decidida_em,
       ug.nome                                                AS gestor,
       fn_dias_entre(s.criada_em, dc.decidida_em)             AS dias_ate_decisao
FROM solicitacoes s
JOIN usuarios us       ON us.id = s.solicitante_id
LEFT JOIN unidades un  ON un.id = s.unidade_id
LEFT JOIN distritos d  ON d.id = COALESCE(un.distrito_id, json_extract(s.dados_propostos, '$.distrito_id'))
LEFT JOIN decisoes dc  ON dc.id = (SELECT MAX(x.id) FROM decisoes x WHERE x.solicitacao_id = s.id)
LEFT JOIN usuarios ug  ON ug.id = dc.gestor_id;

-- 3. Produtividade de cada gestor
DROP VIEW IF EXISTS vw_desempenho_gestores;
CREATE VIEW vw_desempenho_gestores AS
SELECT u.id                                                         AS gestor_id,
       u.nome                                                       AS gestor,
       COUNT(*)                                                     AS decisoes,
       SUM(CASE WHEN dc.resultado = 'APROVADA'  THEN 1 ELSE 0 END)  AS aprovadas,
       SUM(CASE WHEN dc.resultado = 'DEVOLVIDA' THEN 1 ELSE 0 END)  AS devolvidas,
       SUM(CASE WHEN dc.resultado = 'REJEITADA' THEN 1 ELSE 0 END)  AS rejeitadas,
       fn_percentual(SUM(CASE WHEN dc.resultado = 'APROVADA' THEN 1 ELSE 0 END), COUNT(*)) AS taxa_aprovacao,
       ROUND(AVG(fn_dias_entre(s.criada_em, dc.decidida_em)), 1)    AS media_dias
FROM decisoes dc
JOIN usuarios u      ON u.id = dc.gestor_id
JOIN solicitacoes s  ON s.id = dc.solicitacao_id
GROUP BY u.id, u.nome;

-- 4. Evolução mensal das solicitações por situação atual
DROP VIEW IF EXISTS vw_evolucao_mensal;
CREATE VIEW vw_evolucao_mensal AS
SELECT strftime('%Y-%m', criada_em, 'localtime')                                  AS mes,
       COUNT(*)                                                      AS criadas,
       SUM(CASE WHEN status = 'APROVADA'  THEN 1 ELSE 0 END)         AS aprovadas,
       SUM(CASE WHEN status = 'REJEITADA' THEN 1 ELSE 0 END)         AS rejeitadas,
       SUM(CASE WHEN status IN ('PENDENTE', 'DEVOLVIDA') THEN 1 ELSE 0 END) AS em_aberto,
       SUM(CASE WHEN status = 'CANCELADA' THEN 1 ELSE 0 END)         AS canceladas
FROM solicitacoes
GROUP BY strftime('%Y-%m', criada_em, 'localtime');
