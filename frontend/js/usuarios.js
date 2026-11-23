import { api } from './api.js';
import { iniciarPagina } from './layout.js';
import { $, abrirModal, debounce, esc, toast } from './util.js';

const eu = await iniciarPagina('usuarios', { papeis: ['ADMIN'] });

let usuarios = [];

function lerForm(raiz, sufixo) {
  const nome = $(`#${sufixo}-nome`, raiz).value.trim();
  const email = $(`#${sufixo}-email`, raiz).value.trim();
  if (nome.length < 2) throw new Error('Informe um nome com ao menos 2 caracteres.');
  if (!/^[^@\s]+@[^@\s]+$/.test(email)) throw new Error('Informe um e-mail válido.');
  return { nome, email };
}

async function carregar() {
  try {
    usuarios = await api('/usuarios', { params: { q: $('#f-busca').value.trim() } });
    $('#contagem').textContent = `${usuarios.length} usuário(s)`;
    $('#tbody').innerHTML = usuarios.length
      ? usuarios
          .map(
            (u) => `<tr>
              <td class="mono muted">${u.id}</td>
              <td class="nome">${esc(u.nome)}${u.id === eu.id ? ' <span class="chip">você</span>' : ''}</td>
              <td>${esc(u.email)}</td>
              <td class="mono">${esc(u.keycloak_id)}</td>
              <td>
                <button type="button" class="btn btn-ghost btn-xs" data-acao="editar" data-id="${u.id}">Editar</button>
                <button type="button" class="btn btn-ghost btn-xs" data-acao="excluir" data-id="${u.id}" ${u.id === eu.id ? 'disabled' : ''}>Excluir</button>
                <button type="button" class="btn btn-ghost btn-xs" data-acao="anonimizar" data-id="${u.id}" ${u.id === eu.id || u.keycloak_id.startsWith('anonimizado:') ? 'disabled' : ''}>Anonimizar</button>
              </td></tr>`,
          )
          .join('')
      : '<tr><td colspan="5" class="vazio">Nenhum usuário encontrado.</td></tr>';
  } catch (e) {
    toast(e.message);
    $('#tbody').innerHTML = `<tr><td colspan="5" class="vazio">${esc(e.message)}</td></tr>`;
  }
}

function editar(u) {
  abrirModal({
    cor: 'amber',
    titulo: 'Editar Usuário',
    sub: 'No próximo login, nome e e-mail voltam a vir do token.',
    botao: 'Salvar',
    nomeIcone: 'check',
    corpo: `<div class="form-stack">
      <div><label class="lbl" for="m-nome">Nome <span class="req">*</span></label><input type="text" id="m-nome" maxlength="150" value="${esc(u.nome)}"></div>
      <div><label class="lbl" for="m-email">E-mail <span class="req">*</span></label><input type="email" id="m-email" maxlength="150" value="${esc(u.email)}"></div></div>`,
    depois: carregar,
    confirmar: async (raiz) => {
      await api(`/usuarios/${u.id}`, { method: 'PUT', body: lerForm(raiz, 'm') });
      toast('Usuário atualizado.', 'ok');
    },
  });
}

function excluir(u) {
  abrirModal({
    cor: 'red',
    titulo: 'Excluir Usuário',
    sub: u.nome,
    botao: 'Excluir',
    nomeIcone: 'x',
    corpo: '<p>Só é possível excluir usuários sem solicitações, decisões ou eventos de auditoria. Deseja continuar?</p>',
    depois: carregar,
    confirmar: async () => {
      await api(`/usuarios/${u.id}`, { method: 'DELETE' });
      toast('Usuário excluído.', 'ok');
    },
  });
}

function anonimizar(u) {
  abrirModal({
    cor: 'red',
    titulo: 'Anonimizar Usuário (LGPD)',
    sub: u.nome,
    botao: 'Anonimizar',
    nomeIcone: 'x',
    corpo: '<p>Nome, e-mail e login serão apagados de forma definitiva. Solicitações, decisões e auditoria continuam no histórico, sem identificar a pessoa. Deseja continuar?</p>',
    depois: carregar,
    confirmar: async () => {
      await api(`/usuarios/${u.id}/anonimizacao`, { method: 'POST' });
      toast('Usuário anonimizado.', 'ok');
    },
  });
}

const ACOES_LINHA = { editar, excluir, anonimizar };

$('#tbody').onclick = (e) => {
  const botao = e.target.closest('[data-acao]');
  if (!botao) return;
  const u = usuarios.find((x) => String(x.id) === botao.dataset.id);
  if (u) ACOES_LINHA[botao.dataset.acao](u);
};

$('#f-busca').oninput = debounce(carregar);

$('#form-novo').onsubmit = async (e) => {
  e.preventDefault();
  const erro = $('#erro');
  const botao = $('#adicionar');
  erro.hidden = true;
  botao.disabled = true;
  try {
    await api('/usuarios', { method: 'POST', body: lerForm(document, 'f') });
    $('#f-nome').value = '';
    $('#f-email').value = '';
    toast('Usuário adicionado.', 'ok');
    await carregar();
  } catch (err) {
    erro.textContent = err.message;
    erro.hidden = false;
  } finally {
    botao.disabled = false;
  }
};

await carregar();
