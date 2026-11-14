import { api } from './api.js';
import { icon } from './icons.js';
import { iniciarPagina, temPapel } from './layout.js';
import { COR_STATUS, PALETA, grafico, rotuloMes } from './graficos.js';
import { $, STATUS_SOL, TIPOS_UNIDADE, TIPO_SOL, badgeUnidade, debounce, esc, renderPager, toast } from './util.js';

const usuario = await iniciarPagina('dashboard');
const LIMITE = 10;
const filtro = { q: '', distrito_id: '', tipo: '', status: '' };
let skip = 0;
let pedido = 0;

if (temPapel(usuario, 'EDITOR_TECNICO')) {
  $('#acoes').innerHTML = `<a class="btn btn-primary" href="nova-solicitacao.html">${icon('plus')}Nova Solicitação</a>`;
}

async function carregarResumo() {
  const r = await api('/dashboard/resumo');
  const mes = new Date().toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });
  const cards = [
    { rotulo: 'Unidades Ativas', valor: r.unidades_ativas, sub: 'Total cadastrado' },
    { rotulo: 'Sem Código CNES', valor: r.sem_codigo_cnes, sub: 'Requerem atenção', alerta: r.sem_codigo_cnes > 0 },
    { rotulo: 'Solicitações Pendentes', valor: r.solicitacoes_pendentes, sub: 'Aguardando análise', alerta: r.solicitacoes_pendentes > 0 },
    { rotulo: 'Atualizadas este mês', valor: r.atualizadas_no_mes, sub: mes.charAt(0).toUpperCase() + mes.slice(1) },
  ];
  $('#stats').innerHTML = cards
    .map(
      (c) => `<div class="stat ${c.alerta ? 'alerta' : ''}">
        <div><div class="valor">${c.valor}</div><div class="rotulo">${esc(c.rotulo)}</div><div class="sub">${esc(c.sub)}</div></div>
        ${c.alerta ? icon('alert') : ''}</div>`,
    )
    .join('');
}

async function carregarUnidades() {
  const meu = ++pedido;
  $('#tbody').innerHTML = '<tr><td colspan="8" class="vazio">Carregando…</td></tr>';
  let dados;
  try {
    dados = await api('/unidades', { params: { ...filtro, skip, limit: LIMITE } });
  } catch (e) {
    if (meu === pedido) $('#tbody').innerHTML = `<tr><td colspan="8" class="vazio">${esc(e.message)}</td></tr>`;
    return;
  }
  if (meu !== pedido) return; // chegou uma resposta mais antiga

  $('#contagem').textContent = `${dados.itens.length} de ${dados.total} registros`;
  $('#tbody').innerHTML = dados.itens.length
    ? dados.itens
        .map(
          (u) => `<tr>
            <td class="mono muted">${esc(u.codigo)}</td>
            <td class="nome">${esc(u.nome)}</td>
            <td><span class="chip">${esc(u.tipo)}</span></td>
            <td>${esc(u.distrito_nome)}</td>
            <td class="mono">${u.codigo_cnes ? esc(u.codigo_cnes) : `<span class="warn-inline">${icon('alert')}Sem código</span>`}</td>
            <td class="center mono">${u.qtd_equipamentos}</td>
            <td class="center mono">${u.qtd_servicos}</td>
            <td>${badgeUnidade(u.status)}</td>
          </tr>`,
        )
        .join('')
    : '<tr><td colspan="8" class="vazio">Nenhum registro encontrado para os filtros aplicados.</td></tr>';
  renderPager($('#pager'), { skip, limit: LIMITE, total: dados.total }, (novo) => {
    skip = novo;
    carregarUnidades();
  });
}

// ---------- painel estatístico (GET /dashboard/estatisticas) ----------

const isoDia = (d) => d.toLocaleDateString('sv-SE'); // AAAA-MM-DD no fuso local
let distritosPorNome = {};

function definirPeriodo(dias) {
  const fim = new Date();
  const inicio = new Date();
  inicio.setDate(fim.getDate() - dias);
  $('#p-inicio').value = isoDia(inicio);
  $('#p-fim').value = isoDia(fim);
}

function cardIndicador({ rotulo, valor, sub, tendencia }) {
  let t = '';
  if (tendencia != null) {
    const classe = tendencia > 0 ? 'sobe' : tendencia < 0 ? 'desce' : '';
    t = `<div class="tendencia ${classe}">${tendencia > 0 ? '▲' : tendencia < 0 ? '▼' : '='} ${Math.abs(tendencia)}% vs período anterior</div>`;
  }
  return `<div class="stat"><div><div class="valor">${esc(valor)}</div><div class="rotulo">${esc(rotulo)}</div>
    <div class="sub">${esc(sub)}</div>${t}</div></div>`;
}

async function carregarEstatisticas() {
  let e;
  try {
    e = await api('/dashboard/estatisticas', {
      params: { inicio: $('#p-inicio').value, fim: $('#p-fim').value, distrito_id: $('#p-distrito').value },
    });
  } catch (err) {
    toast(err.message);
    return;
  }
  const i = e.indicadores;
  $('#indicadores').innerHTML = [
    { rotulo: 'Solicitações no período', valor: i.solicitacoes, sub: `${i.solicitacoes_periodo_anterior} no período anterior`, tendencia: i.variacao_pct },
    { rotulo: 'Taxa de aprovação', valor: `${i.taxa_aprovacao}%`, sub: `${i.aprovadas} aprovadas · ${i.rejeitadas} rejeitadas` },
    { rotulo: 'Tempo médio de decisão', valor: i.media_dias_decisao == null ? '—' : `${i.media_dias_decisao} dias`, sub: `${i.em_aberto} ainda em aberto` },
    { rotulo: 'Unidades com CNES', valor: `${i.pct_com_cnes}%`, sub: `${i.unidades_ativas} ativas de ${i.unidades_total}` },
  ].map(cardIndicador).join('');

  grafico($('#g-mes'), {
    type: 'line',
    data: {
      labels: e.por_mes.map((m) => rotuloMes(m.mes)),
      datasets: [
        { label: 'Criadas', data: e.por_mes.map((m) => m.criadas), borderColor: PALETA[0], backgroundColor: PALETA[0], tension: 0.3 },
        { label: 'Aprovadas', data: e.por_mes.map((m) => m.aprovadas), borderColor: COR_STATUS.APROVADA, backgroundColor: COR_STATUS.APROVADA, tension: 0.3 },
        { label: 'Rejeitadas', data: e.por_mes.map((m) => m.rejeitadas), borderColor: COR_STATUS.REJEITADA, backgroundColor: COR_STATUS.REJEITADA, tension: 0.3 },
      ],
    },
    options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  grafico($('#g-status'), {
    type: 'doughnut',
    data: {
      labels: e.por_status.map((s) => STATUS_SOL[s.chave] || s.chave),
      datasets: [{ data: e.por_status.map((s) => s.total), backgroundColor: e.por_status.map((s) => COR_STATUS[s.chave]) }],
    },
    options: { plugins: { legend: { position: 'right' } } },
  });

  distritosPorNome = Object.fromEntries([...$('#p-distrito').options].map((o) => [o.textContent, o.value]));
  grafico($('#g-distrito'), {
    type: 'bar',
    data: {
      labels: e.por_distrito.map((d) => d.distrito),
      datasets: [
        { label: 'Ativas', data: e.por_distrito.map((d) => d.ativas), backgroundColor: COR_STATUS.APROVADA },
        { label: 'Inativas', data: e.por_distrito.map((d) => d.inativas), backgroundColor: COR_STATUS.CANCELADA },
      ],
    },
    options: {
      scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } },
      onClick: (_ev, itens, chart) => {
        if (!itens.length) return;
        const nome = chart.data.labels[itens[0].index];
        const atual = $('#p-distrito').value;
        $('#p-distrito').value = atual === distritosPorNome[nome] ? '' : distritosPorNome[nome] ?? '';
        carregarEstatisticas();
      },
    },
  });

  grafico($('#g-tipo'), {
    type: 'bar',
    data: {
      labels: e.por_tipo.map((t) => TIPO_SOL[t.chave] || t.chave),
      datasets: [{ label: 'Solicitações', data: e.por_tipo.map((t) => t.total), backgroundColor: PALETA }],
    },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });

  grafico($('#g-gestor'), {
    type: 'bar',
    data: {
      labels: e.gestores.map((g) => g.gestor),
      datasets: ['aprovadas', 'devolvidas', 'rejeitadas'].map((k) => ({
        label: k[0].toUpperCase() + k.slice(1),
        data: e.gestores.map((g) => g[k]),
        backgroundColor: COR_STATUS[k.slice(0, -1).toUpperCase()],
      })),
    },
    options: { indexAxis: 'y', scales: { x: { stacked: true, ticks: { precision: 0 } }, y: { stacked: true } } },
  });

  grafico($('#g-cnes'), {
    type: 'radar',
    data: {
      labels: e.por_distrito.map((d) => d.distrito.replace('Distrito Sanitário ', 'DS ')),
      datasets: [{ label: '% com CNES', data: e.por_distrito.map((d) => d.pct_com_cnes), borderColor: PALETA[0], backgroundColor: 'rgba(37,99,235,.2)' }],
    },
    options: { scales: { r: { min: 0, max: 100 } } },
  });
}

['#p-inicio', '#p-fim', '#p-distrito'].forEach((s) => ($(s).onchange = () => { $('#p-atalho').value = ''; carregarEstatisticas(); }));
$('#p-atalho').onchange = (ev) => {
  if (!ev.target.value) return;
  definirPeriodo(Number(ev.target.value));
  carregarEstatisticas();
};

function refiltrar() {
  skip = 0;
  carregarUnidades();
}

$('#f-tipo').insertAdjacentHTML('beforeend', TIPOS_UNIDADE.map((t) => `<option>${esc(t)}</option>`).join(''));
$('#f-busca').oninput = debounce((e) => { filtro.q = e.target.value; refiltrar(); });
$('#f-distrito').onchange = (e) => { filtro.distrito_id = e.target.value; refiltrar(); };
$('#f-tipo').onchange = (e) => { filtro.tipo = e.target.value; refiltrar(); };
$('#f-status').onchange = (e) => { filtro.status = e.target.value; refiltrar(); };
$('#limpar').onclick = () => {
  Object.assign(filtro, { q: '', distrito_id: '', tipo: '', status: '' });
  $('#f-busca').value = '';
  ['#f-distrito', '#f-tipo', '#f-status'].forEach((s) => ($(s).value = ''));
  refiltrar();
};

try {
  const distritos = await api('/distritos');
  const opcoes = distritos.map((d) => `<option value="${d.id}">${esc(d.nome)}</option>`).join('');
  $('#f-distrito').insertAdjacentHTML('beforeend', opcoes);
  $('#p-distrito').insertAdjacentHTML('beforeend', opcoes);
  definirPeriodo(365);
  $('#p-atalho').value = '365';
  await Promise.all([carregarResumo(), carregarEstatisticas(), carregarUnidades()]);
} catch (e) {
  toast(e.message);
}
