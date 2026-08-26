# Rastreador de Editais

Vigia automaticamente as paginas de editais e avisa **por e-mail** quando aparece
algo novo:

- **Mestrado / pos-graduacao** na UFG e na UnB (e outras federais do DF, se voce ligar);
- **Concursos publicos para formados em Direito** (tribunais, MP, defensorias, procuradorias).

Roda sozinho no GitHub Actions tres vezes por dia. Nao precisa deixar nada ligado
no seu computador.

---

## Como funciona

1. Baixa cada pagina/feed listado em [`fontes.yml`](fontes.yml).
2. Extrai **todos os links** da pagina — de proposito, sem depender do layout do
   site, que muda com frequencia.
3. Mantem so os links cujo texto casa com as palavras-chave da categoria
   (`edital`, `processo seletivo`, `mestrado`... / `direito`, `procurador`,
   `analista judiciario`...), descartando ruido (`resultado final`, `gabarito`,
   `apostila`...).
4. Compara com o historico em `estado/vistos.json`. **So o que e inedito vira e-mail.**
5. Envia um e-mail agrupado por categoria e grava o novo estado no repositorio.

Se uma fonte cair, as outras continuam funcionando: o erro e registrado no log e
a execucao segue.

---

## Configuracao (uma vez so)

### 1. Criar uma senha de aplicativo do Gmail

O Gmail nao aceita a sua senha normal em programas. Voce precisa de uma
**senha de app** (16 letras):

1. Ative a verificacao em duas etapas na conta Google.
2. Acesse <https://myaccount.google.com/apppasswords>.
3. Crie uma senha chamada, por exemplo, `rastreador-editais`.
4. Guarde as 16 letras — elas so aparecem uma vez.

Usa outro provedor? Basta ajustar `SMTP_SERVIDOR` e `SMTP_PORTA`.

### 2. Cadastrar os segredos no GitHub

No repositorio: **Settings -> Secrets and variables -> Actions -> New repository secret**.

| Segredo | Obrigatorio | Exemplo | Para que serve |
|---|---|---|---|
| `SMTP_USUARIO` | sim | `seuemail@gmail.com` | conta que envia |
| `SMTP_SENHA` | sim | a senha de app de 16 letras | autenticacao |
| `EMAIL_DESTINO` | sim | `seuemail@gmail.com` | quem recebe (varios, separados por virgula) |
| `SMTP_SERVIDOR` | nao | `smtp.gmail.com` (padrao) | outro provedor |
| `SMTP_PORTA` | nao | `465` (padrao, SSL) — use `587` para STARTTLS | outro provedor |
| `EMAIL_REMETENTE` | nao | igual ao `SMTP_USUARIO` | remetente diferente |

### 3. Criar a base inicial (importante)

Na primeira execucao, **tudo** que ja esta publicado nos sites parece novidade.
Para nao receber uma avalanche, rode uma vez em modo de inicializacao:

**Actions -> Rastrear editais -> Run workflow -> marque `inicializar` -> Run.**

Isso registra o acervo atual como "ja visto", sem mandar e-mail. A partir dai,
voce so recebe o que for realmente publicado depois.

Pronto. O rastreio automatico acontece as **09h, 15h e 21h** (horario de Brasilia).

---

## Uso local

```bash
pip install -r requirements.txt

# ver o que as fontes estao devolvendo, sem tocar no estado nem mandar e-mail
python -m rastreador.principal --testar-fontes

# rodar so mostrando no terminal
python -m rastreador.principal --sem-email --verboso

# rodar de verdade (precisa das variaveis de ambiente)
export SMTP_USUARIO=seuemail@gmail.com
export SMTP_SENHA='sua senha de app'
export EMAIL_DESTINO=seuemail@gmail.com
python -m rastreador.principal
```

`--testar-fontes` e o comando mais util para ajustar a configuracao: ele mostra,
fonte por fonte, quantos links foram lidos, quantos passaram no filtro e uma
amostra dos titulos.

---

## Ajustando o que voce acompanha

Tudo fica em [`fontes.yml`](fontes.yml).

**Adicionar uma universidade ou orgao:**

```yaml
  - nome: UFMG - Editais de pos-graduacao
    url: https://www.ufmg.br/prpg/editais/
    tipo: html          # ou "rss" para feeds
    categoria: mestrado # ou "concurso"
    ativa: true
```

**Afinar as palavras-chave** (bloco `padroes`): `qualquer` exige pelo menos um
termo, `todas` exige todos, `excluir` descarta. Acentos e maiusculas nao importam.

**Filtrar so uma area** — por exemplo, mestrado em Direito:

```yaml
  - nome: UFG - PRPG
    url: https://prpg.ufg.br/
    tipo: html
    categoria: mestrado
    filtros:
      todas: [direito]
      qualquer: [edital, processo seletivo, selecao]
      excluir: [resultado final]
```

Recebendo demais? Aperte os filtros ou desligue a fonte com `ativa: false`.
Recebendo de menos? Rode `--testar-fontes` para ver se a fonte responde e se as
palavras-chave batem com os titulos reais daquele site.

---

## Estrutura

```
fontes.yml                     fontes e palavras-chave (e o que voce edita)
estado/vistos.json             historico do que ja foi avisado
rastreador/
  principal.py                 linha de comando e orquestracao
  coletor.py                   download e extracao de links (HTML e RSS)
  filtro.py                    regras de palavras-chave
  estado.py                    memoria anti-duplicata
  notificacao.py               montagem e envio do e-mail
  texto.py                     normalizacao (acentos/maiusculas)
tests/                         testes offline, com paginas de exemplo
.github/workflows/             agendamento e testes
```

---

## Observacoes

- As URLs em `fontes.yml` sao os pontos de entrada oficiais conhecidos, mas
  paginas institucionais mudam de endereco. Rode `--testar-fontes` de vez em
  quando; qualquer fonte que responda com erro aparece marcada como `[ERRO]`.
- Se o envio de e-mail falhar, os itens **nao** sao marcados como vistos: a
  proxima execucao tenta avisar de novo.
- O aviso e automatico e serve como alerta. Confirme sempre prazos e requisitos
  na pagina oficial antes de se inscrever.
