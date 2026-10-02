-- Consulta do Databricks que alimenta a aba "Adquirencia".
-- Deve devolver UMA linha por dia, com exatamente estas colunas:
--   data            (DATE)
--   faturamento     (DECIMAL/DOUBLE)  soma do valor transacionado no dia
--   qtd_transacoes  (BIGINT)          quantidade de transacoes no dia
-- O parametro :dias e a janela de reprocessamento (ultimos N dias, incluindo hoje).
-- TROQUE a tabela e os filtros abaixo pelos reais.
SELECT
  CAST(data_transacao AS DATE) AS data,
  SUM(valor)                   AS faturamento,
  COUNT(*)                     AS qtd_transacoes
FROM catalogo.schema.transacoes_adquirencia   -- TODO: tabela real
WHERE CAST(data_transacao AS DATE) >= date_sub(current_date(), :dias - 1)
  AND CAST(data_transacao AS DATE) <= current_date()
  -- AND status = 'APROVADA'                  -- TODO: filtros de negocio
GROUP BY 1
ORDER BY 1
