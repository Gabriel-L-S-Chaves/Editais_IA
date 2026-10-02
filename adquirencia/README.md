# Report Transacional ADQ — aba "Adquirencia"

Rotina diária (09h Brasília, GitHub Actions) que consulta o Databricks e atualiza
a aba **Adquirencia** do arquivo `Report Transacional ADQ.xlsx` no OneDrive.
As demais abas do arquivo não são tocadas.

## Como funciona
- A consulta (`consulta.sql`) devolve 1 linha por dia: `data`, `faturamento`, `qtd_transacoes`,
  dos últimos `JANELA_DIAS` (padrão 7) — a janela corrige cargas atrasadas.
- A **data é a chave**: reexecutar no mesmo dia não duplica, só sobrescreve o dia.
  Dias fora da janela permanecem como estão (histórico append).
- Todas as métricas são recalculadas do histórico inteiro a cada execução:
  Ticket Médio, Faturamento Semana (acum., semana ISO seg–dom), Maior Ticket Médio
  e Maior Faturamento Semanal (recordes até a data).
- Gravação otimista via eTag: se alguém salvar a planilha durante a execução, a rotina
  relê e tenta de novo (até 3x) em vez de sobrescrever.

## Configuração (uma vez)
1. Editar `consulta.sql` com a tabela e os filtros reais.
2. Registrar um app no Entra ID com permissão `Files.ReadWrite.All` (ou `Sites.ReadWrite.All`)
   e consentimento de admin.
3. Secrets do repositório: `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`,
   `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`,
   `ONEDRIVE_DRIVE_ID` (id do drive/biblioteca que contém a pasta) e
   `ONEDRIVE_CAMINHO` (caminho dentro da biblioteca, terminando em `Report Transacional ADQ.xlsx`).
   O caminho `C:\Users\...\OneDrive - ...` é o da sincronização no PC; a rotina na nuvem usa o
   caminho relativo à biblioteca.
4. Rodar uma vez em *Actions → Atualizar Report Transacional ADQ → Run workflow*.

Teste local: `python -m adquirencia --arquivo teste.xlsx` (exige as variáveis do Databricks).
