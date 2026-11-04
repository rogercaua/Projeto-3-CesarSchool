import { api } from './api.js';
import { icon } from './icons.js';
import { iniciarPagina, temPapel } from './layout.js';
import { $, badgeSolicitacao, chipTipo, esc, fmtData, renderPager, toast } from './util.js';

const usuario = await iniciarPagina('pendencias', { papeis: ['EDITOR_TECNICO', 'GESTOR_INFO', 'ADMIN'] });
const LIMITE = 10;
const gestor = temPapel(usuario, 'GESTOR_INFO');
const soEditor = temPapel(usuario, 'EDITOR_TECNICO') && !temPapel(usuario, 'GESTOR_INFO', 'ADMIN');

const ABAS = [
  { chave: '', rotulo: 'Todos', total: 'TODOS' },
  { chave: 'PENDENTE', rotulo: 'Pendentes', total: 'PENDENTE' },
  { chave: 'DEVOLVIDA', rotulo: 'Devolvidas', total: 'DEVOLVIDA' },
  { chave: 'APROVADA', rotulo: 'Aprovadas', total: 'APROVADA' },
  { chave: 'REJEITADA', rotulo: 'Rejeitadas', total: 'REJEITADA' },
  { chave: 'CANCELADA', rotulo: 'Canceladas', total: 'CANCELADA' },
];

let aba = '';
let skip = 0;
let pedido = 0;

if (soEditor) {
  document.title = 'Minhas Solicitações · GovCadastral';
  $('#titulo').textContent = 'Minhas Solicitações';
  $('#subtitulo').textContent = 'Acompanhe o andamento dos seus pedidos de alteração cadastral';
  $('#acoes').innerHTML = `<a class="btn btn-primary" href="nova-solicitacao.html">${icon('plus')}Nova Solicitação</a>`;
}

function acao(s) {
  const href = `solicitacao.html?id=${s.id}`;
  if (gestor && s.status === 'PENDENTE') return `<a class="link-acao" href="${href}">Analisar ${icon('chevron')}</a>`;
  if (soEditor && s.status === 'DEVOLVIDA') return `<a class="link-acao" href="${href}">Corrigir ${icon('chevron')}</a>`;
  return `<a class="link-muted" href="${href}">Ver detalhes</a>`;
}

async function carregarAbas() {
  const total = await api('/solicitacoes/contagem');
  $('#tabs').innerHTML = ABAS.map(
    (a) => `<button type="button" class="tab ${a.chave === aba ? 'sel' : ''}" data-aba="${a.chave}">
      ${esc(a.rotulo)}<span class="n">${total[a.total] ?? 0}</span></button>`,
  ).join('');
  document.querySelectorAll('.tab').forEach((b) => {
    b.onclick = () => {
      aba = b.dataset.aba;
      skip = 0;
      carregarAbas();
      carregarLista();
    };
  });
}

async function carregarLista() {
  const meu = ++pedido;
  $('#tbody').innerHTML = '<tr><td colspan="8" class="vazio">Carregando…</td></tr>';
  let dados;
  try {
    dados = await api('/solicitacoes', { params: { status: aba, skip, limit: LIMITE } });
  } catch (e) {
    if (meu === pedido) $('#tbody').innerHTML = `<tr><td colspan="8" class="vazio">${esc(e.message)}</td></tr>`;
    return;
  }
  if (meu !== pedido) return;

  $('#tbody').innerHTML = dados.itens.length
    ? dados.itens
        .map(
          (s) => `<tr>
            <td class="mono muted">${esc(s.protocolo)}</td>
            <td>${chipTipo(s.tipo)}</td>
            <td class="nome">${esc(s.unidade_nome ?? '—')}</td>
            <td>${esc(s.solicitante_nome)}</td>
            <td class="mono muted">${fmtData(s.criada_em)}</td>
            <td>${s.unidade_cnes ? `<span class="mono xs">${esc(s.unidade_cnes)}</span>` : `<span class="warn-inline">${icon('alert')}Sem CNES</span>`}</td>
            <td>${badgeSolicitacao(s.status)}</td>
            <td>${acao(s)}</td>
          </tr>`,
        )
        .join('')
    : '<tr><td colspan="8" class="vazio">Nenhuma solicitação nesta aba.</td></tr>';

  $('#rodape').textContent = `Exibindo ${dados.itens.length} de ${dados.total} registro(s) · Atualizado às ${new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
  renderPager($('#pager'), { skip, limit: LIMITE, total: dados.total }, (novo) => {
    skip = novo;
    carregarLista();
  });
}

try {
  await Promise.all([carregarAbas(), carregarLista()]);
} catch (e) {
  toast(e.message);
}
