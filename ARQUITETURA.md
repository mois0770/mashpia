# Arquitetura do Mashpia

Referência de estado atual, organizada por programa. Não é histórico — para
o que mudou, quando e por quê (achados de calibração, bugs corrigidos,
decisões revisadas), ver `00_Estado_Atual.txt`. Este documento explica só o
que cada programa faz hoje.

## Visão geral do pipeline

```
documentos-fonte (CHAT_NIVEL_2/*.odt, *.txt)
    │
    ▼
pipeline/metadados_confirmados.py    (curadoria manual: Sefirah/Tema/Entidade/
    │                                  conceitos_estruturais por documento)
    ▼
pipeline/ingestao.py                 (texto real + chunking por parágrafo)
    │
    ▼
pipeline/gerar_corpus.py             (junta metadados + texto → corpus_confirmado.json)
    │
    ▼
pipeline/vetorizar.py                (embeddings OpenRouter → ChromaDB local)
    │
    ▼
backend/adam_kadmon.py               (classifica a pergunta: Sefirah/Entidade/Tema)
    │
    ▼
grafo/schema.py                      (expande por travessia estrutural: SINTETIZA/CANALIZA/GOVERNA)
    │
    ▼
backend/gerar_resposta.py            (monta contexto + gera resposta com o LLM)
    │
    ▼
interface/app.py  ou  backend/main.py  (Streamlit ou API HTTP)
```

Ferramentas de curadoria (`pipeline/diagnostico_dispersao.py`,
`propor_divisao.py`, `sugerir_tags.py`, `sugerir_pesos_restantes.py`) rodam
**antes** de `gerar_corpus.py`, sempre que um documento novo entra ou um
existente precisa de revisão — não fazem parte do caminho de cada pergunta
do usuário, só do processo de manter o corpus curado.

---

## `config.py`

Configuração compartilhada: caminhos (`BASE_DIR`, `DATA_DIR`, `CHROMA_DIR`) e
`get_openrouter_key()`, que tenta em ordem: variável de ambiente
`OPENROUTER_API_KEY` → `st.secrets` (Streamlit Cloud) → arquivo local
`Openrouter_Ket.txt` (nunca versionado). `EMBEDDING_MODEL` e `LLM_MODEL`
também ficam aqui — um lugar só para trocar de modelo.

## `grafo/schema.py`

Schema estrutural fixo do projeto — o "vocabulário controlado" que todo o
resto do sistema usa:

- `SEFIROT` (11), `ENTIDADES` (14), `TEMAS` (9), `CONCEITOS_ESTRUTURAIS` (3:
  Dirá BeTachtonim, Moach Sholet Al HaLev, Adon Olam) — listas canônicas,
  únicas fontes de verdade para esses nomes em todo o projeto.
- `SEFIROT_E_NOS_PONTE` — os 11 Sefirot mais `EinSof`/`AdamKadmon` (nós-ponte
  do grafo que também são valores válidos de `sefirot_define`/`expressa`).
- `construir_grafo()` monta o grafo NetworkX (nós + arestas PONTE,
  HISHTALSHELUT, MESMA_COLUNA, SINTETIZA, GOVERNA, CANALIZA) — chunks não
  entram aqui, isso é papel do pipeline. `grafo_singleton()` cacheia por
  processo.
- `expandir_por_grafo(sefirot_ativas)` — dado o conjunto de Sefirot que a
  classificação já ativou para uma pergunta, faz a travessia real: SINTETIZA
  só dispara com os dois flancos da tríade ativos; CANALIZA é sempre que a
  origem está ativa; GOVERNA só quando Daat e o alvo aparecem juntos. Usado
  por `backend/gerar_resposta.py`.

## `pipeline/` — construção do corpus

### `ingestao.py`
Extrai texto de `.odt` (via `pandoc`) ou `.txt`, e divide em chunks por
parágrafo (`chunkear_por_paragrafo`): separa por linha em branco, quebra por
linha simples qualquer bloco maior que 2000 caracteres (casos como
`Klalei.txt`, sem linha em branco real entre pontos numerados), e mescla
fragmentos curtos com o seguinte. `_id_estavel` gera um ID determinístico
(documento + posição + hash do texto) — é o que torna o pipeline idempotente
(rodar de novo não duplica).

### `metadados_confirmados.py`
**Dado, não lógica.** Lista `DOCUMENTOS`: um dict por documento-fonte, com
`pasta`, `chave` (substring única do nome de arquivo), `autoria`
(`autor_projeto`/`traducao_propria`/`fonte_externa`), `temas`,
`sefirot_define`, `sefirot_expressa`, `entidades`, `conceitos_estruturais` e
`observacoes`. Granularidade por documento inteiro — simplificação
deliberada (ver seção de limitações em `00_Estado_Atual.txt`). Todo o
conteúdo aqui vem de curadoria humana (ou de curadoria assistida por IA já
revisada), nunca gerado sem revisão.

### `gerar_corpus.py`
Combina `DOCUMENTOS` com o texto real (via `ingestao.processar_documento`) e
grava `corpus_confirmado.json`. `resolver_arquivo(pasta, chave)` localiza o
arquivo real dentro de `CHAT_NIVEL_2/<pasta>/`. Cada chunk de saída herda
todas as tags do documento — exceto `entidades`, que só é aplicada ao chunk
se o nome da entidade aparecer de fato no texto dele (para não contaminar a
etapa B do classificador com falsos positivos).

### `vetorizar.py`
Gera embeddings (`embed_lote`, em lotes de 50) e grava/atualiza a coleção
ChromaDB `mashpia_chunks`. Campos-lista viram string separada por vírgula
(ChromaDB só aceita escalar em metadado); `conceitos_estruturais` é
achatado em campos `peso_<id>` inteiros via `_pesos_conceitos`.
**Reconcilia órfãos**: depois do upsert, apaga da coleção qualquer ID que
não esteja mais no corpus atual — necessário sempre que um documento é
removido/dividido em `metadados_confirmados.py`, senão os chunks antigos
ficam presos na coleção para sempre.

### `diagnostico_dispersao.py`
**Etapa 1 de curadoria.** Para cada documento já em `DOCUMENTOS`, reconstitui
o texto completo e pede a um LLM uma lista dos tópicos reais cobertos + um
veredito de dispersão temática (`baixa`/`media`/`alta`) comparando com as
tags de documento inteiro já atribuídas. Não decide nada sozinho — produz
`diagnostico_dispersao.json` para revisão humana. Documentos "alta" são
candidatos à Etapa 2.

### `propor_divisao.py`
**Etapa 2**, só para documentos sinalizados "alta". Propõe uma partição dos
chunks (já numerados na ordem original) em grupos contíguos, cada um virando
um arquivo focado. **Fidelidade por desenho**: o LLM só decide ONDE cortar —
o texto de cada arquivo novo é montado pelo script concatenando o texto
ORIGINAL dos chunks, nunca reescrito. Validação de partição (sem gaps nem
sobreposição) é programática. Grava arquivos em
`pipeline/propostas_divisao/<slug>/` para revisão antes de mover para
`CHAT_NIVEL_2/Divididos/`.

### `sugerir_tags.py`
**Etapas 4+5**, para arquivos já em `CHAT_NIVEL_2/Divididos/`. Por arquivo,
pede ao LLM Sefirah DEFINE/EXPRESSA + Tema + Entidade (passo 4) e peso 0-5
de cada conceito estrutural (passo 5) numa única chamada. `autoria` é
herdada do documento original, não perguntada ao LLM. Grava
`sugestao_tags.json`. Ao rodar escopado a um subconjunto de pastas,
**mescla** com o relatório existente em vez de sobrescrever.

### `sugerir_pesos_restantes.py`
Mesma ideia de `sugerir_tags.py`, mas só o eixo de peso (Sefirah/Tema/
Entidade dos documentos não-divididos já existem e não são o alvo), e
granularidade por documento inteiro — consistente com como esses documentos
já são tratados, e defensável porque são documentos de dispersão média/baixa
(mais coesos). Grava `pesos_documentos_restantes.json`.

---

## `backend/` — classificação, geração, API

### `openrouter_client.py`
`post_com_retry` — toda chamada à OpenRouter do projeto passa por aqui.
Retry com backoff (1s, 2s) em timeout/desconexão/429/5xx; erro definitivo
(401, 400) falha na hora, sem retry inútil. Depois de esgotar tentativas,
levanta `ErroOpenRouter` (mensagem amigável) em vez de deixar a exceção
crua de `requests` subir. Chamadas não-streaming também registram o custo
real (`usage.cost`) no teto diário de `limites.py` automaticamente.

### `limites.py`
Proteção de custo para uso público (demo protegida) — `TETO_CUSTO_DIARIO_USD`
(padrão US$5) e `MAX_PERGUNTAS_POR_SESSAO` (padrão 10), ambas constantes
fáceis de ajustar. `verificar_teto()` levanta `TetoDeCustoAtingido` se o
gasto acumulado do dia (`data/uso_diario.json`, resetado quando a data
muda) já atingiu o teto — chamada no início de `gerar_resposta._preparar_
geracao`, antes de qualquer chamada à OpenRouter. `registrar_custo(usd)` é
chamada automaticamente por `post_com_retry` (chamadas não-streaming) e
manualmente dentro de `gerar_resposta_stream` (que precisa pedir
`"usage": {"include": true}` no request pra ter o custo disponível no
evento final do SSE). O rate limit por sessão em si vive em
`interface/app.py`/`app_1.py` (contador em `st.session_state`), não aqui.

### `adam_kadmon.py`
Classificação de 3 eixos (Sefirah/Entidade/Tema) para uma pergunta:
- **Etapa A** (`etapa_a`): busca vetorial bilíngue (a pergunta é traduzida
  para inglês via LLM e as duas versões são buscadas, porque boa parte do
  corpus está em inglês) contra ChromaDB. Candidatos de Sefirah/Entidade só
  a partir de chunks DEFINE; candidatos de Tema usam lift (contagem
  observada / frequência esperada no corpus) para não deixar Temas grandes
  (Fundamentos, Educacao) dominarem por volume.
- **Etapa B** (`etapa_b`): um LLM decide quais candidatos realmente se
  aplicam, vendo só o texto DEFINE recuperado — nunca conhecimento geral.
- Se a etapa A não encontra candidato, ou a etapa B rejeita todos, aciona
  `protocolo_lacuna=True`.
- `classificar_com_vizinhos` devolve também os vizinhos buscados, para
  `gerar_resposta.py` reaproveitar sem repetir a busca.

### `gerar_resposta.py`
O módulo que gera a resposta final — ver docstring do próprio arquivo para
o fluxo completo (classificar → expandir por grafo → montar contexto com
notas de relações estruturais e conceitos de peso alto → gerar com o
prompt fixo, ajustado pelo `NIVEIS` escolhido → retry/streaming via
`openrouter_client`).
`NIVEIS` (1=Completo, 2=Resumido, 3=Essência prática): cada nível só muda
extensão/estrutura (instrução anexada ao prompt fixo) e `max_tokens` — as
regras de conteúdo do prompt fixo valem sempre, em qualquer nível.

### `main.py`
API FastAPI: `GET /`, `GET /estatisticas`, `GET /grafo`, `POST /classificar`,
`POST /responder` (aceita `nivel` opcional). `ErroOpenRouter` vira HTTP 503
com JSON limpo via `exception_handler`, não 500 genérico.

### `feedback.py` / `feedback_sheets.py` / `ver_feedback.py`
`feedback.py`: grava feedback (avaliação + sugestão + pergunta/resposta do
turno) em `data/feedback.jsonl` (garantia local) e tenta enviar em paralelo
para uma planilha do Google via `feedback_sheets.enviar_feedback_sheets`
(POST direto ao endpoint público do Form, sem credencial). Se o Sheets
falhar por qualquer motivo, o registro local já foi gravado — nada se
perde. `feedback_sheets.py` normaliza o valor de avaliação para os literais
exatos que o Form exige (`_MAPA_AVALIACAO`) antes de enviar.
`ver_feedback.py`: script de linha de comando pra ler `feedback.jsonl` e
imprimir tudo formatado.

### `teste_calibracao.py` / `teste_calibracao_geracao.py`
Não são suítes com asserts — são ferramentas de inspeção manual. O primeiro
roda 8 perguntas fixas contra `adam_kadmon.classificar` (checa
Sefirah/Entidade/Tema/lacuna). O segundo roda 5 perguntas contra
`gerar_resposta.gerar_resposta` e imprime a resposta completa pra conferir
contra o checklist do prompt fixo (ver docstring do arquivo).

---

## `interface/`

### `app.py` (principal, deploy usa este)
Interface Streamlit com streaming (`gerar_resposta_stream` +
`st.write_stream`). Sidebar: seletor de nível de resposta (sempre visível
antes de perguntar) e formulário de feedback. `_garantir_indice()`
reconstrói o ChromaDB a partir de `corpus_confirmado.json` se ausente ou
desatualizado (necessário no Streamlit Cloud, onde `data/chroma/` não é
versionado e o container sobe do zero a cada deploy). `ErroOpenRouter` vira
`st.error()` amigável em vez da tela de traceback do Streamlit.

### `app_1.py` (variante sem streaming)
Mesma estrutura, mas usa `gerar_resposta` (não-streaming) — mantida como
alternativa mais simples, não é o arquivo principal do deploy.

---

## Convenções que atravessam o projeto

- **"IA sugere, curador confirma"**: toda classificação/tag gerada por LLM
  (Sefirah, Tema, Entidade, peso de conceito estrutural, proposta de
  divisão) é gravada em relatório separado para revisão humana antes de
  entrar em `metadados_confirmados.py`. Nenhum script escreve direto no
  arquivo de metadados definitivo.
- **Fidelidade de conteúdo**: nenhuma etapa do sistema (classificação,
  geração, curadoria) usa conhecimento geral do modelo para afirmar
  conteúdo doutrinário — só o que está nos trechos/documentos fornecidos.
  Onde isso é regra do prompt fixo (geração), está explícito no próprio
  prompt; onde é regra de ferramenta de curadoria (ex.: `propor_divisao.py`
  nunca reescreve texto), está documentado no docstring do script.
- **Retry consciente de causa**: erro definitivo (ex.: chave inválida,
  request malformado) falha na hora; erro transiente (rede, rate limit,
  reasoning tokens truncando um JSON) tenta de novo — nunca os dois
  tratados da mesma forma.

---

## Como adicionar um documento novo

Passo a passo com os comandos reais. Sempre a partir de `cd MASHPIA/`. As
ferramentas de curadoria (`diagnostico_dispersao.py`, `propor_divisao.py`,
`sugerir_tags.py`, `sugerir_pesos_restantes.py`) leem o texto a partir de
`corpus_confirmado.json`, não do arquivo bruto direto — por isso o
documento precisa de uma entrada (mesmo provisória) em
`metadados_confirmados.py` **antes** de qualquer diagnóstico.

### 1. Colocar o arquivo
Copiar o `.odt`/`.txt` para dentro de uma pasta em `CHAT_NIVEL_2/` — uma
pasta `Novos/N` existente, uma pasta temática, ou uma nova.

### 2. Entrada provisória em `metadados_confirmados.py`
Adicionar em `DOCUMENTOS`, com tags vazias (só `autoria` já dá pra
preencher com o valor real — é a única coisa que não muda ao longo do
processo):
```python
{"pasta": "Novos/N", "chave": "nome_unico_do_arquivo", "autoria": "fonte_externa",
 "temas": [], "sefirot_define": [], "sefirot_expressa": [],
 "entidades": [], "conceitos_estruturais": [],
 "observacoes": "PROVISÓRIO — aguardando diagnóstico/tags."},
```

### 3. Puxar o texto real pro corpus
```bash
python3 pipeline/gerar_corpus.py
```
Idempotente. Extrai o texto do documento novo (via `pandoc`/leitura direta)
e grava em `corpus_confirmado.json` — a partir daqui as ferramentas de
curadoria conseguem ler o conteúdo dele. **Não** rodar `vetorizar.py`
ainda — isso é caro (embeddings de verdade) e só faz sentido rodar uma
vez, no fim, depois das tags finais decididas.

### 4. Diagnóstico de dispersão temática
```bash
python3 pipeline/diagnostico_dispersao.py "nome_do_arquivo.odt"
```
Um LLM lê o texto completo e avalia se o documento cobre mais assuntos do
que uma única tag de documento inteiro consegue capturar. Salva/mescla em
`pipeline/diagnostico_dispersao.json` (rodar escopado nunca apaga o
relatório de outros documentos — bug real já corrigido). Ver o veredito
impresso: `baixa`, `media` ou `alta`.

### 5. Se "alta": proposta de divisão
```bash
python3 pipeline/propor_divisao.py "nome_do_arquivo.odt"
```
Propõe uma partição dos chunks em arquivos focados, salvos em
`pipeline/propostas_divisao/<slug>/` (um `.txt` por grupo + `_proposta.json`
com título/justificativa de cada um). **Revisar antes de mover** — abrir o
`_proposta.json` e pelo menos alguns dos `.txt` pra conferir se os cortes
fazem sentido.

Se aprovado:
```bash
mkdir -p CHAT_NIVEL_2/Divididos
cp -r pipeline/propostas_divisao/<slug> CHAT_NIVEL_2/Divididos/
```
E então **remover** a entrada provisória do documento original em
`metadados_confirmados.py` (ela some, cada arquivo dividido vira sua
própria entrada no passo 7).

Se "media"/"baixa": pula direto para o passo 6, mantendo a entrada
provisória do passo 2 (só vai ganhar tags de verdade, sem dividir).

### 6. Sugestão de tags (Sefirah/Tema/Entidade) + peso de conceitos estruturais

**Se o documento foi dividido** (passo 5): decidir Sefirah/Tema/Entidade
de cada arquivo novo com o mesmo rigor manual sempre usado no projeto, e
rodar a sugestão de peso automaticamente:
```bash
python3 pipeline/sugerir_tags.py "<slug>"
```
Gera sugestão de Sefirah/Tema/Entidade **e** peso de conceitos estruturais
juntos, salvos/mesclados em `pipeline/sugestao_tags.json`. Revisar linha
por linha antes de gravar.

**Se o documento NÃO foi dividido**: Sefirah/Tema/Entidade continuam sendo
decisão manual direta (mesmo processo de sempre); só o peso de conceitos
estruturais precisa de ferramenta, porque é um eixo novo:
```bash
python3 pipeline/sugerir_pesos_restantes.py "nome_do_arquivo.odt"
```
Salva/mescla em `pipeline/pesos_documentos_restantes.json`.

### 7. Gravação final em `metadados_confirmados.py`
- **Documento não dividido**: substituir a entrada provisória pelos valores
  reais — `temas`/`sefirot_define`/`sefirot_expressa`/`entidades`
  decididos manualmente, `conceitos_estruturais` copiado do relatório do
  passo 6, `observacoes` reescrita de verdade.
- **Documento dividido**: nenhuma entrada provisória sobra (já removida no
  passo 5); adicionar uma entrada nova por arquivo dividido, com
  `pasta="Divididos/<slug>"`, `chave=<nome do arquivo>`, tags e
  `conceitos_estruturais` do relatório do passo 6.

### 8. Regenerar corpus e reindexar
```bash
python3 pipeline/gerar_corpus.py
python3 pipeline/vetorizar.py
```
`vetorizar.py` reconcilia sozinho — se alguma entrada foi removida (caso de
divisão), os chunks órfãos correspondentes são apagados da coleção
automaticamente.

### 9. Testar
```bash
python3 backend/teste_calibracao.py
python3 backend/gerar_resposta.py "uma pergunta que deveria puxar o conteúdo novo"
```
Conferir que o Sefirah/Tema esperado aparece, e que nada regrediu nas 8
perguntas fixas.

### 10. Commit e deploy
```bash
git add pipeline/metadados_confirmados.py pipeline/corpus_confirmado.json ...
git commit -m "..."
git push origin main
```
O Streamlit Cloud reconstrói o índice a partir de `corpus_confirmado.json`
no próximo restart do container — dar "Reboot app" no painel se quiser ver
refletido na hora.
