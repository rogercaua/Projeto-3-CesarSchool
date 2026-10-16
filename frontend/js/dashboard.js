import { api } from './api.js';
import { icon } from './icons.js';
import { iniciarPagina, temPapel } from './layout.js';
import { $, TIPOS_UNIDADE, badgeUnidade, debounce, esc, renderPager, toast } from './util.js';

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
  $('#f-distrito').insertAdjacentHTML('beforeend', distritos.map((d) => `<option value="${d.id}">${esc(d.nome)}</option>`).join(''));
  await Promise.all([carregarResumo(), carregarUnidades()]);
} catch (e) {
  toast(e.message);
}
