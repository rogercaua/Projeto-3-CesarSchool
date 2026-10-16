import { api } from './api.js';
import { icon } from './icons.js';
import { iniciarPagina } from './layout.js';
import { $, badge, codigoUnidade, esc, toast } from './util.js';

await iniciarPagina('conciliacao', { papeis: ['GESTOR_INFO', 'ADMIN'] });

const TIPO_DIVERGENCIA = {
  SEM_CODIGO_CNES: 'Unidade sem CNES na base municipal',
  NAO_ENCONTRADO_NO_CNES: 'Código não encontrado no CNES',
  CAMPO_DIVERGENTE: 'Campo diverge do CNES',
};
const NOME_CAMPO = { nome: 'Nome', tipo: 'Tipo' };

try {
  const [divergencias, ativas] = await Promise.all([
    api('/cnes/conciliacao'),
    api('/unidades', { params: { status: 'ATIVO', limit: 200 } }),
  ]);

  const porId = Object.fromEntries(ativas.itens.map((u) => [u.id, u]));
  const comProblema = new Set(divergencias.map((d) => d.unidade_id));
  const conformes = ativas.itens.filter((u) => u.codigo_cnes && !comProblema.has(u.id));

  $('#atualizado').textContent = `Consulta feita às ${new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;

  const cards = [
    { rotulo: 'Total comparado', valor: ativas.total, classe: '' },
    { rotulo: 'Conformes', valor: ativas.total - comProblema.size, classe: 'ok' },
    { rotulo: 'Unidades com divergências', valor: comProblema.size, classe: 'bad', alerta: comProblema.size > 0 },
  ];
  $('#resumo').innerHTML = cards
    .map(
      (c) => `<div class="stat row ${c.classe}"><div class="valor">${c.valor}</div>
        <div><div class="rotulo">${esc(c.rotulo)}</div>${c.alerta ? '<div class="sub" style="color:#ef4444">Requer análise</div>' : ''}</div></div>`,
    )
    .join('');

  $('#divergencias').innerHTML = divergencias.length
    ? `<div class="card alert-border">
        <div class="card-head red">${icon('alert')}<h3>Alertas de Divergência (${divergencias.length})</h3></div>
        <div class="table-wrap"><table class="data red">
          <thead><tr><th>ID</th><th>Unidade</th><th>CNES Municipal</th><th>Tipo de Divergência</th><th>Detalhe</th></tr></thead>
          <tbody>${divergencias
            .map((d) => {
              const cnes = porId[d.unidade_id]?.codigo_cnes;
              const detalhe =
                d.divergencia === 'CAMPO_DIVERGENTE'
                  ? `${esc(NOME_CAMPO[d.campo] ?? d.campo)}: <span class="mono xs">${esc(d.valor_local)}</span> → <span class="mono xs">${esc(d.valor_cnes)}</span>`
                  : '<span class="muted">—</span>';
              return `<tr>
                <td class="mono muted">${codigoUnidade(d.unidade_id)}</td>
                <td class="nome">${esc(d.unidade_nome)}</td>
                <td class="mono">${cnes ? esc(cnes) : '<span style="color:#d97706">(sem código)</span>'}</td>
                <td><span class="chip-red">${esc(TIPO_DIVERGENCIA[d.divergencia] ?? d.divergencia)}</span></td>
                <td>${detalhe}</td></tr>`;
            })
            .join('')}</tbody>
        </table></div></div>`
    : '';

  $('#titulo-conformes').textContent = `Registros Conformes (${conformes.length})`;
  $('#conformes').innerHTML = conformes.length
    ? conformes
        .map(
          (u) => `<tr><td class="mono muted">${esc(u.codigo)}</td><td>${esc(u.nome)}</td>
            <td class="mono">${esc(u.codigo_cnes)}</td><td class="mono">${esc(u.codigo_cnes)}</td>
            <td>${badge('conforme', 'Conforme')}</td></tr>`,
        )
        .join('')
    : '<tr><td colspan="5" class="vazio">Nenhuma unidade conforme.</td></tr>';
} catch (e) {
  toast(e.message);
  $('#conformes').innerHTML = `<tr><td colspan="5" class="vazio">${esc(e.message)}</td></tr>`;
}
