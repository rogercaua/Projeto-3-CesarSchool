"""Criptografia simétrica (AES-256-GCM) de colunas sensíveis no banco.

O valor é serializado em JSON, cifrado com um nonce aleatório de 12 bytes e salvo como
"enc:v1:" + base64(nonce + texto cifrado + tag). O GCM também autentica: um valor
adulterado no banco gera erro na leitura em vez de devolver lixo.
"""
import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

_PREFIXO = "enc:v1:"
_aes = AESGCM(base64.b64decode(settings.cripto_chave))  # exige 32 bytes (AES-256)


def cifrar(valor) -> str:
    nonce = os.urandom(12)
    dados = _aes.encrypt(nonce, json.dumps(valor, ensure_ascii=False).encode(), None)
    return _PREFIXO + base64.b64encode(nonce + dados).decode()


def decifrar(texto: str):
    if not texto.startswith(_PREFIXO):
        # linha gravada antes da criptografia: objeto JSON puro (detalhes) ou texto puro
        try:
            return json.loads(texto) if texto[:1] in "{[" else texto
        except ValueError:  # ex.: justificativa "[URGENTE] ..."
            return texto
    bruto = base64.b64decode(texto[len(_PREFIXO):])
    return json.loads(_aes.decrypt(bruto[:12], bruto[12:], None))


class Cifrado(TypeDecorator):
    """Coluna que guarda qualquer valor serializável em JSON cifrado com AES-GCM."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, valor, dialect):
        return None if valor is None else cifrar(valor)

    def process_result_value(self, valor, dialect):
        return None if valor is None else decifrar(valor)
