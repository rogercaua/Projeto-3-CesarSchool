"""Carga inicial de exemplo: python -m app.seed"""
import app.models  # noqa: F401
from app.core.database import Base, SessionLocal, engine
from app.modules.distritos.models import Distrito
from app.modules.unidades.models import Unidade

DISTRITOS = [f"Distrito Sanitário {n}" for n in ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")]

# nome, tipo, código CNES, índice do distrito, equipamentos, serviços (espelha o protótipo)
UNIDADES = [
    ("UBS Vila Madalena", "UBS", "2077604", 0, 14, 8),
    ("AMA Perdizes", "AMA", "9848271", 0, 9, 5),
    ("UBS Saúde Consolação", "UBS", None, 1, 11, 7),
    ("CEU AS Butantã", "CEU AS", "3456781", 2, 8, 6),
    ("CRS Ipiranga", "CRS", None, 3, 10, 9),
    ("UBS Parelheiros I", "UBS", "4567892", 4, 7, 4),
]


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(Distrito).first():
            print("Banco já possui dados; nada a fazer.")
            return
        distritos = [Distrito(nome=n) for n in DISTRITOS]
        db.add_all(distritos)
        db.flush()
        db.add_all(
            Unidade(nome=n, tipo=t, codigo_cnes=c, distrito_id=distritos[d].id, qtd_equipamentos=e, qtd_servicos=s)
            for n, t, c, d, e, s in UNIDADES
        )
        db.commit()
        print(f"Criados {len(distritos)} distritos e {len(UNIDADES)} unidades.")


if __name__ == "__main__":
    main()
