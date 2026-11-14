import { api, getToken, salvarToken } from './api.js';
import { icon } from './icons.js';
import { concluirSSO, entrarSSO } from './sso.js';
import { $, $$, esc } from './util.js';

const PERFIS = [
  { papel: 'LEITOR', rotulo: 'Leitor', desc: 'Consulta e visualização', email: 'joao.silva@pe.gov.br', nome: 'João Silva' },
  { papel: 'EDITOR_TECNICO', rotulo: 'Editor Técnico', desc: 'Submissão de solicitações', email: 'anaramos@pe.gov.br', nome: 'Ana Paula Ramos' },
  { papel: 'GESTOR_INFO', rotulo: 'Gestor de Informação', desc: 'Aprovação e conciliação', email: 'rmendes@pe.gov.br', nome: 'Ricardo Mendes' },
  { papel: 'ADMIN', rotulo: 'Administrador', desc: 'Acesso completo', email: 'admin@pe.gov.br', nome: 'Administrador' },
];

$$('[data-icon]').forEach((el) => (el.innerHTML = icon(el.dataset.icon)));

function mostrarErro(mensagem) {
  $('#erro').textContent = mensagem;
  $('#erro').hidden = !mensagem;
}

// ---------- modo dev: login simulado com escolha de perfil ----------

let perfil = PERFIS[2];

function desenharPerfis() {
  $('#perfis').innerHTML = PERFIS.map(
    (p) => `<button type="button" class="role-card ${p === perfil ? 'sel' : ''}" data-papel="${p.papel}">
      <div class="t">${esc(p.rotulo)}</div><div class="d">${esc(p.desc)}</div></button>`,
  ).join('');
  $$('.role-card').forEach((b) => {
    b.onclick = () => {
      perfil = PERFIS.find((p) => p.papel === b.dataset.papel);
      $('#email').value = perfil.email;
      desenharPerfis();
    };
  });
}

const nomeDoEmail = (email) =>
  email.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) || 'Usuário';

async function entrarDev() {
  const email = $('#email').value.trim();
  if (!email) throw new Error('Informe o e-mail.');
  const nome = email === perfil.email ? perfil.nome : nomeDoEmail(email);
  const { access_token } = await api('/auth/dev-login', { method: 'POST', body: { email, nome, papel: perfil.papel } });
  salvarToken(access_token);
}

// ---------- início: o backend diz qual modo está ativo ----------

let cfg;
try {
  cfg = await api('/auth/config');
} catch (e) {
  $('#banner').textContent = 'Servidor indisponível';
  mostrarErro(e.message);
  throw e;
}

if (cfg.modo === 'keycloak') {
  $('#banner').textContent = 'Autenticação via Keycloak · SSO Municipal';
  $('#sso-msg').hidden = false;
  $('#entrar').textContent = 'Entrar com o SSO da Prefeitura';
  try {
    if (await concluirSSO(cfg)) location.replace('dashboard.html'); // voltando do Keycloak com o código
  } catch (e) {
    mostrarErro(e.message);
  }
} else {
  $('#banner').textContent = 'Modo desenvolvimento · login simulado';
  $('#dev').hidden = false;
  $('#email').value = perfil.email;
  $('#entrar').textContent = 'Entrar';
  desenharPerfis();
}
$('#entrar').disabled = false;

// Já autenticado? Vai direto ao dashboard.
if (getToken()) {
  api('/auth/me').then(() => location.replace('dashboard.html')).catch(() => {});
}

$('#form-login').onsubmit = async (e) => {
  e.preventDefault();
  mostrarErro('');
  $('#entrar').disabled = true;
  try {
    if (cfg.modo === 'keycloak') {
      await entrarSSO(cfg); // sai da página; o retorno é tratado por concluirSSO
    } else {
      await entrarDev();
      location.href = 'dashboard.html';
    }
  } catch (err) {
    mostrarErro(err.message);
    $('#entrar').disabled = false;
  }
};
