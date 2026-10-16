"""Cliente do CNES. Hoje devolve dados simulados; troque a implementação de `buscar` pela
chamada real à API do CNES quando o acesso estiver disponível (o resto do módulo não muda)."""

_DADOS_SIMULADOS = {
    "2077604": {"nome": "UBS Vila Madalena", "tipo": "UBS"},
    "9848271": {"nome": "AMA Perdizes II", "tipo": "AMA"},
    "3456781": {"nome": "CEU AS Butantã", "tipo": "CEU AS"},
    "4567892": {"nome": "UBS Parelheiros I", "tipo": "UBS"},
}


class CnesClient:
    def buscar(self, codigo: str) -> dict | None:
        return _DADOS_SIMULADOS.get(codigo)


def get_cnes_client() -> CnesClient:
    return CnesClient()
