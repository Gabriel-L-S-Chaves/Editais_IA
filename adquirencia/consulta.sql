-- Totais diarios de vendas aprovadas (silver.adquirencia.vendas_dock).
-- Devolve UMA linha por dia: data, faturamento, qtd_transacoes.
-- :dias = janela de reprocessamento (ultimos N dias fechados, ate ontem).
--  * dedup por transacao_id: vale a versao mais recente da transacao
--  * status aprovado apos o dedup: venda depois revertida deixa de contar
--  * hoje fica de fora (dia incompleto distorceria ticket medio e recordes)
SELECT
  data,
  SUM(valor) AS faturamento,
  COUNT(*)   AS qtd_transacoes
FROM (
  SELECT
    data,
    valor,
    status_transacao,
    ROW_NUMBER() OVER (
      PARTITION BY transacao_id
      ORDER BY data_hora_atualizacao DESC
    ) AS rn
  FROM silver.adquirencia.vendas_dock
  WHERE data >= date_sub(current_date(), :dias)
    AND data <  current_date()
) t
WHERE rn = 1
  AND status_transacao = 'aprovado'
GROUP BY data
ORDER BY data
