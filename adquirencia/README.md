# Report Transacional ADQ - aba "Adquirencia" (execucao local)

Roda na sua maquina: consulta o Databricks pelo ODBC e atualiza a aba **Adquirencia** do
`Report Transacional ADQ.xlsx` direto na pasta sincronizada do OneDrive (o OneDrive sobe o arquivo).
As demais abas nao sao tocadas.

## Como funciona
- `consulta.sql` devolve 1 linha por dia (`data`, `faturamento`, `qtd_transacoes`) dos ultimos
  `JANELA_DIAS` (padrao 7), o que corrige cargas atrasadas.
- A data e a chave: reexecutar nao duplica, so corrige o dia. Dias antigos permanecem (historico).
- Ticket Medio, Faturamento Semana (ISO, seg-dom), Maior Ticket Medio e Maior Faturamento Semanal
  sao recalculados do historico inteiro a cada execucao.
- Consulta vazia = nada e gravado. Planilha aberta no Excel = erro claro, sem corromper.

## Instalacao (uma vez)
1. Python 3.11+ e, na pasta do projeto: `pip install -r adquirencia\requirements.txt`
2. Confirme o nome do DSN (Fontes de Dados ODBC 64 bits) e ajuste `ODBC_DSN` no `rodar_adquirencia.bat`.
3. Mapeie os dados: `python -m adquirencia.inventario_odbc --dsn NOME --catalogo gold --schema adquirencia --mascarar`
   e me envie `inventario_colunas.csv` / `inventario_amostras.csv`.
4. Edite `consulta.sql` com a tabela e filtros reais.
5. Teste: `adquirencia\rodar_adquirencia.bat` e veja `adquirencia\execucao.log`.
6. Agende (o PC precisa estar ligado e logado as 09h):
   `schtasks /Create /TN "Report ADQ" /TR "\"C:\caminho\Editais_IA\adquirencia\rodar_adquirencia.bat\"" /SC DAILY /ST 09:00`
   Em *Configuracoes* da tarefa marque "Executar assim que possivel apos um inicio agendado perdido".
