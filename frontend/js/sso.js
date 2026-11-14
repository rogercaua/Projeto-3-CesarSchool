// Login pelo SSO do Keycloak (OIDC Authorization Code + PKCE), sem biblioteca.
// A senha é digitada só na página do Keycloak; o front recebe os tokens e guarda na sessão do navegador.
import { salvarToken } from './api.js';

const SESSAO_SSO = 'govcad.sso'; // { issuer, client_id, refresh_token, id_token }
const PEDIDO = 'govcad.sso.pedido'; // { state, verifier } enquanto o usuário está no Keycloak

const endpoint = (issuer, nome) => `${issuer}/protocol/openid-connect/${nome}`;
const voltaPara = () => `${location.origin}${location.pathname}`; // a própria página de login

function base64url(bytes) {
  return btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
const aleatorio = () => base64url(crypto.getRandomValues(new Uint8Array(32)));

/** code_challenge do PKCE: base64url(SHA-256(verifier)). */
export async function desafioPkce(verifier) {
  return base64url(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)));
}

function lerSessao() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSAO_SSO));
  } catch {
    return null;
  }
}

async function pedirTokens(issuer, corpo) {
  const r = await fetch(endpoint(issuer, 'token'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(corpo),
  });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(dados.error_description || dados.error || `Erro ${r.status} no Keycloak`);
  return dados;
}

function guardar(cfg, tokens) {
  salvarToken(tokens.access_token);
  sessionStorage.setItem(SESSAO_SSO, JSON.stringify({
    issuer: cfg.issuer,
    client_id: cfg.client_id,
    refresh_token: tokens.refresh_token,
    id_token: tokens.id_token ?? lerSessao()?.id_token,
  }));
}

/** Leva o usuário à tela de login do Keycloak. */
export async function entrarSSO(cfg) {
  const state = aleatorio();
  const verifier = aleatorio();
  sessionStorage.setItem(PEDIDO, JSON.stringify({ state, verifier }));
  const url = new URL(endpoint(cfg.issuer, 'auth'));
  url.search = new URLSearchParams({
    client_id: cfg.client_id,
    redirect_uri: voltaPara(),
    response_type: 'code',
    scope: 'openid',
    state,
    code_challenge: await desafioPkce(verifier),
    code_challenge_method: 'S256',
  });
  location.assign(url);
}

/**
 * Na volta do Keycloak (?code=...&state=...), troca o código pelos tokens.
 * Devolve true se entrou, false se a página não é uma volta do SSO. Lança erro se o retorno for inválido.
 */
export async function concluirSSO(cfg) {
  const params = new URLSearchParams(location.search);
  if (!params.has('code') && !params.has('error')) return false;
  history.replaceState(null, '', voltaPara()); // tira o código da barra de endereço
  const pedido = JSON.parse(sessionStorage.getItem(PEDIDO) || 'null');
  sessionStorage.removeItem(PEDIDO);

  if (params.has('error')) throw new Error(params.get('error_description') || 'Login cancelado no Keycloak.');
  if (!pedido || params.get('state') !== pedido.state) throw new Error('Retorno do SSO inválido. Tente entrar de novo.');

  guardar(cfg, await pedirTokens(cfg.issuer, {
    grant_type: 'authorization_code',
    code: params.get('code'),
    redirect_uri: voltaPara(),
    client_id: cfg.client_id,
    code_verifier: pedido.verifier,
  }));
  return true;
}

let renovando = null;

/** Troca o refresh token por um access token novo. Devolve false se não houver sessão SSO ou se ela expirou. */
export function renovarToken() {
  const s = lerSessao();
  if (!s?.refresh_token) return Promise.resolve(false);
  renovando ??= pedirTokens(s.issuer, { grant_type: 'refresh_token', refresh_token: s.refresh_token, client_id: s.client_id })
    .then((tokens) => (guardar(s, tokens), true))
    .catch(() => false)
    .finally(() => (renovando = null)); // várias chamadas com 401 ao mesmo tempo esperam a mesma renovação
  return renovando;
}

/** URL que encerra a sessão no Keycloak e volta ao login; null no modo dev. Limpa a sessão SSO local. */
export function urlSaidaSSO() {
  const s = lerSessao();
  sessionStorage.removeItem(SESSAO_SSO);
  if (!s) return null;
  const url = new URL(endpoint(s.issuer, 'logout'));
  url.search = new URLSearchParams({
    client_id: s.client_id,
    post_logout_redirect_uri: `${location.origin}${location.pathname.replace(/[^/]*$/, '')}index.html`,
    ...(s.id_token ? { id_token_hint: s.id_token } : {}),
  });
  return url.href;
}
