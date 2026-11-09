import os
import re
import tempfile
import streamlit as st
from google import genai
from google.genai import types
from fpdf import FPDF

# Configuração da Página
st.set_page_config(
    page_title="AUDITOR TSG",
    page_icon="🗺️",
    layout="wide"
)

# ----------------- CAMADA DE SEGURANÇA E ACESSO -----------------
def verificar_acesso():
    """Valida a palavra-passe definida nos Secrets antes de carregar o sistema."""
    senha_correta = st.secrets.get("APP_PASSWORD", "tsg2026")
    
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        col_esq, col_centro, col_dir = st.columns([1, 2, 1])
        with col_centro:
            st.markdown("## 🔒 TSG Soluções Ambientais, Topografia e Georreferenciamento")
            st.markdown("### Acesso Restrito - AUDITOR TSG")
            senha_digitada = st.text_input("Introduza a palavra-passe de acesso:", type="password")
            if st.button("Entrar", type="primary", use_container_width=True):
                if senha_digitada == senha_correta:
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Palavra-passe incorreta. Acesso negado.")
            st.stop()

# Executa o bloqueio de segurança
verificar_acesso()

# Obtém a API Key de forma oculta a partir dos Segredos (Secrets)
api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))

# ----------------- GESTÃO DE IMAGENS E PDF -----------------
PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))
PASTA_ATUAL = os.getcwd()

def obter_caminho_logo():
    """Localiza a imagem do logotipo da TSG para cabeçalho do documento."""
    pastas_busca = [PASTA_PROJETO, PASTA_ATUAL]
    extensoes_validas = (".jpg", ".jpeg", ".png", ".webp")
    for pasta in pastas_busca:
        if not os.path.exists(pasta):
            continue
        try:
            for arquivo in os.listdir(pasta):
                nome_minusculo = arquivo.lower()
                if "logo" in nome_minusculo and any(nome_minusculo.endswith(ext) for ext in extensoes_validas):
                    return os.path.join(pasta, arquivo)
        except Exception:
            pass
    return None

class AuditoriaPDF(FPDF):
    def header(self):
        caminho_logo = obter_caminho_logo()
        if caminho_logo:
            self.image(caminho_logo, x=12, y=6, w=34)
            self.set_xy(48, 10)
            largura_texto = self.epw - 36
        else:
            self.set_xy(12, 10)
            largura_texto = self.epw

        # Título Corporativo TSG (sem o subtítulo longo)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(20, 45, 30)
        self.cell(largura_texto, 8, "TSG - RELATORIO DE AUDITORIA NOTARIAL E REGISTRAL RURAL", border=0, new_x="LMARGIN", new_y="NEXT", align="L")
        
        # Linha decorativa verde institucional da TSG
        self.ln(2)
        self.set_draw_color(34, 112, 62)
        self.set_line_width(0.4)
        self.line(12, 22, 12 + self.epw, 22)
        self.set_draw_color(180, 185, 195)
        self.set_line_width(0.2)
        self.set_text_color(0, 0, 0)
        self.set_y(25)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        # Rodapé completo corrigido
        self.cell(self.epw, 10, f"TSG Solucoes Ambientais, Topografia e Georreferenciamento | Pagina {self.page_no()}/{{nb}}", align="C")
        self.set_text_color(0, 0, 0)

def sanitizar_para_pdf(texto: str) -> str:
    substituicoes = {
        "–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'",
        "…": "...", "•": "*", "º": "o.", "ª": "a.", "§": "Art.", "°": " graus ",
    }
    for orig, dest in substituicoes.items():
        texto = texto.replace(orig, dest)
    texto = re.sub(r"\*\*(.*?)\*\*", r"\1", texto)
    texto = re.sub(r"\*(.*?)\*", r"\1", texto)
    texto = texto.replace("<br>", "\n").replace("<br/>", "\n").replace("&nbsp;", " ")
    return texto.encode("latin-1", "replace").decode("latin-1").strip()

def exportar_para_pdf(texto_relatorio: str) -> bytes:
    pdf = AuditoriaPDF(orientation="L", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    
    linhas = texto_relatorio.split("\n")
    i = 0
    total_linhas = len(linhas)
    
    while i < total_linhas:
        linha_crua = linhas[i].strip()
        if not linha_crua:
            pdf.ln(2)
            i += 1
            continue
            
        if linha_crua.startswith("|") and linha_crua.endswith("|"):
            linhas_tabela = []
            while i < total_linhas and linhas[i].strip().startswith("|") and linhas[i].strip().endswith("|"):
                linha_tab = linhas[i].strip()
                if not set(linha_tab.replace("|", "").replace(":", "").replace("-", "").strip()) == set():
                    linhas_tabela.append(linha_tab)
                elif linha_tab.replace("|", "").replace(":", "").replace("-", "").strip() != "":
                    linhas_tabela.append(linha_tab)
                i += 1
            if linhas_tabela:
                renderizar_tabela_markdown(pdf, linhas_tabela)
            continue
            
        if linha_crua.startswith("#"):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(240, 245, 242)
            titulo = sanitizar_para_pdf(linha_crua.lstrip("#").strip())
            pdf.multi_cell(pdf.epw, 5.5, titulo, border="B", fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)
            i += 1
            continue
            
        if linha_crua.startswith("* ") or linha_crua.startswith("- "):
            pdf.set_font("Helvetica", size=8.5)
            conteudo = sanitizar_para_pdf(linha_crua[2:])
            pdf.multi_cell(pdf.epw, 4.2, f"  * {conteudo}", new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue

        pdf.set_font("Helvetica", size=8.5)
        conteudo = sanitizar_para_pdf(linha_crua)
        pdf.multi_cell(pdf.epw, 4.2, conteudo, new_x="LMARGIN", new_y="NEXT")
        i += 1

    return bytes(pdf.output())

def renderizar_tabela_markdown(pdf: AuditoriaPDF, linhas_tabela: list):
    dados_processados = []
    for l in linhas_tabela:
        celulas = [sanitizar_para_pdf(c) for c in l.strip("|").split("|")]
        dados_processados.append(celulas)
        
    if not dados_processados:
        return

    num_colunas = max(len(row) for row in dados_processados)
    for row in dados_processados:
        while len(row) < num_colunas:
            row.append("")

    largura_total = pdf.epw
    if num_colunas == 7:
        proporcoes = [0.12, 0.14, 0.16, 0.17, 0.16, 0.11, 0.14]
    elif num_colunas == 5:
        proporcoes = [0.06, 0.22, 0.22, 0.32, 0.18]
    elif num_colunas == 4:
        proporcoes = [0.18, 0.22, 0.35, 0.25]
    else:
        proporcoes = [1.0 / num_colunas] * num_colunas
        
    col_widths = [largura_total * p for p in proporcoes]
    pdf.ln(2)
    pdf.set_draw_color(180, 185, 195)
    
    cabecalho = dados_processados[0]
    with pdf.table(
        col_widths=col_widths,
        text_align="LEFT",
        borders_layout="ALL",
        line_height=3.8,
        padding=1.5
    ) as table:
        header_row = table.row()
        pdf.set_font("Helvetica", "B", 7.5)
        for col_text in cabecalho:
            header_row.cell(col_text)
            
        pdf.set_font("Helvetica", size=7.2)
        for linha_dados in dados_processados[1:]:
            row = table.row()
            for cell_text in linha_dados:
                row.cell(cell_text)
    pdf.ln(3)

# ----------------- PROMPTS ESPECIALISTAS -----------------
PROMPT_AUDITORIA_COMPLETA = """
Voce e um Engenheiro Agrimensor e Consultor Juridico Notarial/Registral senior da empresa TSG - Solucoes Ambientais, Topografia e Georreferenciamento, especializado em Direito Notarial e Registral Imobiliario Brasileiro, Lei 6.015/1973 (Arts. 212 e 213), Lei 10.267/2001 e Normas Tecnicas do INCRA/SIGEF.

Sua tarefa e fazer a auditoria cruzada estrita entre a Matricula Paradigma, Matriculas dos Confrontantes e as Pecas Tecnicas.
Esta e uma ANALISE PREVIA DE MINUTAS.

CRITERIOS E PARAMETROS ESPECIFICOS:
1. Confrontantes Tabulares vs. Pecas Tecnicas:
   - Restrinja a conferencia dos confrontantes estritamente aos dados inseridos nas pecas tecnicas: Nome completo, CPF, matricula do confrontante e denominacao do imovel.
   - Pluralidade de Proprietarios: Se a matricula do confrontante tiver multiplos coproprietarios, considere REGULAR e suficiente a indicacao de apenas 1 deles como representante anuente formalizado.
   - Ignore ausencia de reconhecimento de firma ou carimbos notariais (analise pre-impressao).
2. Imovel Paradigma:
   - Denominacao, Comarca, CNS, Matricula, codigos cadastrais (INCRA/SNCR, NIRF/CIB, CAR e SIGEF).
   - Continuidade e Disponibilidade: Verificar titularidade atual e gravames/penhoras.
3. Coerencia Tecnica:
   - Area (ha e m²) e perimetro identicos em Memorial Descritivo, Planta Topografica, Requerimento e ART/TRT.
   - Responsavel Tecnico (Nome, Conselho e Codigo INCRA) uniformes.

ESTRUTURA OBRIGATORIA DO RELATORIO:
1. Resumo do Imovel e Conformidade Geral (EM TEXTO E TOPICOS, indicando Status: APTO / INAPTO COM EXIGENCIAS / DIVERGENCIAS CRITICAS).
2. Tabela de Matriz de Confrontacoes e Anuencias (EM TABELA MARKDOWN: Segmento/Vértices, Confrontante Declarado, Matrícula Confrontante, Proprietário Tabular, Representante Declarado, CPF, Situação Notarial).
3. Matriz de Inconsistencias Tecnicas e Cadastrais (EM TABELA MARKDOWN: Item, Peça de Origem, Peça Divergente, Descrição Detalhada, Impacto Registral).
4. Minuta de Nota Devolutiva Registral Previa (EM TEXTO DISCURSIVO COM ITENS NUMERADOS).
"""

PROMPT_ANALISE_MATRICULA_ISOLADA = """
Voce e um Engenheiro Agrimensor e Consultor Juridico Notarial/Registral senior da empresa TSG - Solucoes Ambientais, Topografia e Georreferenciamento, especializado em Direito Notarial e Registral Imobiliario Brasileiro, Lei 6.015/1973 e Lei 10.267/2001.

O usuario enviou APENAS A MATRICULA DO IMOVEL A RETIFICAR (sem pecas tecnicas anexadas).
Sua missao e realizar uma AUDITORIA JURIDICO-REGISTRAL PREVIA DA MATRICULA para orientar a elaboracao dos trabalhos topograficos de georreferenciamento e instrucao do processo de retificacao de area (art. 213, II da Lei 6.015/73).

ESTRUTURA OBRIGATORIA DO RELATORIO:
1. Diagnostico Dominial e Tabular do Imovel:
   - Denominacao, Comarca, Circunscricao Registral, Numero da Matricula.
   - Area Tabular Registrada (origem e eventuais destaques ao longo dos registros/averbacoes).
   - Cadeia Dominial Resumida e Titulares Atuais do Dominio (qualificacao, estado civil, regime de bens e continuidade).
2. Gravames, Onus e Disponibilidade (Analise Critica):
   - Detalhamento de penhoras, hipotecas, usufrutos, acoes reipersecutorias ou indisponibilidades averbadas.
   - Orientacoes sobre a necessidade de autorizacao judicial ou levantamento de gravames em caso de retificacao/desmembramento futuro.
3. Codigos Cadastrais e Situacao Tributaria Constante na Matricula:
   - Codigo INCRA/SNCR, NIRF/CIB, CAR, indicando o que consta registrado e o que precisara ser atualizado/averbado.
4. Tabela de Confrontantes Tabulares Historicos:
   - Montar uma TABELA MARKDOWN com os confrontantes citados na descricao da matricula: Confrontacao Original, Proprietario Tabular Mencionado, Matricula Indicada (se houver), Recomendacoes para a Topografia em Campo.
5. Recomendacoes Tecnicas e Juridicas para o Georreferenciamento e Retificacao (TSG):
   - Checklist dos documentos e cautelas que o agrimensor/proprietario devera providenciar antes de confeccionar a planta e memoriais definitivos.
"""

# ----------------- INTERFACE GRÁFICA -----------------
# Imagem da logo exibida diretamente sem o título "Painel TSG"
logo_encontrada = obter_caminho_logo()
if logo_encontrada:
    st.sidebar.image(logo_encontrada, width=160)

model_name = st.sidebar.selectbox(
    "Modelo de IA",
    ["gemini-3.8-flash", "gemini-3.1-pro-preview"],
    index=0
)

if st.sidebar.button("Terminar Sessão"):
    st.session_state.autenticado = False
    st.rerun()

# Título Atualizado da Aplicação
st.title("AUDITOR TSG")
st.caption("Conferência prévia de peças técnicas completas OU auditoria registral isolada da matrícula.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Títulos Imobiliários (Obrigatório)")
    uploaded_matricula_mae = st.file_uploader(
        "Matrícula do Imóvel a Retificar (PDF/TXT) *",
        type=["pdf", "txt", "docx"],
        key="mat_mae"
    )
    uploaded_confrontantes = st.file_uploader(
        "Matrículas dos Confrontantes (Opcional)",
        type=["pdf", "txt", "docx"],
        accept_multiple_files=True,
        key="mat_confrontantes"
    )

with col2:
    st.subheader("2. Peças Técnicas (Opcional)")
    uploaded_memoriais = st.file_uploader(
        "Memorial Descritivo e Planta (Opcional)",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        key="memorial_planta"
    )
    uploaded_outros = st.file_uploader(
        "Requerimento, ART/TRT e Anuências (Opcional)",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        key="outros_docs"
    )

modo_completo = bool(uploaded_memoriais)
if uploaded_matricula_mae and not uploaded_memoriais:
    st.info("💡 **Modo Ativo: Auditoria Registral e Dominial da Matrícula Mãe**.")
elif uploaded_matricula_mae and uploaded_memoriais:
    st.success("📐 **Modo Ativo: Auditoria Cruzada Completa (Topografia + Registro)**.")

st.divider()

if st.button("🔍 Executar Auditoria TSG", type="primary", use_container_width=True):
    if not api_key:
        st.error("Chave de API não configurada no servidor. Verifique os Secrets.")
        st.stop()
    
    if not uploaded_matricula_mae:
        st.warning("É obrigatório carregar ao menos a Matrícula do Imóvel.")
        st.stop()

    prompt_sistema = PROMPT_AUDITORIA_COMPLETA if modo_completo else PROMPT_ANALISE_MATRICULA_ISOLADA
    instrucao_usuario = (
        "Realize a conferência prévia e o confronto rigoroso considerando os parâmetros estritos de análise (validando apenas os dados declarados nas peças técnicas, admitindo 1 coproprietário representante e desconsiderando firmas/reconhecimentos)."
        if modo_completo else
        "Realize a auditoria jurídica e registral profunda exclusivamente com base na matrícula apresentada, estruturando os diagnósticos de disponibilidade, continuidade e a tabela de confrontantes históricos com recomendações para a topografia."
    )

    client = genai.Client(api_key=api_key)

    with st.spinner("A processar documentos na infraestrutura protegida..."):
        uploaded_gemini_files = []
        temp_paths = []

        try:
            all_files = [uploaded_matricula_mae]
            if uploaded_memoriais:
                all_files.extend(uploaded_memoriais)
            if uploaded_confrontantes:
                all_files.extend(uploaded_confrontantes)
            if uploaded_outros:
                all_files.extend(uploaded_outros)

            for file in all_files:
                suffix = os.path.splitext(file.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(file.getvalue())
                    tmp_path = tmp.name
                    temp_paths.append(tmp_path)

                gemini_file = client.files.upload(
                    file=tmp_path,
                    config=types.UploadFileConfig(display_name=file.name)
                )
                uploaded_gemini_files.append(gemini_file)

            status_box = st.empty()
            status_box.info("A aguardar indexação dos ficheiros...")
            for gf in uploaded_gemini_files:
                arquivo_checado = client.files.get(name=gf.name)
                espera = 0
                while getattr(arquivo_checado, "state", None) and arquivo_checado.state.name == "PROCESSING":
                    time.sleep(2)
                    espera += 2
                    arquivo_checado = client.files.get(name=gf.name)
                    if espera >= 40:
                        break

            contents = [instrucao_usuario, *uploaded_gemini_files]
            status_box.info(f"A executar auditoria com o modelo {model_name}...")
            
            response = None
            for tentativa in range(1, 4):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=prompt_sistema,
                            temperature=0.2
                        )
                    )
                    break
                except Exception as err:
                    if tentativa < 3 and any(code in str(err) for code in ["503", "UNAVAILABLE", "500"]):
                        time.sleep(tentativa * 4)
                        continue
                    raise err

            status_box.empty()
            st.success("Auditoria TSG concluída com sucesso!")
            
            st.markdown("### Relatório de Auditoria TSG")
            st.markdown(response.text)

            pdf_bytes = exportar_para_pdf(response.text)

            st.download_button(
                label="📥 Descarregar Relatório Timbrado TSG em PDF",
                data=pdf_bytes,
                file_name="TSG_auditoria_rural.pdf",
                mime="application/pdf",
                type="primary"
            )

        except Exception as e:
            st.error(f"Erro durante o processamento: {str(e)}")

        finally:
            for p in temp_paths:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
            for gf in uploaded_gemini_files:
                try:
                    client.files.delete(name=gf.name)
                except Exception:
                    pass
