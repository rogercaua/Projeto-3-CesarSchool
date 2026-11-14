import { icon } from './icons.js';

export const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
export const $$ = (seletor, raiz = document) => [...raiz.querySelectorAll(seletor)];

/** Escapa texto antes de inserir em innerHTML (evita XSS com dados vindos da API). */
export const esc = (valor) =>
  String(valor ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

export function debounce(fn, ms = 300) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

// O backend devolve datas em UTC; o SQLite as envia sem fuso, então assumimos UTC.
const parseData = (iso) => new Date(/[zZ]$|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
export const fmtData = (iso) => (iso ? parseData(iso).toLocaleDateString('pt-BR') : '');
export const fmtDataHora = (iso) =>
  iso ? parseData(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '';

export const codigoUnidade = (id) => `U${String(id).padStart(3, '0')}`;

export const TIPO_SOL = { INCLUSAO: 'Inclusão', ALTERACAO: 'Alteração', INATIVACAO: 'Inativação', REATIVACAO: 'Reativação' };
export const STATUS_SOL = { PENDENTE: 'Pendente', DEVOLVIDA: 'Devolvida', APROVADA: 'Aprovada', REJEITADA: 'Rejeitada', CANCELADA: 'Cancelada' };
export const STATUS_UNIDADE = { ATIVO: 'Ativo', INATIVO: 'Inativo' };
export const TIPOS_UNIDADE = ['UBS', 'AMA', 'CMS', 'CEU AS', 'CRS', 'AMA/UBS'];

export const badge = (classe, texto) => `<span class="badge badge-${classe}">${esc(texto)}</span>`;
export const badgeSolicitacao = (s) => badge(s.toLowerCase(), STATUS_SOL[s] || s);
export const badgeUnidade = (s) => badge(s.toLowerCase(), STATUS_UNIDADE[s] || s);
export const chipTipo = (t) => `<span class="chip-tipo ${t.toLowerCase()}">${esc(TIPO_SOL[t] || t)}</span>`;

export function toast(mensagem, tipo = 'erro') {
  let raiz = document.getElementById('toast-root');
  if (!raiz) {
    raiz = document.createElement('div');
    raiz.id = 'toast-root';
    document.body.appendChild(raiz);
  }
  const el = document.createElement('div');
  el.className = `toast ${tipo}`;
  el.textContent = mensagem;
  raiz.appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

/** Paginação "Anterior  1 / N  Próximo". onPagina recebe o novo skip. */
export function renderPager(el, { skip, limit, total }, onPagina) {
  const pagina = Math.floor(skip / limit) + 1;
  const paginas = Math.max(1, Math.ceil(total / limit));
  el.innerHTML = `
    <button type="button" data-d="-1" ${pagina <= 1 ? 'disabled' : ''}>Anterior</button>
    <span class="mono xs muted">${pagina} / ${paginas}</span>
    <button type="button" data-d="1" ${pagina >= paginas ? 'disabled' : ''}>Próximo</button>`;
  el.querySelectorAll('button').forEach((b) => {
    b.onclick = () => onPagina(Math.max(0, skip + Number(b.dataset.d) * limit));
  });
}

/** Janela de confirmação. `confirmar` faz a chamada à API; se falhar, o erro aparece na própria janela.
 *  `depois` roda após o sucesso (ex.: recarregar a lista). */
export function abrirModal({ cor, titulo, sub, botao, nomeIcone, corpo = '', confirmar, depois }) {
  const raiz = document.createElement('div');
  raiz.className = 'modal-root';
  raiz.innerHTML = `
    <div class="modal-backdrop"></div>
    <form class="modal" role="dialog" aria-modal="true" autocomplete="off">
      <div class="modal-head ${cor}"><h3>${esc(titulo)}</h3><p>${esc(sub)}</p></div>
      <div class="modal-body">
        ${corpo}
        <div class="form-error" id="m-erro" hidden></div>
        <div class="modal-actions">
          <button type="submit" class="btn btn-${cor}" id="m-ok">${icon(nomeIcone)}${esc(botao)}</button>
          <button type="button" class="btn btn-ghost" id="m-cancelar">Cancelar</button>
        </div>
      </div>
      <div class="modal-foot">Esta ação gerará um registro imutável na Trilha de Auditoria.</div>
    </form>`;
  document.body.appendChild(raiz);

  const fechar = () => { raiz.remove(); document.removeEventListener('keydown', aoTeclar); };
  const aoTeclar = (e) => e.key === 'Escape' && fechar();
  document.addEventListener('keydown', aoTeclar);
  raiz.querySelector('.modal-backdrop').onclick = fechar;
  raiz.querySelector('#m-cancelar').onclick = fechar;

  const ok = raiz.querySelector('#m-ok');
  raiz.querySelector('form').onsubmit = async (e) => {
    e.preventDefault();
    const erro = raiz.querySelector('#m-erro');
    erro.hidden = true;
    ok.disabled = true;
    try {
      await confirmar(raiz);
      fechar();
      await depois?.();
    } catch (err) {
      erro.textContent = err.message;
      erro.hidden = false;
      ok.disabled = false;
    }
  };
  (raiz.querySelector('input') ?? ok).focus();
}
