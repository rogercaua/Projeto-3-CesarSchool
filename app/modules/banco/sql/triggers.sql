-- Triggers (SQLite). Recriados a cada inicialização da aplicação.

-- 1 e 2. Histórico de status: toda solicitação criada ou com status alterado gera uma linha
DROP TRIGGER IF EXISTS trg_solicitacao_status_inicial;
CREATE TRIGGER trg_solicitacao_status_inicial
AFTER INSERT ON solicitacoes
BEGIN
    INSERT INTO historico_status (solicitacao_id, status_anterior, status_novo, mudou_em)
    VALUES (NEW.id, NULL, NEW.status, NEW.atualizada_em);
END;

DROP TRIGGER IF EXISTS trg_solicitacao_status_mudou;
CREATE TRIGGER trg_solicitacao_status_mudou
AFTER UPDATE OF status ON solicitacoes
WHEN OLD.status <> NEW.status
BEGIN
    INSERT INTO historico_status (solicitacao_id, status_anterior, status_novo, mudou_em)
    VALUES (NEW.id, OLD.status, NEW.status, NEW.atualizada_em);
END;

-- 3. Distrito com unidades vinculadas não pode ser excluído (reforça a regra da API)
DROP TRIGGER IF EXISTS trg_distrito_bloqueia_exclusao;
CREATE TRIGGER trg_distrito_bloqueia_exclusao
BEFORE DELETE ON distritos
WHEN EXISTS (SELECT 1 FROM unidades WHERE distrito_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'Distrito possui unidades vinculadas');
END;

-- 4 e 5. Trilha de auditoria imutável também no banco, não só no ORM
DROP TRIGGER IF EXISTS trg_auditoria_sem_update;
CREATE TRIGGER trg_auditoria_sem_update
BEFORE UPDATE ON auditoria_eventos
BEGIN
    SELECT RAISE(ABORT, 'Eventos de auditoria são imutáveis');
END;

DROP TRIGGER IF EXISTS trg_auditoria_sem_delete;
CREATE TRIGGER trg_auditoria_sem_delete
BEFORE DELETE ON auditoria_eventos
BEGIN
    SELECT RAISE(ABORT, 'Eventos de auditoria são imutáveis');
END;

-- 6 e 7. Código CNES, quando informado, precisa ter exatamente 7 dígitos
DROP TRIGGER IF EXISTS trg_unidade_cnes_insert;
CREATE TRIGGER trg_unidade_cnes_insert
BEFORE INSERT ON unidades
WHEN NEW.codigo_cnes IS NOT NULL AND (length(NEW.codigo_cnes) <> 7 OR NEW.codigo_cnes GLOB '*[^0-9]*')
BEGIN
    SELECT RAISE(ABORT, 'Código CNES deve ter 7 dígitos');
END;

DROP TRIGGER IF EXISTS trg_unidade_cnes_update;
CREATE TRIGGER trg_unidade_cnes_update
BEFORE UPDATE OF codigo_cnes ON unidades
WHEN NEW.codigo_cnes IS NOT NULL AND (length(NEW.codigo_cnes) <> 7 OR NEW.codigo_cnes GLOB '*[^0-9]*')
BEGIN
    SELECT RAISE(ABORT, 'Código CNES deve ter 7 dígitos');
END;
