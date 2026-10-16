import { api, getToken, salvarToken } from './api.js';
import { icon } from './icons.js';
import { $, $$, esc } from './util.js';

const PERFIS = [
  { papel: 'LEITOR', rotulo: 'Leitor', desc: 'Consulta e visualização', email: 'joao.silva@pe.gov.br', nome: 'João Silva' },
  { papel: 'EDITOR_TECNICO', rotulo: 'Editor Técnico', desc: 'Submissão de solicitações', email: 'anaramos@pe.gov.br', nome: 'Ana Paula Ramos' },
  { papel: 'GESTOR_INFO', rotulo: 'Gestor de Informação', desc: 'Aprovação e conciliação', email: 'rmendes@pe.gov.br', nome: 'Ricardo Mendes' },
  { papel: 'ADMIN', rotulo: 'Administrador', desc: 'Acesso completo', email: 'admin@pe.gov.br', nome: 'Administrador' },
];

$$('[data-icon]').forEach((el) => (el.innerHTML = icon(el.dataset.icon)));

// Já autenticado? Vai direto ao dashboard.
if (getToken()) {
  api('/auth/me').then(() => location.replace('dashboard.html')).catch(() => {});
}

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

$('#email').value = perfil.email;
desenharPerfis();

$('#form-login').onsubmit = async (e) => {
  e.preventDefault();
  const erro = $('#erro');
  erro.hidden = true;
  const email = $('#email').value.trim();
  const nome = email === perfil.email ? perfil.nome : nomeDoEmail(email);

  $('#entrar').disabled = true;
  try {
    const { access_token } = await api('/auth/dev-login', { method: 'POST', body: { email, nome, papel: perfil.papel } });
    salvarToken(access_token);
    location.href = 'dashboard.html';
  } catch (err) {
    erro.textContent =
      err.status === 404
        ? 'O login simulado está desativado neste servidor (AUTH_MODE=keycloak). Use o SSO institucional.'
        : err.message;
    erro.hidden = false;
    $('#entrar').disabled = false;
  }
};
