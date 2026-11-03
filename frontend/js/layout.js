import { api, getToken, sair } from './api.js';
import { icon } from './icons.js';
import { $$, esc } from './util.js';

export const temPapel = (usuario, ...papeis) => papeis.some((p) => usuario.papeis.includes(p));

const ROTULO_PAPEL = {
  LEITOR: 'LEITOR',
  EDITOR_TECNICO: 'EDITOR_TECNICO',
  GESTOR_INFO: 'GESTOR_INFO',
  ADMIN: 'ADMIN',
};

function item(href, chave, ativo, nomeIcone, rotulo, badge = 0) {
  return `<a class="nav-link ${chave === ativo ? 'active' : ''}" href="${href}">
    ${icon(nomeIcone, 'icon-lg')}<span class="label">${esc(rotulo)}</span>
    ${badge ? `<span class="nav-badge">${badge}</span>` : ''}
  </a>`;
}

function sidebarHtml(usuario, ativo, badge) {
  const editor = temPapel(usuario, 'EDITOR_TECNICO');
  const gestao = temPapel(usuario, 'GESTOR_INFO', 'ADMIN');
  const admin = temPapel(usuario, 'ADMIN');

  let nav = item('dashboard.html', 'dashboard', ativo, 'grid', 'Dashboard');
  if (editor) {
    nav += item('nova-solicitacao.html', 'nova', ativo, 'plus', 'Nova Solicitação');
    nav += item('pendencias.html', 'pendencias', ativo, 'inbox', 'Minhas Solicitações', badge);
  }
  if (gestao) {
    nav += '<div class="nav-section">Gestão</div>';
    nav += item('pendencias.html', 'pendencias', ativo, 'inbox', 'Central de Pendências', badge);
    nav += item('conciliacao.html', 'conciliacao', ativo, 'refresh', 'Conciliação CNES');
  }
  if (admin) {
    nav += '<div class="nav-section">Administração</div>';
    nav += item('distritos.html', 'distritos', ativo, 'mapPin', 'Distritos');
    nav += item('auditoria.html', 'auditoria', ativo, 'fileText', 'Trilha de Auditoria');
  }

  const papel = ROTULO_PAPEL[usuario.papeis[0]] || usuario.papeis.join(', ');
  return `
    <div class="brand">
      <div class="brand-logo">${icon('shield')}</div>
      <div><div class="brand-name">GovCadastral</div><div class="brand-sub">Plataforma Municipal</div></div>
    </div>
    <div class="role-box"><small>Perfil de acesso</small><span>${esc(papel)}</span></div>
    <nav class="nav">${nav}</nav>
    <div class="user-box">
      <div><div class="nome">${esc(usuario.nome)}</div><div class="email">${esc(usuario.email)}</div></div>
      <button type="button" class="icon-btn" id="btn-logout" title="Sair" aria-label="Sair">${icon('logout')}</button>
    </div>`;
}

async function contarBadge(usuario) {
  try {
    if (temPapel(usuario, 'GESTOR_INFO', 'ADMIN')) return (await api('/solicitacoes/contagem')).PENDENTE;
    if (temPapel(usuario, 'EDITOR_TECNICO')) return (await api('/solicitacoes/contagem')).DEVOLVIDA;
  } catch {
    /* o badge é opcional */
  }
  return 0;
}

/**
 * Inicialização comum das páginas autenticadas: confere a sessão, desenha a barra lateral
 * e preenche os ícones marcados com data-icon. Devolve o usuário logado.
 * Se `papeis` for informado e o usuário não tiver nenhum deles, volta ao dashboard.
 */
export async function iniciarPagina(ativo, { papeis } = {}) {
  if (!getToken()) {
    location.replace('index.html');
    return new Promise(() => {});
  }

  let usuario;
  try {
    usuario = await api('/auth/me');
  } catch (erro) {
    document.getElementById('main').innerHTML = `<div class="page-error">${esc(erro.message)}</div>`;
    throw erro;
  }

  if (papeis && !temPapel(usuario, ...papeis)) {
    location.replace('dashboard.html');
    return new Promise(() => {});
  }

  const badge = await contarBadge(usuario);
  document.getElementById('sidebar').innerHTML = sidebarHtml(usuario, ativo, badge);
  document.getElementById('btn-logout').onclick = sair;
  $$('[data-icon]').forEach((el) => {
    el.innerHTML = icon(el.dataset.icon, el.dataset.iconClass || '');
  });
  return usuario;
}
