import { api } from './api.js';
import { iniciarPagina } from './layout.js';
import { $, esc, fmtDataHora, renderPager, toast } from './util.js';

await iniciarPagina('auditoria', { papeis: ['ADMIN'] });
const LIMITE = 15;
let skip = 0;
let entidade = '';

const ACOES = {
  SOLICITACAO_CRIADA: 'Solicitação criada',
  SOLICITACAO_REENVIADA: 'Solicitação reenviada',
  SOLICITACAO_APROVADA: 'Solicitação aprovada',
  SOLICITACAO_DEVOLVIDA: 'Solicitação devolvida',
  SOLICITACAO_REJEITADA: 'Solicitação rejeitada',
  SOLICITACAO_CANCELADA: 'Solicitação cancelada',
  DISTRITO_CRIADO: 'Distrito criado',
  DISTRITO_ATUALIZADO: 'Distrito atualizado',
  DISTRITO_EXCLUIDO: 'Distrito excluído',
};

function detalhes(d) {
  if (!d) return '<span class="muted">—</span>';
  return Object.entries(d)
    .map(([k, v]) => `<span class="xs"><span class="muted">${esc(k)}:</span> ${esc(v)}</span>`)
    .join('<br>');
}

async function carregar() {
  $('#tbody').innerHTML = '<tr><td colspan="5" class="vazio">Carregando…</td></tr>';
  try {
    const dados = await api('/auditoria', { params: { entidade, skip, limit: LIMITE } });
    $('#contagem').textContent = `${dados.total} evento(s)`;
    $('#tbody').innerHTML = dados.itens.length
      ? dados.itens
          .map(
            (e) => `<tr>
              <td class="mono muted">${fmtDataHora(e.ocorrido_em)}</td>
              <td>${esc(e.usuario_nome ?? '—')}</td>
              <td class="nome">${esc(ACOES[e.acao] ?? e.acao)}</td>
              <td class="mono">${esc(e.entidade)}${e.entidade_id ? ` #${e.entidade_id}` : ''}</td>
              <td>${detalhes(e.detalhes)}</td></tr>`,
          )
          .join('')
      : '<tr><td colspan="5" class="vazio">Nenhum evento registrado.</td></tr>';
    renderPager($('#pager'), { skip, limit: LIMITE, total: dados.total }, (novo) => {
      skip = novo;
      carregar();
    });
  } catch (e) {
    toast(e.message);
    $('#tbody').innerHTML = `<tr><td colspan="5" class="vazio">${esc(e.message)}</td></tr>`;
  }
}

$('#f-entidade').onchange = (e) => {
  entidade = e.target.value;
  skip = 0;
  carregar();
};
await carregar();
