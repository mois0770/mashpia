"""Metadados confirmados por documento, re-derivados da análise manual feita na
conversa de design (ver CHAT_NIVEL_2/*/00_Analise.txt e
01_Arquitetura_e_Criterios.txt).

Granularidade: por documento (às vezes por trecho numerado, nos 8 arquivos de
Sefirot_Conceitos/, mas aqui simplificado para o documento inteiro). As tags
de um documento são aplicadas a TODOS os parágrafos/chunks extraídos dele —
isso é uma simplificação deliberada, documentada, não uma alegação de precisão
por parágrafo.

`chave` é uma substring ASCII segura (sem acentos/aspas curvas/travessões)
usada para localizar o arquivo real dentro da pasta, evitando erro de
correspondência por causa de caracteres especiais nos nomes originais.

Arquivos excluídos por não serem fonte de corpus (cópias de respostas da IA,
ou duplicatas de outro arquivo já presente): Analise_Claude.odt
(Sefirot_Conceitos_2), Uso.txt (Novos/1), kla_114.txt a kla_117.txt (Novos/5,
duplicam Klalei.txt).
"""

DOCUMENTOS = [
    # --- Sefirot_Conceitos ---
    {"pasta": "Sefirot_Conceitos", "chave": "01_Keter", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["Keter", "EinSof"], "sefirot_expressa": [],
     "observacoes": "Keter = intermediary between Ein Sof and Sefirot, root/soul of Sefirot, Ratzon Haelyon. Base da aresta PONTE."},
    {"pasta": "Sefirot_Conceitos", "chave": "02_ChaBaD", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["Chochmah", "Binah", "Daat", "Keter"], "sefirot_expressa": [],
     "observacoes": "Fonte da aresta GOVERNA expandida (7 alvos): Da'at e a essencia de todas as Midot. Abba/Imma/Ben = Chochmah/Binah/Daat."},
    {"pasta": "Sefirot_Conceitos", "chave": "03_ChaGaT", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["Chesed", "Gevurah", "Tiferet"], "sefirot_expressa": ["Chesed", "Gevurah", "Tiferet"],
     "observacoes": "Fonte da aresta SINTETIZA Chesed+Gevurah->Tiferet. EXPRESSA: Abraao/Isaac/Jaco."},
    {"pasta": "Sefirot_Conceitos", "chave": "04_NeHY", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["Netzach", "Hod", "Yesod"], "sefirot_expressa": ["Netzach", "Hod", "Chesed", "Gevurah"],
     "observacoes": "Fonte das arestas SINTETIZA Netzach+Hod->Yesod e CANALIZA. EXPRESSA: parabola pai ensinando o filho."},
    {"pasta": "Sefirot_Conceitos", "chave": "05_Malchut", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["Malchut", "EinSof"], "sefirot_expressa": [],
     "observacoes": "Malchut = vaso receptor final, origem da luz revelada do EinSof, identica a Shechinah."},
    {"pasta": "Sefirot_Conceitos", "chave": "Sefirot_Grafo_1", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["EinSof", "Malchut"], "sefirot_expressa": [],
     "observacoes": "Etimologia Adon Olam, guematria Adon=Ein/Olam=Sof, Tzimtzum como autolimitacao."},
    {"pasta": "Sefirot_Conceitos", "chave": "Sefirot_Grafo_2", "autoria": "fonte_externa",
     "temas": ["Fundamentos"],
     "sefirot_define": ["EinSof", "AdamKadmon", "Keter", "Chochmah", "Binah", "Daat", "Chesed",
                         "Gevurah", "Tiferet", "Netzach", "Hod", "Yesod", "Malchut"],
     "sefirot_expressa": [],
     "observacoes": "Tabela resumo, DEFINE thin, superada pelos docs posteriores. Relacao Adon Olam x EinSof."},
    {"pasta": "Sefirot_Conceitos", "chave": "Sefirot_Grafo_3", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["EinSof", "AdamKadmon", "Keter"],
     "sefirot_expressa": ["Chochmah", "Binah", "Daat", "Chesed", "Gevurah", "Tiferet", "Netzach", "Hod", "Yesod", "Malchut"],
     "observacoes": "AdamKadmon detalhado. Kochot HaNefesh: 1a EXPRESSA real do corpus."},

    # --- Sefirot_Conceitos_2 ---
    {"pasta": "Sefirot_Conceitos_2", "chave": "01.odt", "autoria": "fonte_externa",
     "temas": ["Fundamentos"],
     "sefirot_define": ["Keter", "Chochmah", "Binah", "Daat", "Chesed", "Gevurah", "Tiferet", "Netzach", "Hod", "Yesod", "Malchut"],
     "sefirot_expressa": ["Keter", "Chochmah", "Binah", "Daat", "Malchut"],
     "observacoes": "Chabad.org 'The Sefirot' (Dubov), 'Ten Powers of the Soul' (Miller), Tanya cap.3. Preenche EXPRESSA para Keter/Chochmah/Binah/Daat/Malchut."},
    {"pasta": "Sefirot_Conceitos_2", "chave": "02.odt", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["Keter", "Chochmah", "Binah", "Daat", "Malchut"],
     "sefirot_expressa": ["Keter", "Chochmah", "Binah", "Daat", "Malchut"],
     "observacoes": "Exemplo do medico fumante (Daat) com fonte. Guia do Omer (Jacobson) para Malchut."},
    {"pasta": "Sefirot_Conceitos_2", "chave": "03.odt", "autoria": "fonte_externa",
     "temas": ["Fundamentos"],
     "sefirot_define": ["Keter", "Chochmah", "Binah", "Daat", "Chesed", "Gevurah", "Tiferet", "Netzach", "Hod", "Yesod", "Malchut"],
     "sefirot_expressa": ["Chesed", "Gevurah", "Tiferet", "Netzach", "Hod", "Yesod", "Malchut"],
     "observacoes": "Correspondencia biblica completa das 7 Sefirot inferiores, ligada a Contagem do Omer (Jacobson). Igrot Kodesh vol.4."},
    {"pasta": "Sefirot_Conceitos_2", "chave": "04.odt", "autoria": "fonte_externa",
     "temas": ["Fundamentos"],
     "sefirot_define": ["Keter", "Chochmah", "Binah", "Daat", "Chesed", "Gevurah", "Tiferet", "Netzach", "Hod", "Yesod", "Malchut"],
     "sefirot_expressa": ["Keter", "Chochmah", "Binah", "Daat", "Chesed", "Gevurah", "Tiferet", "Netzach", "Hod", "Yesod", "Malchut"],
     "observacoes": "Nomeia 'Moach Shalit Al HaLev' (Tanya caps.3 e 16) explicitamente. Ma'aseh Hu HaIkar (Tanya 35/37) para Malchut."},
    {"pasta": "Sefirot_Conceitos_2", "chave": "05.odt", "autoria": "fonte_externa",
     "temas": ["Fundamentos"],
     "sefirot_define": ["Keter", "Chochmah", "Binah", "Daat", "Chesed", "Gevurah", "Tiferet", "Netzach", "Hod", "Yesod", "Malchut"],
     "sefirot_expressa": ["Chochmah", "Binah", "Daat", "Chesed", "Gevurah", "Tiferet", "Netzach", "Hod", "Yesod", "Malchut"],
     "observacoes": "Citacoes diretas com URL chabad.org por trecho. Medico fumante repetido com fonte especifica."},

    # --- Novos/1 ---
    {"pasta": "Novos/1", "chave": "13 Meditations", "autoria": "fonte_externa",
     "temas": ["Financas"], "sefirot_define": [], "sefirot_expressa": ["Malchut", "Chesed"],
     "observacoes": "Tzvi Freeman, chabad.org. Likkutei Sichot, Igeret Hakodesh 11, Torat Menachem 5742."},
    {"pasta": "Novos/1", "chave": "A Dwelling Below", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["EinSof", "Keter"], "sefirot_expressa": ["Malchut"],
     "observacoes": "Tzvi Freeman, chabad.org. FONTE de Dira BeTachtonim no prompt fixo. Nuance em Keter: a Essencia (Etzem) fica alem ate de Keter, distinta da Vontade Suprema. Duplicata parcial de 'Where the Essence Dwells' (Novos/9)."},
    {"pasta": "Novos/1", "chave": "Anxiety", "autoria": "fonte_externa",
     "temas": ["Saude_Mental"], "sefirot_define": [], "sefirot_expressa": [],
     "entidades": ["Nefesh_nivel", "Ruach_nivel", "Neshamah_nivel", "Chayah_nivel", "Yechidah_nivel"],
     "observacoes": "Ginsburgh, inner.org/mental/mental40.htm. 1a fonte dos 5 niveis da alma (via Jo)."},
    {"pasta": "Novos/1", "chave": "Basis of Humility", "autoria": "fonte_externa",
     "temas": ["Humildade"], "sefirot_define": [], "sefirot_expressa": ["Hod"],
     "observacoes": "Ginsburgh, inner.org, serie 'Mystery of Marriage'. Tanya Igeret HaKodesh/HaTeshuvah."},

    # --- Novos/2 ---
    {"pasta": "Novos/2", "chave": "Boosting Self-Esteem", "autoria": "fonte_externa",
     "temas": ["Autoestima"], "sefirot_define": [], "sefirot_expressa": ["Keter"],
     "observacoes": "chabad.org Q&A. Valor intrinseco da alma."},
    {"pasta": "Novos/2", "chave": "Combating Sadness", "autoria": "fonte_externa",
     "temas": ["Saude_Mental"], "sefirot_define": [], "sefirot_expressa": ["Daat", "Netzach"],
     "observacoes": "Cartas do Rebbe (Igros Kodesh), Tanya cap.41, Chovos HaLevavos."},
    {"pasta": "Novos/2", "chave": "Educacacao", "autoria": "autor_projeto",
     "temas": ["Educacao", "Fundamentos"], "sefirot_define": ["AdamKadmon", "Chochmah", "Binah"],
     "sefirot_expressa": ["Chochmah", "Binah"],
     "observacoes": "TEXTO PROPRIO DO USUARIO ('Sistema Talmud'). Cita o Zohar: intelecto domina o coracao (3a fonte de Moach Sholet Al HaLev). Chochmah/Binah = 'dois amigos inseparaveis' (Zohar), principio holistico (cada Sefirah contem todas as demais)."},
    {"pasta": "Novos/2", "chave": "Moral Obligation", "autoria": "fonte_externa",
     "temas": ["Educacao"], "sefirot_define": [], "sefirot_expressa": ["Chochmah", "Binah", "Daat"],
     "observacoes": "Provavel carta/proclamacao publica do Rebbe."},

    # --- Novos/3 ---
    {"pasta": "Novos/3", "chave": "Education and Leadership", "autoria": "fonte_externa",
     "temas": ["Lideranca", "Educacao"], "sefirot_define": ["Chochmah", "Binah", "Malchut"],
     "sefirot_expressa": ["Chochmah", "Binah", "Malchut"],
     "observacoes": "Dr. Tali Loewenthal, Library of Congress. Correspondencia Tetragrammaton <-> Sefirot."},
    {"pasta": "Novos/3", "chave": "Five Dynamics", "autoria": "fonte_externa",
     "temas": ["Lideranca"], "sefirot_define": [], "sefirot_expressa": ["Netzach", "Hod"],
     "observacoes": "inner.org. Pirkei Avot, Moises/Josue, Arizal sobre Tzimtzum."},
    {"pasta": "Novos/3", "chave": "For Whom", "autoria": "fonte_externa",
     "temas": ["Proposito", "Fundamentos"], "sefirot_define": [], "sefirot_expressa": ["Netzach", "Malchut"],
     "observacoes": "inner.org. Talmud. Moises=Netzach, David=Malchut reforcados."},
    {"pasta": "Novos/3", "chave": "Four Crowns", "autoria": "fonte_externa",
     "temas": ["Proposito", "Autoestima"], "sefirot_define": ["Keter"], "sefirot_expressa": ["Chochmah", "Binah", "Malchut"],
     "observacoes": "inner.org/Ginsburgh. Guematria dos 'zer zahav'. Cruza com Maslow abertamente."},

    # --- Novos/4 ---
    {"pasta": "Novos/4", "chave": "Kabbalah Approach.odt", "autoria": "fonte_externa",
     "temas": ["Saude_Mental"], "sefirot_define": [], "sefirot_expressa": ["Malchut", "Daat"],
     "observacoes": "inner.org/mental/mental30.htm. 3 vestimentas da alma (Pensamento-Fala-Acao)."},
    {"pasta": "Novos/4", "chave": "Approach_39", "autoria": "fonte_externa",
     "temas": ["Saude_Mental"], "sefirot_define": [], "sefirot_expressa": [],
     "entidades": ["Nefesh_nivel", "Ruach_nivel", "Neshamah_nivel", "Chayah_nivel", "Yechidah_nivel"],
     "observacoes": "inner.org/mental/mental39.htm. 2a fonte dos 5 niveis da alma."},

    # --- Novos/5 ---
    {"pasta": "Novos/5", "chave": "Klalei", "autoria": "traducao_propria",
     "temas": ["Educacao"], "sefirot_define": ["Keter", "AdamKadmon", "Daat"],
     "sefirot_expressa": ["Daat", "Gevurah", "Chochmah", "Binah"],
     "entidades": ["Pnimi", "Makif"],
     "observacoes": "Traducao do usuario, obra de Rabino Iossef Isaac Schneerson. Mesmo capitulo citado por Educacacao.odt. Cita o Rambam (Hilchot Yessodei HaTorah cap.7)."},

    # --- Novos/6 ---
    {"pasta": "Novos/6", "chave": "Rectified Ego", "autoria": "fonte_externa",
     "temas": ["Lideranca", "Humildade"], "sefirot_define": [], "sefirot_expressa": ["Malchut", "Hod"],
     "observacoes": "inner.org/leader/leader3.htm. Guematria ani/ayin. David vs. Adoniyahu."},
    {"pasta": "Novos/6", "chave": "Rectified Speech", "autoria": "fonte_externa",
     "temas": ["Lideranca"], "sefirot_define": ["Malchut"], "sefirot_expressa": ["Malchut"],
     "observacoes": "inner.org/leader/leader2.htm. Patach Eliyahu: Malchut = 'malchut peh'."},
    {"pasta": "Novos/6", "chave": "Messianic Spark", "autoria": "fonte_externa",
     "temas": ["Lideranca", "Proposito", "Saude_Mental"], "sefirot_define": [], "sefirot_expressa": [],
     "entidades": ["Nefesh_nivel", "Ruach_nivel", "Neshamah_nivel", "Chayah_nivel", "Yechidah_nivel"],
     "observacoes": "inner.org/leader/leader1.htm. 3a fonte independente dos 5 niveis da alma, a mais citavel."},

    # --- Novos/7 ---
    {"pasta": "Novos/7", "chave": "positive self-image", "autoria": "fonte_externa",
     "temas": ["Autoestima"], "sefirot_define": [], "sefirot_expressa": ["Keter"],
     "observacoes": "Carta do Rebbe, chabad.org. Minimizar o proprio valor e truque do yetzer hara."},
    {"pasta": "Novos/7", "chave": "Self-Esteem.odt", "autoria": "fonte_externa",
     "temas": ["Autoestima"], "sefirot_define": [], "sefirot_expressa": ["Yesod", "Malchut", "Keter"],
     "observacoes": "chabad.org Q&A. Rabbi Moshe Cordevero."},
    {"pasta": "Novos/7", "chave": "autoestima.odt", "autoria": "fonte_externa",
     "temas": ["Autoestima"], "sefirot_define": [], "sefirot_expressa": ["Keter", "Hod", "Malchut"],
     "observacoes": "Sintese/indice, nao fonte primaria."},
    {"pasta": "Novos/7", "chave": "Humility & Happiness", "autoria": "fonte_externa",
     "temas": ["Autoestima", "Saude_Mental"], "sefirot_define": ["Hod"], "sefirot_expressa": ["Hod"],
     "observacoes": "Discurso real do Rabino Shalom Dovber (Rashab), 1918. chabad.org."},
    {"pasta": "Novos/7", "chave": "Ego, And", "autoria": "fonte_externa",
     "temas": ["Autoestima"], "sefirot_define": [], "sefirot_expressa": ["Keter", "Hod"],
     "observacoes": "chabad.org Q&A. Talentos como dom Divino a desenvolver."},
    {"pasta": "Novos/7", "chave": "Self-Esteem And", "autoria": "fonte_externa",
     "temas": ["Autoestima"], "sefirot_define": [], "sefirot_expressa": ["Yesod", "Malchut", "Keter"],
     "observacoes": "DUPLICATA de Self-Esteem.odt (mesmo artigo chabad.org)."},
    {"pasta": "Novos/7", "chave": "Humble Self-Esteem", "autoria": "fonte_externa",
     "temas": ["Autoestima", "Humildade"], "sefirot_define": ["Hod"], "sefirot_expressa": ["Hod", "Keter"],
     "observacoes": "Sichah real do Rebbe (Behar-Bechukosai), chabad.org/therebbe."},

    # --- Novos/8 ---
    {"pasta": "Novos/8", "chave": "Shalom Bayit", "autoria": "fonte_externa",
     "temas": ["Casamento"], "sefirot_define": [], "sefirot_expressa": ["Tiferet"],
     "observacoes": "chabad.org. Traducao talmudica dos 40 dias antes do nascimento, com integridade."},
    {"pasta": "Novos/8", "chave": "speak-to-the-heart", "autoria": "fonte_externa",
     "temas": ["Lideranca"], "sefirot_define": ["Netzach", "Hod", "Yesod"], "sefirot_expressa": ["Netzach", "Hod", "Yesod"],
     "observacoes": "inner.org. NAO e sobre Casamento apesar da pasta. Or HaChaim."},
    {"pasta": "Novos/8", "chave": "Cultivating Selflessness", "autoria": "fonte_externa",
     "temas": ["Casamento"], "sefirot_define": [], "sefirot_expressa": [],
     "entidades": ["Olam_dimensao", "Shanah_dimensao", "Nefesh_dimensao"],
     "observacoes": "inner.org/covenant/marr09.htm. Trio Olam-Shanah-Nefesh."},
    {"pasta": "Novos/8", "chave": "Finding Eve", "autoria": "fonte_externa",
     "temas": ["Casamento"], "sefirot_define": [], "sefirot_expressa": [],
     "observacoes": "inner.org/covenant/marr02.htm. Talmud Kidushin 2b, Bereishit Rabbah 17:6."},
    {"pasta": "Novos/8", "chave": "Have You Found", "autoria": "fonte_externa",
     "temas": ["Casamento"], "sefirot_define": [], "sefirot_expressa": ["Chesed"],
     "observacoes": "inner.org/covenant/marr01.htm. Talmud Yevamot 63b, Zohar 343b."},
    {"pasta": "Novos/8", "chave": "Three Levels", "autoria": "fonte_externa",
     "temas": ["Casamento"], "sefirot_define": [], "sefirot_expressa": [],
     "entidades": ["Tzadik", "Beinoni"],
     "observacoes": "inner.org/covenant/marr11.htm. Eixo Tzadik-Beinoni (Tanya)."},
    {"pasta": "Novos/8", "chave": "True State", "autoria": "fonte_externa",
     "temas": ["Saude_Mental", "Autoestima"], "sefirot_define": [], "sefirot_expressa": ["Keter"],
     "observacoes": "Carta datada do Rebbe (5719). NAO e sobre Casamento apesar da pasta."},

    # --- Novos/9 ---
    {"pasta": "Novos/9", "chave": "Four Reasons", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["EinSof", "Chochmah", "Malchut"], "sefirot_expressa": [],
     "observacoes": "inner.org. FONTE-ANCORA de Dira BeTachtonim como razao PRIMARIA em Chabad (Tanya)."},
    {"pasta": "Novos/9", "chave": "Purpose of this World", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["EinSof"], "sefirot_expressa": [],
     "observacoes": "chabad.org, provavel Tzvi Freeman. Registro popular do mesmo tema do Partzuf."},
    {"pasta": "Novos/9", "chave": "Descent to This World", "autoria": "fonte_externa",
     "temas": ["Fundamentos", "Proposito"], "sefirot_define": ["EinSof"], "sefirot_expressa": [],
     "observacoes": "chabad.org/therebbe, Sichah real do Rebbe. Bittul, 'conhece-O em todos os teus caminhos'."},
    {"pasta": "Novos/9", "chave": "Secret of Enclothement", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": [], "sefirot_expressa": ["Malchut"],
     "entidades": ["Mashiach"],
     "observacoes": "inner.org. Materia como 'luz condensada' (Zohar), comparacao aberta com relatividade."},
    {"pasta": "Novos/9", "chave": "Nine Principles", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": ["EinSof", "Chochmah", "Binah"], "sefirot_expressa": [],
     "observacoes": "inner.org, serie 'Wonders' (Ginsburgh), Parte 2. Nachmanides, Maharal. Chochmah/Binah = 'dois amigos que nunca se separam' (confirma Educacacao.odt)."},
    {"pasta": "Novos/9", "chave": "Essence Dwells", "autoria": "fonte_externa",
     "temas": ["Fundamentos"], "sefirot_define": [], "sefirot_expressa": [],
     "observacoes": "DUPLICATA/variante de 'A Dwelling Below' (Novos/1). Nao conta como fonte independente."},

    # --- Novos/10 ---
    {"pasta": "Novos/10", "chave": "Kesef", "autoria": "fonte_externa",
     "temas": ["Financas"], "sefirot_define": [], "sefirot_expressa": ["Malchut", "Chesed"],
     "observacoes": "chabad.org. Mitzvot de honestidade e redistribuicao. Talmud: primeira pergunta do tribunal celestial."},
]

# Arquivo vazio confirmado (nao entra no corpus, so registrado por completude)
ARQUIVOS_VAZIOS = [
    {"pasta": "Novos/10", "chave": "Personal Finance",
     "observacoes": "ARQUIVO VAZIO - confirmado no XML interno do .odt."},
]
