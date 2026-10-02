@echo off
rem Chamado pelo Agendador de Tarefas. Ajuste ODBC_DSN se o nome do seu DSN for outro.
set ODBC_DSN=Databricks
set ARQUIVO_XLSX=C:\Users\GabrielLuizdaSilvaCh\OneDrive - RAFATELLA\BCJ - 08 - Escritório de Processos - 08 - Escritório de Processos\03 - Indicadores\03 - Status Report CEO\Report BCJ e Adquirencia\Report Transacional ADQ.xlsx
cd /d "%~dp0.."
python -m adquirencia >> "%~dp0execucao.log" 2>&1
