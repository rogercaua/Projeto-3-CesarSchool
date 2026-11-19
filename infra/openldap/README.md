# OpenLDAP no AWS Academy Learner Lab

Setup mínimo de OpenLDAP (modo teste, sem TLS confiável) para servir de fonte
de credenciais/grupos via protocolo LDAP para este projeto, pensado para
rodar numa instância EC2 do Learner Lab — mesmo padrão usado em
`infra/keycloak`.

> Por que EC2 + Docker e não "AWS Directory Service"? O Directory Service
> (Simple AD / AWS Managed Microsoft AD) normalmente não está disponível na
> IAM role restrita do Learner Lab, e o Managed AD tem custo por hora alto
> demais para o crédito do lab. Um container OpenLDAP dá o mesmo protocolo
> LDAP para o cliente Python, de graça, com total controle.

## 1. Subir o lab e a instância EC2

Pode ser a **mesma instância** que já roda o Keycloak (economiza o Learner
Lab) ou uma nova — os passos abaixo assumem uma instância já up conforme
`infra/keycloak/README.md`.

1. **Modules → AWS Academy Learner Lab → Start Lab**, espere o círculo ficar
   verde, clique em **AWS** para abrir o Console.
2. Se for usar uma instância nova: **EC2 → Launch Instance**, AMI
   **Amazon Linux 2023** (nessa conta restrita do Learner Lab, a aba
   "Ubuntu" só oferecia uma AMI com SQL Server pré-instalado — evite essa,
   gera custo de licença extra; a aba "Amazon Linux" tem a opção simples e
   gratuita). Tipo `t3.micro`/`t3.small`. Crie/baixe o key pair `.pem`.
3. **Security Group** da instância: adicione regras de entrada para:
   - `22` (SSH) — origem **"Meu IP"**.
   - `389` (LDAP) — origem **"Meu IP"**, nunca `0.0.0.0/0` (LDAP sem TLS
     trafega a senha em claro).
   - `8081` (phpLDAPadmin, interface web de administração) — mesma origem.
4. (Opcional, recomendado) Associe um **Elastic IP** para o IP não mudar se
   a instância reiniciar durante a sessão do lab.

No Windows, ajuste a permissão da chave antes do primeiro SSH:

```powershell
icacls "sua-chave.pem" /inheritance:r
icacls "sua-chave.pem" /grant:r "$($env:USERNAME):(R)"
```

## 2. Copiar estes arquivos para a instância

Do seu computador (usuário SSH do Amazon Linux é `ec2-user`, não `ubuntu`):

```bash
scp -i sua-chave.pem -r infra/openldap ec2-user@<ip-da-instancia>:~/openldap
```

A pasta chega com permissão restritiva (herdada do Windows) — libere a
leitura para os containers conseguirem ler o seed:

```bash
ssh -i sua-chave.pem ec2-user@<ip-da-instancia> "chmod -R a+rX ~/openldap"
```

## 3. Instalar Docker e subir o OpenLDAP

Via SSH na instância (Amazon Linux usa `dnf`, não `apt`, e não vem com o
plugin do Docker Compose — instala-se o binário manualmente):

```bash
ssh -i sua-chave.pem ec2-user@<ip-da-instancia>

sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
# reconecte o SSH depois do usermod, pra sessão pegar o novo grupo

mkdir -p ~/.docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose

cd ~/openldap
cp .env.example .env
nano .env   # troque as senhas de admin

docker compose up -d
docker compose logs -f openldap   # espere a linha "slapd starting"
```

> **Imagem usada:** `bitnamilegacy/openldap` (não `osixia/openldap`, que
> tem um bug conhecido nessa versão — falha com erros de `sed: can't read
> .../replication-disable.ldif` por faltar arquivos internos da imagem,
> mesmo com pull limpo). O Bitnami original (`bitnami/openldap`) não tem
> mais tags públicas no Docker Hub desde a mudança de licenciamento da
> Broadcom em 2025; `bitnamilegacy/*` é o snapshot congelado (mas
> funcional) que ficou disponível gratuitamente.

O seed em `seed/10-seed.ldif` só é aplicado **na primeira subida** (volume
`ldap_data` vazio). Se precisar recarregar do zero:

```bash
docker compose down -v   # apaga os dados e força reaplicar o seed
docker compose up -d
```

## 4. Conferir que o diretório subiu com os dados certos

Da própria instância (ou do seu computador, se a porta 389 estiver liberada
para o seu IP):

```bash
ldapsearch -x -H ldap://<ip-da-instancia> \
  -b "dc=governanca,dc=local" \
  -D "cn=admin,dc=governanca,dc=local" -w '<LDAP_ADMIN_PASSWORD do .env>' \
  "(objectClass=posixGroup)" cn memberUid
```

Deve listar os 4 grupos (`ADMIN`, `GESTOR_INFO`, `EDITOR_TECNICO`, `LEITOR`)
com seus respectivos `memberUid`. Para ver pela interface web, acesse
`http://<ip-da-instancia>:8081` e faça login com
`cn=admin,dc=governanca,dc=local` / a senha do `.env`.

Teste o bind de um usuário de teste (senha de todos: `Senha123!`):

```bash
ldapwhoami -x -H ldap://<ip-da-instancia> \
  -D "uid=editor.teste,ou=people,dc=governanca,dc=local" -w 'Senha123!'
```

## 5. Estrutura criada pelo seed

| DN | Papel equivalente no projeto |
|---|---|
| `uid=admin.teste,ou=people,...` | `ADMIN` |
| `uid=gestor.teste,ou=people,...` | `GESTOR_INFO` |
| `uid=editor.teste,ou=people,...` | `EDITOR_TECNICO` |
| `uid=leitor.teste,ou=people,...` | `LEITOR` |

Os grupos em `ou=groups` usam o mesmo nome do enum `Papel`
(`app/modules/auth/schemas.py`) de propósito: o módulo de consumo LDAP do
backend (próximo passo, ainda não implementado) vai ler `memberUid` desses
grupos e mapear 1:1 para `Papel`, exatamente como hoje o Keycloak manda os
papéis em `realm_access.roles`.

## 6. Próximo passo (fora deste arquivo)

Este README cobre só a **infraestrutura** do servidor LDAP. Falta ainda,
no código do backend:

- Um `AUTH_MODE=ldap` (ou um endpoint `/auth/ldap-login`) que faça o bind
  do usuário contra este servidor e leia seus grupos.
- Tabelas locais `Grupo` / `UsuarioGrupo` para persistir o que vier do LDAP
  (e também do Keycloak, que hoje não grava grupo nenhum — só o token).

Me avise quando quiser seguir para essa parte.

## Limitações do Learner Lab

- A sessão expira (geralmente ~4h) e o lab tem limite de horas totais do
  curso. Recursos podem ser parados/terminados ao reiniciar o lab — confirme
  no seu curso se o estado das instâncias persiste entre sessões.
- Sem domínio próprio não há certificado TLS confiável; por isso este setup
  roda só LDAP em texto puro (porta 389, sem 636/LDAPS), adequado só para
  teste dentro de uma Security Group fechada, nunca para produção.
- Se o Elastic IP for liberado ao encerrar o lab, reassocie-o (ou atualize
  onde o projeto aponta para este LDAP) na próxima sessão.
- As senhas do seed (`Senha123!`) e do `.env` ficam em texto puro no LDIF e
  no arquivo de ambiente — aceitável só porque é um diretório descartável de
  teste, dentro de uma Security Group fechada ao seu IP.
