"""Carga de dados de exemplo.

    python -m app.seed            # popula um banco vazio (não mexe em dados existentes)
    python -m app.seed --recriar  # APAGA todas as tabelas e popula de novo

Gera distritos e unidades de Recife, usuários de todos os papéis e cerca de 250 solicitações
nos últimos 18 meses, com todos os tipos e fluxos (decisão direta, devolução e reenvio,
cancelamento e pendentes), decisões, histórico de status (pelos triggers) e auditoria.
Usa uma semente fixa: os dados são sempre os mesmos.
"""
import random
import sys
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select

import app.models  # noqa: F401
from app.core.database import Base, SessionLocal, agora, engine
from app.modules.auditoria.models import AuditoriaEvento
from app.modules.auth.models import Usuario
from app.modules.banco.service import instalar
from app.modules.distritos.models import Distrito
from app.modules.solicitacoes.models import (
    Decisao,
    ResultadoDecisao,
    Solicitacao,
    StatusSolicitacao,
    TipoSolicitacao,
)
from app.modules.solicitacoes.service import _aplicar
from app.modules.unidades.models import StatusUnidade, Unidade

# Distrito -> bairros (uma unidade por bairro; o tipo vem de TIPOS em rodízio)
BAIRROS = {
    "Distrito Sanitário I": ["Boa Vista", "Santo Amaro", "Coelhos", "Soledade", "São José"],
    "Distrito Sanitário II": ["Encruzilhada", "Água Fria", "Beberibe", "Campo Grande", "Arruda", "Campina do Barreto"],
    "Distrito Sanitário III": ["Casa Amarela", "Casa Forte", "Parnamirim", "Vasco da Gama", "Nova Descoberta"],
    "Distrito Sanitário IV": ["Várzea", "Torre", "Madalena", "Iputinga", "Cordeiro", "Engenho do Meio"],
    "Distrito Sanitário V": ["Afogados", "Mustardinha", "San Martin", "Bongi", "Totó"],
    "Distrito Sanitário VI": ["Boa Viagem", "Imbiribeira", "Pina", "Ipsep", "Brasília Teimosa"],
    "Distrito Sanitário VII": ["Macaxeira", "Alto José do Pinho", "Córrego do Jenipapo", "Brejo da Guabiraba"],
    "Distrito Sanitário VIII": ["Cohab", "Ibura", "Jordão", "UR-10", "Lagoa Encantada"],
}
TIPOS = ["UBS", "UBS", "UBS", "AMA/UBS", "CMS", "AMA", "CRS", "CEU AS"]

# (nome, e-mail, papel sugerido para o login simulado)
USUARIOS = [
    ("Carla Menezes", "carla.menezes@recife.pe.gov.br", "EDITOR_TECNICO"),
    ("Bruno Albuquerque", "bruno.albuquerque@recife.pe.gov.br", "EDITOR_TECNICO"),
    ("Juliana Farias", "juliana.farias@recife.pe.gov.br", "EDITOR_TECNICO"),
    ("Helena Cavalcanti", "helena.cavalcanti@recife.pe.gov.br", "GESTOR_INFO"),
    ("Marcos Vasconcelos", "marcos.vasconcelos@recife.pe.gov.br", "GESTOR_INFO"),
    ("Patrícia Lins", "patricia.lins@recife.pe.gov.br", "GESTOR_INFO"),
    ("Rafael Siqueira", "rafael.siqueira@recife.pe.gov.br", "ADMIN"),
    ("Luana Barros", "luana.barros@recife.pe.gov.br", "LEITOR"),
]

JUST_EDITOR = {
    TipoSolicitacao.INCLUSAO: ["Nova unidade inaugurada pela prefeitura", "Unidade aberta para cobrir área descoberta",
                               "Expansão da cobertura da ESF no bairro"],
    TipoSolicitacao.ALTERACAO: ["Atualização após visita técnica", "Correção de dados conforme o CNES",
                                "Novos equipamentos recebidos", "Ampliação dos serviços oferecidos",
                                "Ajuste solicitado pela coordenação do distrito"],
    TipoSolicitacao.INATIVACAO: ["Unidade fechada para reforma", "Unidade incorporada a outra unidade",
                                 "Imóvel devolvido ao proprietário"],
    TipoSolicitacao.REATIVACAO: ["Reforma concluída", "Unidade reaberta após mudança de endereço"],
}
JUST_GESTOR = {
    ResultadoDecisao.APROVADA: ["Dados conferidos", "Conferido com o CNES", "De acordo com a coordenação"],
    ResultadoDecisao.REJEITADA: ["Dados não conferem com o CNES", "Solicitação duplicada", "Sem documentação comprobatória"],
    ResultadoDecisao.DEVOLVIDA: ["Falta o código CNES", "Corrigir a quantidade de equipamentos", "Anexar justificativa detalhada"],
}

DIAS_HISTORICO = 540
TOTAL_SOLICITACOES = 250


class Gerador:
    def __init__(self, db):
        self.db = db
        self.rnd = random.Random(2026)
        self.hoje = agora()
        self.cnes_usados: set[str] = set()

    # ---------- utilitários ----------

    def cnes(self) -> str:
        while True:
            codigo = str(self.rnd.randint(2_000_000, 9_999_999))
            if codigo not in self.cnes_usados:
                self.cnes_usados.add(codigo)
                return codigo

    def coordenada(self) -> tuple[float, float]:
        return round(self.rnd.uniform(-8.15, -7.98), 6), round(self.rnd.uniform(-34.96, -34.87), 6)

    def auditar(self, usuario, acao, s, quando, **detalhes):
        self.db.add(AuditoriaEvento(usuario_id=usuario.id, acao=acao, entidade="solicitacao", entidade_id=s.id,
                                    detalhes={"protocolo": s.protocolo, **detalhes}, ocorrido_em=quando))

    def depois(self, inicio, min_dias, max_dias):
        return min(inicio + timedelta(days=self.rnd.uniform(min_dias, max_dias)), self.hoje)

    # ---------- cadastro base ----------

    def cadastro(self) -> None:
        criado_em = self.hoje - timedelta(days=DIAS_HISTORICO + 30)
        for i_d, (nome_d, bairros) in enumerate(BAIRROS.items()):
            distrito = Distrito(nome=nome_d)
            self.db.add(distrito)
            self.db.flush()
            for i_b, bairro in enumerate(bairros):
                tipo = TIPOS[(i_d + i_b) % len(TIPOS)]
                lat, lon = self.coordenada()
                self.db.add(Unidade(
                    nome=f"{tipo} {bairro}", tipo=tipo, distrito_id=distrito.id,
                    codigo_cnes=None if self.rnd.random() < 0.25 else self.cnes(),  # ~25% sem CNES
                    status=StatusUnidade.INATIVO if self.rnd.random() < 0.08 else StatusUnidade.ATIVO,
                    latitude=lat, longitude=lon,
                    qtd_equipamentos=self.rnd.randint(3, 18), qtd_servicos=self.rnd.randint(2, 12),
                    atualizada_em=criado_em,
                ))
        self.db.add_all(Usuario(keycloak_id=f"dev:{e}", nome=n, email=e) for n, e, _ in USUARIOS)
        self.db.flush()

    # ---------- solicitações ----------

    def proposta(self, tipo, unidade):
        """Dados propostos e atuais de cada tipo."""
        if tipo == TipoSolicitacao.INCLUSAO:
            bairro = self.rnd.choice(["Areias", "Caçote", "Estância", "Jiquiá", "Sancho", "Tejipió", "Barro", "Curado",
                                      "Dois Irmãos", "Sítio dos Pintos", "Guabiraba", "Passarinho", "Mangueira"])
            lat, lon = self.coordenada()
            distrito = self.rnd.choice(self.distritos)
            propostos = {"nome": f"UBS {bairro} {self.rnd.randint(1, 3)}", "tipo": "UBS", "distrito_id": distrito.id,
                         "latitude": lat, "longitude": lon, "qtd_equipamentos": self.rnd.randint(3, 10),
                         "qtd_servicos": self.rnd.randint(2, 8)}
            if self.rnd.random() < 0.7:
                propostos["codigo_cnes"] = self.cnes()
            return propostos, None
        if tipo != TipoSolicitacao.ALTERACAO:  # inativação e reativação: só o status muda
            return None, {"status": unidade.status.value}
        propostos = {}
        if unidade.codigo_cnes is None and self.rnd.random() < 0.25:
            propostos["codigo_cnes"] = self.cnes()
        for campo in self.rnd.sample(["qtd_equipamentos", "qtd_servicos", "tipo"], k=self.rnd.randint(1, 2)):
            if campo == "tipo":
                propostos["tipo"] = self.rnd.choice(sorted(t for t in set(TIPOS) if t != unidade.tipo))
            else:
                propostos[campo] = max(0, getattr(unidade, campo) + self.rnd.choice([-2, -1, 1, 2, 3]))
        return propostos, {c: getattr(unidade, c) for c in propostos}

    def decidir(self, s, resultado, quando):
        gestor = self.rnd.choice(self.gestores)
        snap = None
        if resultado == ResultadoDecisao.APROVADA:
            try:
                snap = _aplicar(self.db, s)  # a mesma regra da aprovação real, com as mesmas validações
            except HTTPException:  # o cadastro mudou desde o pedido (ex.: unidade já inativada)
                resultado = ResultadoDecisao.REJEITADA
            else:
                unidade = self.db.get(Unidade, s.unidade_id)
                unidade.atualizada_em = quando
                if s.tipo == TipoSolicitacao.INCLUSAO:
                    self.unidades.append(unidade)
        justificativa = self.rnd.choice(JUST_GESTOR[resultado])
        self.db.add(Decisao(solicitacao_id=s.id, gestor_id=gestor.id, resultado=resultado,
                            justificativa=justificativa, snapshot_anterior=snap, decidida_em=quando))
        s.status, s.atualizada_em = StatusSolicitacao(resultado.value), quando
        self.db.flush()  # trigger: histórico da mudança de status
        self.auditar(gestor, f"SOLICITACAO_{resultado.value}", s, quando, justificativa=justificativa)

    def escolher_tipo(self):
        ativas = [u for u in self.unidades if u.status == StatusUnidade.ATIVO]
        inativas = [u for u in self.unidades if u.status == StatusUnidade.INATIVO]
        # pesos na ordem do enum: INCLUSAO, ALTERACAO, INATIVACAO, REATIVACAO
        tipo = self.rnd.choices(list(TipoSolicitacao), weights=[18, 60, 14, 5])[0]
        if tipo == TipoSolicitacao.REATIVACAO and not inativas:
            tipo = TipoSolicitacao.ALTERACAO
        if tipo == TipoSolicitacao.INCLUSAO:
            return tipo, None
        return tipo, self.rnd.choice(inativas if tipo == TipoSolicitacao.REATIVACAO else ativas)

    def solicitacoes(self) -> None:
        # datas com tendência de alta: mais pedidos nos meses recentes
        idades = sorted((DIAS_HISTORICO * (1 - self.rnd.random() ** 0.75) for _ in range(TOTAL_SOLICITACOES)),
                        reverse=True)
        for idade in idades:
            criada = self.hoje - timedelta(days=idade, minutes=self.rnd.randint(0, 600))
            tipo, unidade = self.escolher_tipo()
            propostos, atuais = self.proposta(tipo, unidade)
            editor = self.rnd.choice(self.editores)
            s = Solicitacao(tipo=tipo, unidade_id=unidade.id if unidade else None, solicitante_id=editor.id,
                            dados_propostos=propostos, dados_atuais=atuais,
                            justificativa=self.rnd.choice(JUST_EDITOR[tipo]), criada_em=criada, atualizada_em=criada)
            self.db.add(s)
            self.db.flush()  # trigger: histórico PENDENTE
            self.auditar(editor, "SOLICITACAO_CRIADA", s, criada, tipo=tipo.value, justificativa=s.justificativa)
            self.fluxo(s, editor, criada, recente=idade < 45)

    def fluxo(self, s, editor, criada, recente):
        sorteio = self.rnd.random()
        if recente and sorteio < 0.7:
            return  # continua PENDENTE
        if sorteio < 0.07:  # cancelada pelo solicitante
            quando = self.depois(criada, 0.5, 6)
            s.status, s.atualizada_em = StatusSolicitacao.CANCELADA, quando
            self.db.flush()
            self.auditar(editor, "SOLICITACAO_CANCELADA", s, quando, justificativa="Pedido aberto por engano")
            return

        quando = self.depois(criada, 0.2, 7)
        if sorteio < 0.25:  # devolvida para correção
            self.decidir(s, ResultadoDecisao.DEVOLVIDA, quando)
            if recente or self.rnd.random() < 0.15:
                return  # aguardando o editor
            quando = self.depois(quando, 0.5, 5)
            s.status, s.atualizada_em = StatusSolicitacao.PENDENTE, quando
            self.db.flush()
            self.auditar(editor, "SOLICITACAO_REENVIADA", s, quando)
            quando = self.depois(quando, 0.2, 4)

        aprova = {TipoSolicitacao.INCLUSAO: 0.55, TipoSolicitacao.ALTERACAO: 0.75,
                  TipoSolicitacao.REATIVACAO: 0.5}.get(s.tipo, 0.85)
        self.decidir(s, ResultadoDecisao.APROVADA if self.rnd.random() < aprova else ResultadoDecisao.REJEITADA, quando)

    def executar(self) -> None:
        self.cadastro()
        self.distritos = self.db.scalars(select(Distrito)).all()
        self.unidades = list(self.db.scalars(select(Unidade)))
        self.cnes_usados |= {u.codigo_cnes for u in self.unidades if u.codigo_cnes}
        usuarios = {u.email: u for u in self.db.scalars(select(Usuario))}
        self.editores = [usuarios[e] for _, e, p in USUARIOS if p == "EDITOR_TECNICO"]
        self.gestores = [usuarios[e] for _, e, p in USUARIOS if p == "GESTOR_INFO"]
        self.solicitacoes()
        self.db.commit()


def main(recriar: bool = False) -> None:
    if recriar:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    instalar(engine)
    with SessionLocal() as db:
        if db.query(Distrito).first():
            print("O banco já tem dados; nada foi feito. Use --recriar para apagar tudo e popular de novo.")
            return
        Gerador(db).executar()
        totais = {m.__tablename__: db.query(m).count() for m in (Distrito, Unidade, Usuario, Solicitacao, Decisao, AuditoriaEvento)}
        print("Criados: " + ", ".join(f"{n} {t}" for t, n in totais.items()))
        print("Login simulado: use um destes e-mails com o papel indicado:")
        for _, email, papel in USUARIOS:
            print(f"  {papel:<15} {email}")


if __name__ == "__main__":
    main(recriar="--recriar" in sys.argv)
