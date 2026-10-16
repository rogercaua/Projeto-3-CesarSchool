import { api } from './api.js';
import { icon } from './icons.js';
import { iniciarPagina, temPapel } from './layout.js';
import { $, badgeSolicitacao, chipTipo, codigoUnidade, esc, fmtData, fmtDataHora, TIPO_SOL, toast } from './util.js';

const usuario = await iniciarPagina('pendencias', { papeis: ['EDITOR_TECNICO', 'GESTOR_INFO', 'ADMIN'] });
const id = new URLSearchParams(location.search).get('id');
const conteudo = $('#conteudo');

const CAMPOS = {
  nome: 'Nome',
  tipo: 'Tipo de Unidade',
  codigo_cnes: 'Código CNES',
  distrito_id: 'Distrito',
  status: 'Status',
  latitude: 'Latitude',
  longitude: 'Longitude',
  qtd_equipamentos: 'Qtd. Equipamentos',
  qtd_servicos: 'Qtd. Serviços',
};

const RESULTADOS = {
  APROVADA: { titulo: 'Confirmar Aprovação', sub: 'A base oficial será atualizada após confirmação.', cor: 'green', botao: 'Aprovar Solicitação', icone: 'check',
    exemplo: 'Ex: Dados conferidos com documentação oficial. CNES validado no DATASUS.' },
  DEVOLVIDA: { titulo: 'Devolver para Correção', sub: 'A solicitação volta ao solicitante, que poderá corrigir e reenviar.', cor: 'amber', botao: 'Devolver Solicitação', icone: 'undo',
    exemplo: 'Ex: Falta comprovante do novo endereço. Anexe o documento e reenvie.' },
  REJEITADA: { titulo: 'Confirmar Rejeição', sub: 'A solicitação será recusada e encerrada.', cor: 'red', botao: 'Rejeitar Solicitação', icone: 'x',
    exemplo: 'Ex: Código CNES informado não consta na base DATASUS.' },
};

const MENSAGEM_FINAL = {
  APROVADA: ['green', 'check', 'Solicitação Aprovada', 'A base oficial foi atualizada e o log de auditoria foi gerado.'],
  DEVOLVIDA: ['amber', 'undo', 'Solicitação Devolvida', 'A solicitação voltou ao solicitante para correção e novo envio.'],
  REJEITADA: ['red', 'x', 'Solicitação Rejeitada', 'A recusa foi registrada no histórico e na trilha de auditoria.'],
};

const distritos = Object.fromEntries((await api('/distritos').catch(() => [])).map((d) => [d.id, d.nome]));

function exibir(campo, valor) {
  if (valor === null || valor === undefined || valor === '') {
    return `<span class="vazio-i">${campo === 'codigo_cnes' ? '(sem código)' : '(vazio)'}</span>`;
  }
  if (campo === 'distrito_id') return esc(distritos[valor] ?? `#${valor}`);
  if (campo === 'status') return esc(String(valor).charAt(0) + String(valor).slice(1).toLowerCase());
  return esc(valor);
}

function linhasComparativo(s) {
  if (s.tipo === 'INATIVACAO') return [{ campo: 'status', de: s.dados_atuais?.status ?? 'ATIVO', para: 'INATIVO' }];
  return Object.entries(s.dados_propostos || {}).map(([campo, para]) => ({ campo, de: s.dados_atuais?.[campo], para }));
}

function eventosHistorico(s) {
  const eventos = [{ quando: s.criada_em, quem: s.solicitante_nome, texto: `Solicitação criada (${TIPO_SOL[s.tipo]})` }];
  for (const d of s.decisoes) {
    const rotulo = { APROVADA: 'Aprovada', DEVOLVIDA: 'Devolvida para correção', REJEITADA: 'Rejeitada' }[d.resultado];
    eventos.push({ quando: d.decidida_em, quem: d.gestor_nome, texto: `${rotulo}. Justificativa: ${d.justificativa}` });
  }
  if (s.status === 'PENDENTE' && s.decisoes.length) {
    eventos.push({ quando: s.atualizada_em, quem: s.solicitante_nome, texto: 'Solicitação reenviada após correção' });
  }
  return eventos.sort((a, b) => new Date(a.quando) - new Date(b.quando));
}

function renderizar(s) {
  const ehGestor = temPapel(usuario, 'GESTOR_INFO');
  const ehDono = temPapel(usuario, 'EDITOR_TECNICO') && s.solicitante_id === usuario.id;
  const ultima = s.decisoes[s.decisoes.length - 1];

  $('#status').innerHTML = badgeSolicitacao(s.status);
  $('#protocolo').textContent = `Protocolo ${s.protocolo}`;

  const linhas = linhasComparativo(s);
  const nomeUnidade = s.unidade_nome ?? '—';
  const codigo = s.unidade_id ? ` (${codigoUnidade(s.unidade_id)})` : '';

  let acoes = '';
  if (ehGestor && s.status === 'PENDENTE') {
    acoes = `<div class="actions-row">
      <button type="button" class="btn btn-green" data-decisao="APROVADA">${icon('check')}Aprovar</button>
      <button type="button" class="btn btn-amber" data-decisao="DEVOLVIDA">${icon('undo')}Devolver</button>
      <button type="button" class="btn btn-red" data-decisao="REJEITADA">${icon('x')}Rejeitar</button>
      <a class="push" href="pendencias.html">Deixar para depois</a></div>`;
  } else if (ehDono && s.status === 'DEVOLVIDA') {
    acoes = `<div class="actions-row"><a class="btn btn-primary" href="nova-solicitacao.html?reenviar=${s.id}">Corrigir e reenviar</a></div>`;
  }

  const banner = ehDono && s.status === 'DEVOLVIDA' && ultima
    ? `<div class="banner"><strong>Devolvida por ${esc(ultima.gestor_nome)}</strong>${esc(ultima.justificativa)}</div>`
    : '';

  conteudo.innerHTML = `
    ${banner}
    <div class="card meta">
      <div><div class="k">Tipo</div><div class="v">${chipTipo(s.tipo)}</div></div>
      <div><div class="k">Solicitante</div><div class="v">${esc(s.solicitante_nome)}</div></div>
      <div><div class="k">Data da Solicitação</div><div class="v mono xs">${fmtData(s.criada_em)}</div></div>
    </div>

    <div class="card pad">
      <div class="k xs muted" style="text-transform:uppercase;letter-spacing:.05em;font-weight:600;margin-bottom:6px">Justificativa do solicitante</div>
      <div class="just-text">${esc(s.justificativa)}</div>
    </div>

    <div class="card compare">
      <div class="card-head gray">
        <h3>Comparativo: Dados Atuais × Alterações Propostas</h3>
        <p class="card-sub">Unidade: <strong>${esc(nomeUnidade)}${esc(codigo)}</strong></p>
      </div>
      <div class="table-wrap"><table class="data">
        <thead><tr>
          <th style="width:25%">Campo</th>
          <th><span class="dot"></span>Dados Atuais</th>
          <th><span class="dot new"></span>Alterações Propostas</th>
        </tr></thead>
        <tbody>${linhas.length
          ? linhas.map((l) => `<tr>
              <td class="campo">${esc(CAMPOS[l.campo] ?? l.campo)}</td>
              <td class="atual">${exibir(l.campo, l.de)}</td>
              <td><span class="novo">${exibir(l.campo, l.para)}</span></td></tr>`).join('')
          : '<tr><td colspan="3" class="vazio">Sem alterações de campos.</td></tr>'}</tbody>
      </table></div>
    </div>

    <div class="history">
      <div class="history-title">${icon('fileText')}Histórico da solicitação</div>
      <ul>${eventosHistorico(s)
        .map((e) => `<li><span class="quando">${fmtDataHora(e.quando)}</span><span class="quem">${esc(e.quem)}</span><span class="oque">${esc(e.texto)}</span></li>`)
        .join('')}</ul>
    </div>
    ${acoes}`;

  conteudo.querySelectorAll('[data-decisao]').forEach((b) => {
    b.onclick = () => abrirModal(s, b.dataset.decisao);
  });
}

function telaFinal(s, resultado) {
  const [cor, nomeIcone, titulo, texto] = MENSAGEM_FINAL[resultado];
  document.getElementById('main').innerHTML = `
    <div class="center-screen"><div class="done-card">
      <div class="done-icon ${cor}">${icon(nomeIcone)}</div>
      <h2>${titulo}</h2><p>${texto}</p>
      <p class="protocolo">Protocolo: ${esc(s.protocolo)}</p>
      <a class="btn btn-primary" href="pendencias.html">Voltar à fila de pendências</a>
    </div></div>`;
}

function abrirModal(s, resultado) {
  const cfg = RESULTADOS[resultado];
  const raiz = document.createElement('div');
  raiz.className = 'modal-root';
  raiz.innerHTML = `
    <div class="modal-backdrop"></div>
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-head ${cfg.cor}"><h3>${cfg.titulo}</h3><p>${cfg.sub}</p></div>
      <div class="modal-body">
        <label class="lbl" for="m-just">Justificativa <span class="req">*</span>
          <span class="hint">(obrigatória para registro na Trilha de Auditoria)</span></label>
        <textarea id="m-just" rows="4" placeholder="${esc(cfg.exemplo)}"></textarea>
        <p class="hint-warn" id="m-hint" hidden>Justificativa deve ter ao menos 20 caracteres.</p>
        <div class="form-error" id="m-erro" hidden></div>
        <div class="modal-actions">
          <button type="button" class="btn btn-${cfg.cor}" id="m-ok" disabled>${icon(cfg.icone)}${cfg.botao}</button>
          <button type="button" class="btn btn-ghost" id="m-cancelar">Cancelar</button>
        </div>
      </div>
      <div class="modal-foot">Esta ação gerará um registro imutável na Trilha de Auditoria.</div>
    </div>`;
  document.body.appendChild(raiz);

  const fechar = () => { raiz.remove(); document.removeEventListener('keydown', aoTeclar); };
  const aoTeclar = (e) => e.key === 'Escape' && fechar();
  document.addEventListener('keydown', aoTeclar);

  const texto = raiz.querySelector('#m-just');
  const ok = raiz.querySelector('#m-ok');
  texto.focus();
  texto.oninput = () => {
    const n = texto.value.trim().length;
    ok.disabled = n < 20;
    raiz.querySelector('#m-hint').hidden = n === 0 || n >= 20;
  };
  raiz.querySelector('.modal-backdrop').onclick = fechar;
  raiz.querySelector('#m-cancelar').onclick = fechar;

  ok.onclick = async () => {
    const erro = raiz.querySelector('#m-erro');
    erro.hidden = true;
    ok.disabled = true;
    try {
      await api(`/solicitacoes/${s.id}/decisao`, { method: 'POST', body: { resultado, justificativa: texto.value.trim() } });
      fechar();
      telaFinal(s, resultado);
    } catch (e) {
      erro.textContent = e.message;
      erro.hidden = false;
      ok.disabled = false;
    }
  };
}

try {
  if (!id) throw new Error('Solicitação não informada.');
  renderizar(await api(`/solicitacoes/${encodeURIComponent(id)}`));
} catch (e) {
  conteudo.innerHTML = `<div class="page-error">${esc(e.message)}<p style="margin-top:12px"><a class="link-acao" href="pendencias.html">Voltar à lista</a></p></div>`;
  toast(e.message);
}
