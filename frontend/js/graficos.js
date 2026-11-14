// Gráficos com Chart.js (carregado por <script> na página, expõe window.Chart).

export const COR_STATUS = {
  PENDENTE: '#f59e0b', DEVOLVIDA: '#ea580c', APROVADA: '#16a34a', REJEITADA: '#dc2626', CANCELADA: '#94a3b8',
};
export const PALETA = ['#2563eb', '#16a34a', '#dc2626', '#f59e0b', '#7e22ce', '#0891b2', '#64748b', '#db2777'];

const ativos = new Map();

/** Cria (ou recria) o gráfico no canvas. Sem Chart.js (ex.: sem internet), mostra um aviso no lugar. */
export function grafico(canvas, config) {
  ativos.get(canvas)?.destroy();
  if (!window.Chart) {
    canvas.parentElement.innerHTML = '<p class="loading">Gráfico indisponível: não foi possível carregar o Chart.js.</p>';
    return null;
  }
  const g = new window.Chart(canvas, {
    ...config,
    options: { responsive: true, maintainAspectRatio: false, ...config.options },
  });
  ativos.set(canvas, g);
  return g;
}

/** "2026-03" -> "mar/26" */
export const rotuloMes = (mes) => {
  const [a, m] = mes.split('-');
  return `${new Date(a, m - 1).toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '')}/${a.slice(2)}`;
};
