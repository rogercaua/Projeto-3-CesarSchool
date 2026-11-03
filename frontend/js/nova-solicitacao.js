import { api } from './api.js';
import { iniciarPagina } from './layout.js';
import { $, $$, TIPOS_UNIDADE, codigoUnidade, esc, toast } from './util.js';
import { icon } from './icons.js';

const reenvioId = new URLSearchParams(location.search).get('reenviar');
await iniciarPagina(reenvioId ? 'pendencias' : 'nova', { papeis: ['EDITOR_TECNICO'] });

let tipo = null;
let unidades = [];
let solicitacao = null; // preenchida no modo "corrigir e reenviar"

const unidadeSelecionada = () => unidades.find((u) => String(u.id) === $('#f-unidade').value);

// ───────── Preenchimento dos campos ─────────
function preencher(o = {}, semCnes = false) {
  $('#f-nome').value = o.nome ?? '';
  if (o.tipo && ![...$('#f-tipo').options].some((op) => op.value === o.tipo)) {
    $('#f-tipo').insertAdjacentHTML('beforeend', `<option>${esc(o.tipo)}</option>`);
  }
  $('#f-tipo').value = o.tipo ?? TIPOS_UNIDADE[0];
  if (o.distrito_id) $('#f-distrito').value = String(o.distrito_id);
  $('#f-cnes').value = o.codigo_cnes ?? '';
  $('#f-semcnes').checked = semCnes; // marcada só quando a intenção é ficar sem código
  $('#f-eq').value = o.qtd_equipamentos ?? 0;
  $('#f-serv').value = o.qtd_servicos ?? 0;
  $('#cnes-msg').hidden = true;
  atualizarSemCnes();
}

function atualizarSemCnes() {
  const marcado = $('#f-semcnes').checked;
  $('#f-cnes').disabled = marcado || tipo === 'INATIVACAO';
  $('#btn-cnes').disabled = marcado || tipo === 'INATIVACAO';
  $('#card-semcnes').classList.toggle('on', marcado);
  $('#ic-semcnes').hidden = !marcado;
}

function aplicarTipo() {
  $$('#tipos button').forEach((b) => b.classList.toggle('sel', b.dataset.tipo === tipo));
  $('#bloco-unidade').hidden = tipo === 'INCLUSAO';
  $('#bloco-qtd').hidden = tipo === 'INATIVACAO';
  const somenteLeitura = tipo === 'INATIVACAO';
  ['#f-nome', '#f-tipo', '#f-distrito', '#f-semcnes', '#f-eq', '#f-serv'].forEach((s) => ($(s).disabled = somenteLeitura));
  atualizarSemCnes();
}

function mudarTipo(novo) {
  tipo = novo;
  aplicarTipo();
  if (tipo === 'INCLUSAO') {
    preencher({});
  } else {
    const u = unidadeSelecionada();
    if (u) preencher(u);
  }
}

// ───────── Leitura e validação ─────────
function lerCampos() {
  const cnes = $('#f-cnes').value.trim();
  return {
    nome: $('#f-nome').value.trim(),
    tipo: $('#f-tipo').value,
    distrito_id: Number($('#f-distrito').value) || null,
    codigo_cnes: $('#f-semcnes').checked || !cnes ? null : cnes,
    qtd_equipamentos: Number($('#f-eq').value || 0),
    qtd_servicos: Number($('#f-serv').value || 0),
  };
}

function validar(c) {
  if (c.nome.length < 2) throw new Error('Informe o nome da unidade.');
  if (!c.tipo) throw new Error('Selecione o tipo da unidade.');
  if (!c.distrito_id) throw new Error('Selecione o distrito.');
  if (c.codigo_cnes && !/^\d{7}$/.test(c.codigo_cnes)) throw new Error('O código CNES deve ter 7 dígitos.');
  for (const q of [c.qtd_equipamentos, c.qtd_servicos]) {
    if (!Number.isInteger(q) || q < 0) throw new Error('As quantidades devem ser números inteiros iguais ou maiores que zero.');
  }
}

/** Monta dados_propostos: inclusão envia tudo; alteração envia só o que mudou. */
function montarDados(unidade) {
  if (tipo === 'INATIVACAO') return undefined;
  const c = lerCampos();
  validar(c);
  if (tipo === 'INCLUSAO') {
    const { codigo_cnes, ...resto } = c;
    return codigo_cnes ? { ...resto, codigo_cnes } : resto;
  }
  const diff = {};
  for (const [campo, valor] of Object.entries(c)) {
    if (valor !== (unidade[campo] ?? null)) diff[campo] = valor;
  }
  if (!Object.keys(diff).length) throw new Error('Altere ao menos um campo da unidade.');
  return diff;
}

function mostrarErro(msg) {
  const el = $('#erro');
  el.textContent = msg;
  el.hidden = !msg;
}

// ───────── Envio ─────────
async function enviar() {
  mostrarErro('');
  const botao = $('#enviar');
  try {
    if (!tipo) throw new Error('Selecione o tipo de solicitação.');
    const justificativa = $('#f-just').value.trim();
    if (justificativa.length < 3) throw new Error('Informe a justificativa da solicitação.');

    let unidade = null;
    if (tipo !== 'INCLUSAO') {
      unidade = unidadeSelecionada();
      if (!unidade) throw new Error('Selecione a unidade de referência.');
    }
    const dados_propostos = montarDados(unidade);

    botao.disabled = true;
    const resposta = solicitacao
      ? await api(`/solicitacoes/${solicitacao.id}`, { method: 'PUT', body: { dados_propostos, justificativa } })
      : await api('/solicitacoes', { method: 'POST', body: { tipo, unidade_id: unidade?.id ?? null, dados_propostos, justificativa } });
    telaSucesso(resposta);
  } catch (e) {
    mostrarErro(e.message);
    botao.disabled = false;
  }
}

function telaSucesso(s) {
  const reenviada = Boolean(solicitacao);
  document.getElementById('main').innerHTML = `
    <div class="center-screen"><div class="done-card">
      <div class="done-icon green">${icon('check')}</div>
      <h2>Solicitação ${reenviada ? 'reenviada' : 'enviada'}!</h2>
      <p>O pedido foi registrado com status <strong>Pendente de Aprovação</strong>.</p>
      <p class="protocolo">Protocolo: ${esc(s.protocolo)}</p>
      <a class="btn btn-primary" href="${reenviada ? 'pendencias.html' : 'dashboard.html'}">${reenviada ? 'Ver minhas solicitações' : 'Voltar ao Dashboard'}</a>
    </div></div>`;
}

// ───────── Busca no CNES ─────────
async function buscarCnes() {
  const msg = $('#cnes-msg');
  const codigo = $('#f-cnes').value.trim();
  msg.hidden = false;
  msg.className = 'field-msg';
  if (!/^\d{7}$/.test(codigo)) {
    msg.textContent = 'Informe os 7 dígitos do código CNES.';
    msg.classList.add('bad');
    return;
  }
  try {
    const r = await api(`/cnes/estabelecimentos/${codigo}`);
    msg.textContent = `Encontrado no CNES: ${r.nome} (${r.tipo}).`;
    msg.classList.add('ok');
    if (tipo === 'INCLUSAO') {
      $('#f-nome').value = r.nome;
      if ([...$('#f-tipo').options].some((o) => o.value === r.tipo)) $('#f-tipo').value = r.tipo;
    }
  } catch (e) {
    msg.textContent = e.status === 404 ? 'Código não encontrado no CNES.' : e.message;
    msg.classList.add('bad');
  }
}

// ───────── Inicialização ─────────
try {
  const [distritos, lista] = await Promise.all([api('/distritos'), api('/unidades', { params: { limit: 200 } })]);
  unidades = lista.itens;

  $('#f-tipo').innerHTML = TIPOS_UNIDADE.map((t) => `<option>${esc(t)}</option>`).join('');
  $('#f-distrito').innerHTML = distritos.length
    ? distritos.map((d) => `<option value="${d.id}">${esc(d.nome)}</option>`).join('')
    : '<option value="">Nenhum distrito cadastrado</option>';
  $('#f-unidade').insertAdjacentHTML(
    'beforeend',
    unidades.map((u) => `<option value="${u.id}">${esc(u.nome)} (${codigoUnidade(u.id)})</option>`).join(''),
  );
} catch (e) {
  toast(e.message);
}

$$('#tipos button').forEach((b) => (b.onclick = () => mudarTipo(b.dataset.tipo)));
$('#f-unidade').onchange = () => {
  const u = unidadeSelecionada();
  if (u) preencher(u);
};
$('#f-semcnes').onchange = atualizarSemCnes;
$('#btn-cnes').onclick = buscarCnes;
$('#enviar').onclick = enviar;

if (reenvioId) {
  // Modo "corrigir e reenviar": solicitação devolvida pelo gestor
  try {
    solicitacao = await api(`/solicitacoes/${encodeURIComponent(reenvioId)}`);
    if (solicitacao.status !== 'DEVOLVIDA') {
      toast('Só é possível reenviar solicitações devolvidas.');
      location.replace(`solicitacao.html?id=${solicitacao.id}`);
    }
    tipo = solicitacao.tipo;
    document.title = 'Corrigir e Reenviar · GovCadastral';
    $('#titulo').textContent = 'Corrigir e Reenviar';
    $('#subtitulo').textContent = `Protocolo ${solicitacao.protocolo}`;
    $('#voltar').href = `solicitacao.html?id=${solicitacao.id}`;
    $('#cancelar').href = `solicitacao.html?id=${solicitacao.id}`;
    $('#enviar').textContent = 'Reenviar Solicitação';

    const ultima = solicitacao.decisoes[solicitacao.decisoes.length - 1];
    if (ultima) {
      $('#devolucao').innerHTML = `<strong>Devolvida por ${esc(ultima.gestor_nome)}</strong>${esc(ultima.justificativa)}`;
      $('#devolucao').hidden = false;
    }

    const unidade = unidades.find((u) => u.id === solicitacao.unidade_id);
    if (unidade) $('#f-unidade').value = String(unidade.id);
    aplicarTipo();
    const propostos = solicitacao.dados_propostos ?? {};
    preencher({ ...(unidade ?? {}), ...propostos }, propostos.codigo_cnes === null);
    $('#f-just').value = solicitacao.justificativa;
    $$('#tipos button').forEach((b) => (b.disabled = true));
    $('#f-unidade').disabled = true;
  } catch (e) {
    mostrarErro(e.message);
    $('#enviar').disabled = true;
  }
} else {
  aplicarTipo();
}
