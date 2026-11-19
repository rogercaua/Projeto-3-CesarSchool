# Keycloak no AWS Academy Learner Lab

Setup mínimo de Keycloak (modo dev, HTTP) para testar o `AUTH_MODE=keycloak`
deste projeto, pensado para rodar numa instância EC2 do Learner Lab.

## 1. Subir o lab e a instância EC2

1. No curso, abra **Modules → AWS Academy Learner Lab → Start Lab** e espere o
   círculo ficar verde.
2. Clique em **AWS** para abrir o Console (já logado).
3. **EC2 → Launch Instance**: AMI Ubuntu 22.04, tipo `t3.small` (se o lab
   recusar, caia para `t2.micro`/`t3.micro`).
4. Crie/baixe o key pair `.pem` para SSH.
5. Security Group: libere `22` (seu IP), `80` (público).
6. (Opcional, recomendado) **EC2 → Elastic IPs → Allocate** e associe à
   instância, para o IP não mudar se ela reiniciar durante a sessão do lab.

## 2. Copiar estes arquivos para a instância

Do seu computador:

```bash
scp -i sua-chave.pem -r infra/keycloak ubuntu@<ip-da-instancia>:~/keycloak
```

## 3. Instalar Docker e subir o Keycloak

Via SSH na instância:

```bash
ssh -i sua-chave.pem ubuntu@<ip-da-instancia>

sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER && newgrp docker

cd ~/keycloak
cp .env.example .env
nano .env   # troque as senhas

docker compose up -d
docker compose logs -f keycloak   # espere "Keycloak ... started"
```

Acesse `http://<ip-da-instancia>/admin` com o usuário/senha definidos em
`KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD`.

## 4. Criar o realm e o client

No console admin do Keycloak:

1. Crie um realm (ex.: `saude`).
2. **Clients → Create client**, client ID `govcadastral-web` (mesmo valor do
   `KEYCLOAK_CLIENT_ID` do projeto), tipo **público**.
3. Habilite **Standard Flow**, desabilite os demais fluxos que não usa.
4. Em **Advanced → Proof Key for Code Exchange**, marque `S256`.
5. Em **Valid redirect URIs**, adicione a URL do frontend do projeto (ex.:
   `http://127.0.0.1:5500/index.html` em dev).
6. Crie um usuário de teste em **Users** com uma senha.

## 5. Apontar o projeto para este Keycloak

No `.env` do `Projeto-3-CesarSchool`:

```
AUTH_MODE=keycloak
KEYCLOAK_ISSUER=http://<ip-da-instancia>/realms/saude
KEYCLOAK_CLIENT_ID=govcadastral-web
CRIPTO_CHAVE=<gere com: python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())">
```

## Limitações do Learner Lab

- A sessão expira (geralmente ~4h) e o lab tem um limite de horas total do
  curso. Resources podem ser parados/terminados ao reiniciar o lab —
  confirme no seu curso se o estado das instâncias persiste entre sessões.
- Sem domínio próprio não há HTTPS automático; por isso este setup usa
  `start-dev` (HTTP) do Keycloak, adequado só para teste, nunca para produção.
- Se o Elastic IP for liberado ao encerrar o lab, reassocie-o (ou atualize o
  `KEYCLOAK_ISSUER` no `.env` do projeto) na próxima sessão.
