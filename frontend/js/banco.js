import { api } from './api.js';
import { COR_STATUS, PALETA, grafico, rotuloMes } from './graficos.js';
import { iniciarPagina, temPapel } from './layout.js';
import {
  $, STATUS_SOL, TIPO_SOL, abrirModal, badgeSolicitacao, chipTipo, debounce, esc, fmtDataHora, toast,
} from './util.js';

const usuario = await iniciarPagina('banco', { papeis: ['GESTOR_INFO', 'ADMIN'] });

const opcoes = (mapa) => Object.entries(mapa).map(([v, t]) => `<option value="${v}">${esc(t)}</option>`).join('');
let distritosHtml = '';

// Filtros que cada view aceita (o backend confere a mesma lista) e o gráfico de cada uma.
const VIEWS = {
  vw_unidades_por_distrito: {
    titulo: 'Unidades por distrito',
    descricao: 'Total de unidades, ativas, inativas, ativas sem CNES e % das ativas com CNES em cada distrito.',
    filtros: () => `<select data-f="distrito_id" aria-label="Distrito"><option value="">Todos os distritos</option>${distritosHtml}</select>`,
    grafico: (l) => ({
      type: 'bar',
      data: {
        labels: l.map((r) => r.distrito),
        datasets: [
          { label: 'Ativas', data: l.map((r) => r.ativas), backgroundColor: COR_STATUS.APROVADA },
          { label: 'Sem CNES', data: l.map((r) => r.sem_cnes), backgroundColor: COR_STATUS.PENDENTE },
        ],
      },
      options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
    }),
  },
  vw_solicitacoes_detalhadas: {
    titulo: 'Solicitações detalhadas',
    descricao: 'Solicitação com solicitante, unidade, distrito, última decisão e dias até a decisão (fn_protocolo, fn_dias_entre).',
    filtros: () => `
      <select data-f="status" aria-label="Status"><option value="">Todos os status</option>${opcoes(STATUS_SOL)}</select>
      <select data-f="tipo" aria-label="Tipo"><option value="">Todos os tipos</option>${opcoes(TIPO_SOL)}</select>
      <select data-f="distrito_id" aria-label="Distrito"><option value="">Todos os distritos</option>${distritosHtml}</select>
      <label class="mini">De <input type="date" data-f="inicio"></label>
      <label class="mini">até <input type="date" data-f="fim"></label>`,
    grafico: (l) => {
      const cont = {};
      l.forEach((r) => (cont[r.status] = (cont[r.status] || 0) + 1));
      const chaves = Object.keys(cont);
      return {
        type: 'doughnut',
        data: { labels: chaves.map((c) => STATUS_SOL[c]), datasets: [{ data: chaves.map((c) => cont[c]), backgroundColor: chaves.map((c) => COR_STATUS[c]) }] },
        options: { plugins: { legend: { position: 'right' } } },
      };
    },
  },
  vw_desempenho_gestores: {
    titulo: 'Desempenho dos gestores',
    descricao: 'Decisões por gestor, taxa de aprovação (fn_percentual) e tempo médio de análise em dias.',
    filtros: () => '',
    grafico: (l) => ({
      type: 'bar',
      data: {
        labels: l.map((r) => r.gestor),
        datasets: [
          { label: 'Taxa de aprovação (%)', data: l.map((r) => r.taxa_aprovacao), backgroundColor: PALETA[0] },
          { label: 'Média de dias', data: l.map((r) => r.media_dias), backgroundColor: PALETA[3] },
        ],
      },
      options: { scales: { y: { beginAtZero: true } } },
    }),
  },
  vw_evolucao_mensal: {
    titulo: 'Evolução mensal',
    descricao: 'Solicitações criadas por mês e a situação atual delas.',
    filtros: () => `<label class="mini">De <input type="date" data-f="inicio"></label><label class="mini">até <input type="date" data-f="fim"></label>`,
    grafico: (l) => ({
      type: 'line',
      data: {
        labels: l.map((r) => rotuloMes(r.mes)),
        datasets: [
          { label: 'Criadas', data: l.map((r) => r.criadas), borderColor: PALETA[0], backgroundColor: PALETA[0], tension: 0.3 },
          { label: 'Aprovadas', data: l.map((r) => r.aprovadas), borderColor: COR_STATUS.APROVADA, backgroundColor: COR_STATUS.APROVADA, tension: 0.3 },
          { label: 'Em aberto', data: l.map((r) => r.em_aberto), borderColor: COR_STATUS.PENDENTE, backgroundColor: COR_STATUS.PENDENTE, tension: 0.3 },
        ],
      },
      options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
    }),
  },
};

function celula(coluna, valor) {
  if (valor == null) return '<td class="muted">—</td>';
  if (coluna === 'status' && STATUS_SOL[valor]) return `<td>${badgeSolicitacao(valor)}</td>`;
  if (coluna === 'tipo' && TIPO_SOL[valor]) return `<td>${chipTipo(valor)}</td>`;
  if (coluna.endsWith('_em')) return `<td class="mono">${esc(fmtDataHora(valor))}</td>`;
  if (coluna.startsWith('pct_') || coluna.startsWith('taxa_')) return `<td class="mono">${esc(valor)}%</td>`;
  return `<td${typeof valor === 'number' ? ' class="mono"' : ''}>${esc(valor)}</td>`;
}

let viewAtual = 'vw_unidades_por_distrito';
let pedido = 0;
let sqlViews = {};

async function carregarView() {
  const meu = ++pedido;
  const params = {};
  document.querySelectorAll('#v-filtros [data-f]').forEach((el) => (params[el.dataset.f] = el.value));
  let r;
  try {
    r = await api(`/banco/views/${viewAtual}`, { params });
  } catch (e) {
    if (meu === pedido) $('#v-tbody').innerHTML = `<tr><td class="vazio">${esc(e.message)}</td></tr>`;
    return;
  }
  if (meu !== pedido) return; // chegou uma resposta mais antiga
  $('#v-contagem').textContent = r.truncado
    ? `mostrando as primeiras ${r.linhas.length} linhas; use os filtros para ver o restante`
    : `${r.linhas.length} linha(s)`;
  $('#v-thead').innerHTML = `<tr>${r.colunas.map((c) => `<th>${esc(c)}</th>`).join('')}</tr>`;
  $('#v-tbody').innerHTML = r.linhas.length
    ? r.linhas.map((l) => `<tr>${l.map((v, i) => celula(r.colunas[i], v)).join('')}</tr>`).join('')
    : `<tr><td colspan="${r.colunas.length}" class="vazio">Nenhum registro para os filtros aplicados.</td></tr>`;
  const objetos = r.linhas.map((l) => Object.fromEntries(l.map((v, i) => [r.colunas[i], v])));
  grafico($('#v-grafico'), VIEWS[viewAtual].grafico(objetos));
}

function abrirView(nome) {
  viewAtual = nome;
  const v = VIEWS[nome];
  $('#v-abas').innerHTML = Object.entries(VIEWS)
    .map(([n, x]) => `<button type="button" role="tab" class="tab ${n === nome ? 'sel' : ''}" data-view="${n}" aria-selected="${n === nome}">${esc(x.titulo)}</button>`)
    .join('');
  $('#v-descricao').innerHTML = `<span class="mono">${esc(nome)}</span> · ${esc(v.descricao)}`;
  const filtros = v.filtros();
  $('#v-filtros').innerHTML = filtros ? `<div class="filters-label">Filtros</div>${filtros}` : '<span class="xs muted">Esta view não tem filtros.</span>';
  $('#v-sql').textContent = sqlViews[nome] || '';
  carregarView();
}

$('#v-abas').onclick = (e) => {
  const b = e.target.closest('[data-view]');
  if (b) abrirView(b.dataset.view);
};
$('#v-filtros').onchange = carregarView;

// ---------- procedimentos ----------

const ROTULOS_SP1 = {
  inicio: 'Início', fim: 'Fim', unidades_total: 'Unidades', unidades_ativas: 'Ativas', unidades_sem_cnes: 'Ativas sem CNES',
  pct_com_cnes: '% com CNES', solicitacoes: 'Solicitações', aprovadas: 'Aprovadas', rejeitadas: 'Rejeitadas',
  em_aberto: 'Em aberto', taxa_aprovacao: 'Taxa de aprovação (%)', media_dias_decisao: 'Média de dias até a decisão',
  solicitacoes_periodo_anterior: 'Solicitações no período anterior', variacao_pct: 'Variação (%)',
};

$('#sp1-exec').onclick = async () => {
  try {
    const r = await api('/banco/procedimentos/sp_relatorio_periodo', {
      params: { inicio: $('#sp1-inicio').value, fim: $('#sp1-fim').value, distrito_id: $('#sp1-distrito').value },
    });
    $('#sp1-res').innerHTML = `<table class="data"><tbody>${Object.entries(r)
      .map(([k, v]) => `<tr><td class="nome">${esc(ROTULOS_SP1[k] || k)}</td><td class="mono">${esc(v ?? '—')}</td></tr>`)
      .join('')}</tbody></table>`;
  } catch (e) {
    toast(e.message);
  }
};

$('#sp2-exec').onclick = () => {
  const dias = Number($('#sp2-dias').value);
  abrirModal({
    cor: 'red',
    titulo: 'Executar sp_cancelar_paradas',
    sub: `Cancela solicitações em aberto sem movimentação há mais de ${dias} dias`,
    botao: 'Executar',
    nomeIcone: 'x',
    corpo: '<p>As solicitações afetadas passam a CANCELADA e não podem ser reabertas. Deseja continuar?</p>',
    confirmar: async () => {
      const r = await api('/banco/procedimentos/sp_cancelar_paradas', { method: 'POST', body: { dias } });
      $('#sp2-res').hidden = false;
      $('#sp2-res').textContent = `${r.canceladas} solicitação(ões) cancelada(s)${r.ids.length ? ` · ids ${r.ids.join(', ')}` : ''}. Veja o histórico de status abaixo.`;
      toast('Procedimento executado.', 'ok');
    },
    depois: async () => {
      await carregarHistorico();
      await carregarView();
    },
  });
};

// ---------- funções ----------

let funcoes = [];
const EXEMPLOS = { fn_percentual: ['3', '4'], fn_dias_entre: ['2026-01-01', '2026-03-15'], fn_protocolo: ['7', '2026-05-10'] };

function escolherFuncao() {
  const f = funcoes.find((x) => x.nome === $('#fn-nome').value);
  $('#fn-desc').textContent = f.descricao;
  [$('#fn-a0').value, $('#fn-a1').value] = EXEMPLOS[f.nome] || ['', ''];
  $('#fn-res').textContent = 'SELECT …';
}

$('#fn-nome').onchange = escolherFuncao;
$('#fn-exec').onclick = async () => {
  const nome = $('#fn-nome').value;
  const args = [$('#fn-a0').value, $('#fn-a1').value].map((v) => (v.trim() !== '' && !Number.isNaN(Number(v)) ? Number(v) : v));
  try {
    const r = await api(`/banco/funcoes/${nome}`, { method: 'POST', body: { argumentos: args } });
    $('#fn-res').textContent = `SELECT ${nome}(${args.map((a) => JSON.stringify(a)).join(', ')}) → ${JSON.stringify(r.resultado)}`;
  } catch (e) {
    $('#fn-res').textContent = e.message;
  }
};

// ---------- triggers e histórico ----------

async function carregarHistorico() {
  try {
    const linhas = await api('/banco/historico-status', { params: { protocolo: $('#h-protocolo').value.trim(), limit: 50 } });
    $('#h-tbody').innerHTML = linhas.length
      ? linhas.map((h) => `<tr>
          <td class="mono">${esc(fmtDataHora(h.mudou_em))}</td>
          <td class="mono">${esc(h.protocolo)}</td>
          <td>${h.status_anterior ? badgeSolicitacao(h.status_anterior) : '<span class="muted">criada</span>'}</td>
          <td>${badgeSolicitacao(h.status_novo)}</td></tr>`).join('')
      : '<tr><td colspan="4" class="vazio">Nenhuma mudança registrada.</td></tr>';
  } catch (e) {
    toast(e.message);
  }
}
$('#h-protocolo').oninput = debounce(carregarHistorico);

// ---------- início ----------

try {
  const [objetos, distritos] = await Promise.all([api('/banco/objetos'), api('/distritos')]);
  distritosHtml = distritos.map((d) => `<option value="${d.id}">${esc(d.nome)}</option>`).join('');
  $('#sp1-distrito').insertAdjacentHTML('beforeend', distritosHtml);
  sqlViews = Object.fromEntries(objetos.views.map((v) => [v.nome, v.sql]));

  funcoes = objetos.funcoes;
  $('#fn-nome').innerHTML = funcoes.map((f) => `<option>${esc(f.nome)}</option>`).join('');
  escolherFuncao();

  const sp = Object.fromEntries(objetos.procedimentos.map((p) => [p.nome, p]));
  $('#sp1-desc').textContent = sp.sp_relatorio_periodo.descricao;
  $('#sp2-desc').textContent = sp.sp_cancelar_paradas.descricao;
  $('#sp2').hidden = !temPapel(usuario, 'ADMIN');
  $('#sp-sql').innerHTML = objetos.procedimentos
    .map((p) => `<div class="xs muted" style="padding: 8px 20px">${esc(p.nome)}</div><pre class="sql">${esc(p.sql)}</pre>`)
    .join('');

  $('#t-contagem').textContent = `${objetos.triggers.length} trigger(s)`;
  $('#t-lista').innerHTML = objetos.triggers
    .map((t) => `<details class="obj"><summary><span class="mono">${esc(t.nome)}</span><span class="d">tabela ${esc(t.tabela)}</span></summary><pre class="sql">${esc(t.sql)}</pre></details>`)
    .join('');

  abrirView(viewAtual);
  await carregarHistorico();
} catch (e) {
  toast(e.message);
}
