"""Bind e busca de grupos num servidor LDAP (ldap3, puro Python)."""
from dataclasses import dataclass

from ldap3 import ALL_ATTRIBUTES, SIMPLE, Connection, Server
from ldap3.core.exceptions import LDAPBindError
from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import escape_rdn

from app.core.config import settings


class CredenciaisInvalidas(Exception):
    """Usuário/senha incorretos. Erros de conectividade com o LDAP propagam como LDAPException."""


@dataclass(frozen=True)
class UsuarioLdap:
    username: str
    nome: str
    email: str
    grupos: list[str]


def autenticar(username: str, senha: str) -> UsuarioLdap:
    """Faz o bind do usuário contra o LDAP e lê seus dados e grupos.

    Levanta CredenciaisInvalidas se o bind falhar (mensagem genérica de propósito,
    para não revelar se o usuário existe). Erros de conectividade propagam como
    ldap3.core.exceptions.LDAPException.
    """
    user_dn = settings.ldap_user_dn_template.format(
        username=escape_rdn(username), base_dn=settings.ldap_base_dn
    )
    server = Server(settings.ldap_url)
    try:
        with Connection(server, user=user_dn, password=senha, authentication=SIMPLE, auto_bind=True) as conn:
            conn.search(user_dn, "(objectClass=*)", attributes=ALL_ATTRIBUTES)
            atributos = conn.entries[0] if conn.entries else None
            nome = str(atributos.cn.value) if atributos and "cn" in atributos else username
            email = str(atributos.mail.value) if atributos and "mail" in atributos else ""

            filtro_username = escape_filter_chars(username)
            grupos_base = settings.ldap_group_search_base.format(base_dn=settings.ldap_base_dn)
            conn.search(
                grupos_base,
                f"(&(objectClass=posixGroup)(memberUid={filtro_username}))",
                attributes=["cn"],
            )
            grupos = [str(g.cn.value) for g in conn.entries]
    except LDAPBindError:
        raise CredenciaisInvalidas("Usuário ou senha inválidos")

    return UsuarioLdap(username=username, nome=nome, email=email, grupos=grupos)
