import { API_BASE } from './config.js';

const TOKEN_KEY = 'govcad.token';

export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const salvarToken = (token) => sessionStorage.setItem(TOKEN_KEY, token);

export function sair() {
  sessionStorage.removeItem(TOKEN_KEY);
  location.href = 'index.html';
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function mensagemDeErro(corpo, status) {
  const d = corpo?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) {
    return d.map((e) => `${(e.loc || []).filter((p) => p !== 'body').join('.')}: ${e.msg}`).join(' · ');
  }
  return `Erro ${status}`;
}

/** Chamada à API com o token Bearer. Lança ApiError em respostas de erro. */
export async function api(caminho, { method = 'GET', body, params } = {}) {
  const url = new URL(API_BASE + caminho, location.href);
  for (const [chave, valor] of Object.entries(params || {})) {
    if (valor !== '' && valor != null) url.searchParams.set(chave, valor);
  }

  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  let resposta;
  try {
    resposta = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'Não foi possível conectar ao servidor.');
  }

  if (resposta.status === 401 && token) {
    sair();
    throw new ApiError(401, 'Sessão expirada. Entre novamente.');
  }
  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) throw new ApiError(resposta.status, mensagemDeErro(corpo, resposta.status));
  return corpo;
}
