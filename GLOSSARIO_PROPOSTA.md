# Proposta de Glossário Fixo — Inglês e Espanhol

**STATUS: APROVADO em 2026-07-29**, com 3 decisões do curador:
1. Moach Sholet Al HaLev (EN) = "the mind rules over the heart" (substitui a proposta original).
2. Glosa de Daat = mantida como estava (sem ajuste pra frase do corpus).
3. Grafia = "Daat" (não "Da'at") em toda ocorrência, nos dois idiomas.

Já incorporado em `00_Prompt_Sistema_Fixo.txt` (seção "TERMINOLOGIA FIXADA — TRADUÇÃO POR
IDIOMA"). Este arquivo fica como registro do processo de curadoria.


Segue o padrão do projeto: eu proponho, você confirma/ajusta. Depois de aprovado, isto entra
como uma seção nova em `00_Prompt_Sistema_Fixo.txt` (algo como "TERMINOLOGIA FIXADA — outros
idiomas"), para o LLM parar de traduzir esses termos do zero a cada resposta.

Escopo: os termos que já são "fixos" em português (`TERMINOLOGIA FIXADA` + `CONCEITOS_ESTRUTURAIS`),
mais Ein Sof (por aparecer dentro da glosa de dois outros termos). Não inclui os 11 nomes de
Sefirot nem as 14 Entidades — o prompt já os isenta da glosa obrigatória quando o texto explica o
sentido no fluxo da resposta, então o risco de inconsistência é bem menor ali.

Cada entrada indica se a proposta tem **base no próprio corpus** (o texto em inglês já usa essa
formulação) ou se é **tradução minha**, sem precedente direto nas fontes — marcado para você revisar
com mais atenção, já que ali eu não tenho como verificar contra a fonte.

---

## 1. Dirá BeTachtonim — base no corpus (alta confiança)

- **PT (fixo):** Objetivo da Criação — que o mundo material se torne morada para a Presença Divina.
- **EN (proposto):** *the Purpose of Creation — that the physical world become a dwelling place for
  God in the lower realms.*
- **ES (proposto, tradução minha):** *el Objetivo de la Creación — que el mundo material se
  convierta en morada para la Presencia Divina en los mundos inferiores.*

Achado no próprio corpus, em inglês (documentos `01_o_decreto_rescindido...` e
`05_paralelo_alma-mundo...`): a fonte já traduz literalmente "dira b'tachtonim" como **"a dwelling
in the lower realms"** / **"dwelling below"**. Não é uma tradução minha — é a formulação que a
própria fonte em inglês usa. Por isso a proposta EN acima incorpora essa frase quase ao pé da
letra, só reordenando pra caber no formato de glosa entre colchetes.

Termo em hebraico continua igual nos dois idiomas: **Dirá BeTachtonim**.

---

## 2. Moach Sholet Al HaLev — DECIDIDO pelo curador

- **PT (fixo):** a Mente governa o Sentimento.
- **EN (final, definido pelo curador):** *the mind rules over the heart.*
- **ES (proposto):** *la Mente gobierna el Corazón*.

Não achei ocorrência desse termo no corpus atual (0 resultados) — ele vem do `EXCEÇÃO — regras
estruturais sempre ativas`, não de um chunk específico. O curador forneceu diretamente a formulação
padrão em inglês ("the mind rules over the heart"), substituindo minha proposta original.

Termo em hebraico continua igual: **Moach Sholet Al HaLev**.

---

## 3. Daat — parcialmente apoiado no corpus

- **PT (fixo):** interface entre intelecto e emoção (não "dobradiça").
- **EN (proposto):** *the interface between intellect and emotion.*
- **ES (proposto, tradução minha):** *la interfaz entre el intelecto y la emoción.*

O corpus (`02_ChaBaD.odt`, em inglês) descreve Daat como *"the unifying principle that brings
together and joins the faculties of Chochmah and Binah"* — compatível com a definição fixada, mas
não é a mesma frase. A proposta EN acima é uma tradução direta do termo fixo em português, não uma
citação da fonte. Se preferir alinhar literalmente com a frase do corpus ("unifying principle
that joins Chochmah and Binah"), me avisa que eu ajusto.

Termo continua igual nos dois idiomas: **Daat** (grafia sem apóstrofo, decidida pelo curador — mesmo
que a fonte em inglês use "Da'at" em alguns trechos).

---

## 4. Adam Kadmon — nome próprio, só a glosa muda

- **PT (fixo):** ponte entre a Fonte (Ein Sof/Infinito) e a Criação.
- **EN (proposto):** *the bridge between the Source (Ein Sof, the Infinite) and Creation.*
- **ES (proposto):** *el puente entre la Fuente (Ein Sof, el Infinito) y la Creación.*

O nome "Adam Kadmon" já aparece como está no corpus em português (`Sefirot_Grafo_2/3.odt`, glosado
ali como "Homem Primordial") — é termo técnico consagrado, mantido sem tradução em inglês e
espanhol também, igual já fazemos com os nomes das Sefirot.

Termo continua igual nos dois idiomas: **Adam Kadmon**.

---

## 5. Adon Olam — nome próprio, só a glosa muda

- **PT (fixo):** hino que explica a atuação Divina antes-durante-depois da Criação.
- **EN (proposto):** *the hymn that describes God's activity before, during, and after Creation.*
- **ES (proposto):** *el himno que describe la actuación Divina antes, durante y después de la
  Creación.*

"Adon Olam" é o nome de um hino litúrgico conhecido (recitado em Shacharit/Arvit) — mantido sem
tradução em qualquer idioma, como qualquer título próprio.

Termo continua igual nos dois idiomas: **Adon Olam**.

---

## 6. Ein Sof — termo de apoio (usado dentro de outras glosas)

Não é um dos 4+3 termos fixados originalmente, mas aparece dentro da glosa de Adam Kadmon e de
Dirá BeTachtonim acima — por isso proponho fixá-lo também, pra não ficar sem tradução consistente
nas próprias glosas dos outros termos.

- **PT (uso corrente no corpus):** Sem Fim, Infinito (referência a Deus antes de qualquer
  manifestação/limitação).
- **EN (proposto):** *the Infinite, without limit.*
- **ES (proposto):** *el Infinito, sin límite.*

Termo continua igual nos dois idiomas: **Ein Sof**.

---

## Resumo — tabela de revisão rápida

| Termo (hebraico, invariável) | EN proposto | ES proposto | Base |
|---|---|---|---|
| Dirá BeTachtonim | a dwelling place for God in the lower realms | morada para la Presencia Divina en los mundos inferiores | ✅ corpus |
| Moach Sholet Al HaLev | the mind rules over the heart | la Mente gobierna el Corazón | ✅ decidido pelo curador |
| Daat | the interface between intellect and emotion | la interfaz entre el intelecto y la emoción | ⚠️ parcial (mantido como estava) |
| Adam Kadmon | the bridge between the Source (Ein Sof) and Creation | el puente entre la Fuente (Ein Sof) y la Creación | ✅ nome consagrado, glosa traduzida |
| Adon Olam | the hymn describing God's activity before/during/after Creation | el himno... antes, durante y después de la Creación | ✅ nome consagrado, glosa traduzida |
| Ein Sof | the Infinite, without limit | el Infinito, sin límite | ✅ nome consagrado, glosa traduzida |

Grafia final em todos os idiomas: **Daat** (sem apóstrofo).
===========
Glossário incorporado e testado com sucesso nos dois idiomas — termos fixos saíram com a glosa exata aprovada:

- Inglês: Ein Sof [the Infinite, without limit] e fechamento Dirá BeTachtonim: ... a dwelling place for God in the lower realms
- Espanhol: Moach Sholet Al HaLev [la Mente gobierna el Corazón] e fechamento Dirá BeTachtonim [morada para la Presencia Divina en los mundos inferiores]

Arquivos atualizados: CHAT_NIVEL_2/00_Prompt_Sistema_Fixo.txt (fonte) e MASHPIA/00_Prompt_Sistema_Fixo.txt (cópia sincronizada), com a nova seção "TERMINOLOGIA FIXADA — TRADUÇÃO POR IDIOMA". GLOSSARIO_PROPOSTA.md atualizado como registro da curadoria (status APROVADO).

Detalhe à parte, não relacionado ao glossário: no teste em espanhol a resposta usou "vontade" (português) em vez de "voluntad" — um vazamento pontual não ligado aos termos fixos que acabamos de tratar. Não mexi nisso agora; avise se quiser que eu investigue.
============ Investiga


