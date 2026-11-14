import { api } from './api.js';
import { iniciarPagina } from './layout.js';
import { $, abrirModal, esc, toast } from './util.js';

await iniciarPagina('distritos', { papeis: ['ADMIN'] });

let distritos = [];

function nomeValido(valor) {
  const nome = valor.trim();
  if (nome.length < 2) throw new Error('Informe um nome com ao menos 2 caracteres.');
  return nome;
}

async function carregar() {
  try {
    distritos = await api('/distritos');
    $('#contagem').textContent = `${distritos.length} distrito(s)`;
    $('#tbody').innerHTML = distritos.length
      ? distritos
          .map(
            (d) => `<tr>
              <td class="nome">${esc(d.nome)}</td>
              <td>
                <button type="button" class="btn btn-ghost btn-xs" data-acao="editar" data-id="${d.id}">Editar</button>
                <button type="button" class="btn btn-ghost btn-xs" data-acao="excluir" data-id="${d.id}">Excluir</button>
              </td></tr>`,
          )
          .join('')
      : '<tr><td colspan="2" class="vazio">Nenhum distrito cadastrado.</td></tr>';
  } catch (e) {
    toast(e.message);
    $('#tbody').innerHTML = `<tr><td colspan="2" class="vazio">${esc(e.message)}</td></tr>`;
  }
}

function editar(d) {
  abrirModal({
    cor: 'amber',
    titulo: 'Editar Distrito',
    sub: 'O novo nome aparece em todas as unidades do distrito.',
    botao: 'Salvar',
    nomeIcone: 'check',
    corpo: `<label class="lbl" for="m-nome">Nome <span class="req">*</span></label>
      <input type="text" id="m-nome" maxlength="100" value="${esc(d.nome)}">`,
    depois: carregar,
    confirmar: async (raiz) => {
      const nome = nomeValido(raiz.querySelector('#m-nome').value);
      await api(`/distritos/${d.id}`, { method: 'PUT', body: { nome } });
      toast('Distrito atualizado.', 'ok');
    },
  });
}

function excluir(d) {
  abrirModal({
    cor: 'red',
    titulo: 'Excluir Distrito',
    sub: d.nome,
    botao: 'Excluir',
    nomeIcone: 'x',
    corpo: '<p>Só é possível excluir distritos sem unidades vinculadas. Deseja continuar?</p>',
    depois: carregar,
    confirmar: async () => {
      await api(`/distritos/${d.id}`, { method: 'DELETE' });
      toast('Distrito excluído.', 'ok');
    },
  });
}

$('#tbody').onclick = (e) => {
  const botao = e.target.closest('[data-acao]');
  if (!botao) return;
  const d = distritos.find((x) => String(x.id) === botao.dataset.id);
  if (d) (botao.dataset.acao === 'editar' ? editar : excluir)(d);
};

$('#form-novo').onsubmit = async (e) => {
  e.preventDefault();
  const erro = $('#erro');
  const botao = $('#adicionar');
  erro.hidden = true;
  botao.disabled = true;
  try {
    await api('/distritos', { method: 'POST', body: { nome: nomeValido($('#f-nome').value) } });
    $('#f-nome').value = '';
    toast('Distrito adicionado.', 'ok');
    await carregar();
  } catch (err) {
    erro.textContent = err.message;
    erro.hidden = false;
  } finally {
    botao.disabled = false;
    $('#f-nome').focus();
  }
};

await carregar();
