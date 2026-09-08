import streamlit as st
import pandas as pd
import io
import datetime
import plotly.graph_objects as go
import core_engine as engine

st.set_page_config(page_title="Base Comparável Dinâmica | IM", layout="wide", page_icon="📅")

# --- LOGO DA SEED NA BARRA LATERAL ---
URL_LOGO_SEED = "http://seeddigital.com.br/images/Logo%20Seed%20Registrado.jpg"
try:
    st.sidebar.image(URL_LOGO_SEED, use_container_width=True)
except Exception:
    pass

st.title("📅 Validador de Base Comparável (Campanhas & SSS)")
st.caption("Análise de Performance, Calendário Corporativo e Elegibilidade de Lojas")

# --- 1. VALIDAÇÃO DE ACESSO E-MAIL SEED ---
st.sidebar.header("🔑 Identificação do Analista")
usuario_input = st.sidebar.text_input("E-mail Corporativo:", placeholder="seu.nome@seeddigital.com.br").strip().lower()

if usuario_input:
    if usuario_input.endswith("@seeddigital.com.br") and usuario_input.count("@") == 1 and len(
            usuario_input.split("@")[0]) > 0:
        st.sidebar.caption(f"👤 Acessando como: **{usuario_input}**")
    else:
        st.sidebar.error("Login não autorizado")
        st.stop()
else:
    st.warning("👈 Por favor, informe seu e-mail corporativo no menu lateral para liberar o acesso ao sistema.")
    st.stop()

# --- LINK DA FONTE DE DADOS ---
st.sidebar.markdown("---")
st.sidebar.header("🔗 Fontes & Integrações")
URL_REPORT_SEED = "https://analytics.seeddigital.com.br/#s=/gdc/workspaces/ypz93j7xfq9jarggjdxrd47nydxocpzp|analysisPage|/gdc/md/ypz93j7xfq9jarggjdxrd47nydxocpzp/obj/27495056|/gdc/md/ypz93j7xfq9jarggjdxrd47nydxocpzp/obj/27495057|yui_3_14_1_1_1786992826869_155066"
st.sidebar.link_button("📊 Abrir Report de Exemplo (Seed Analytics)", URL_REPORT_SEED, use_container_width=True)

# --- 2. UPLOAD DE ARQUIVOS ---
st.sidebar.markdown("---")
st.sidebar.header("1. Upload de Arquivos")
uploaded_file = st.sidebar.file_uploader("Suba a base (CSV ou Excel)", type=["csv", "xlsx"])

if "uploaded_filename" in st.session_state and uploaded_file is not None:
    if st.session_state["uploaded_filename"] != uploaded_file.name:
        st.session_state.pop("res_data", None)
        st.session_state["uploaded_filename"] = uploaded_file.name
elif uploaded_file is not None:
    st.session_state["uploaded_filename"] = uploaded_file.name

if uploaded_file is not None:
    try:
        df_raw = engine.carregar_dados(uploaded_file, uploaded_file.name)
        cols = list(df_raw.columns)

        with st.sidebar.form(key="form_configuracao_completa"):
            st.header("2. Mapeamento de Colunas")
            col_id = st.selectbox("ID da Loja (Chave Única):", cols)
            col_nome = st.selectbox("Nome da Loja (Rótulo):", cols)
            col_data = st.selectbox("Coluna de Data:", cols)

            st.markdown("---")
            st.subheader("Métricas de Performance")

            opcoes_metricas = ["(Nenhum)"] + cols
            idx_fluxo = next((i for i, c in enumerate(opcoes_metricas) if "fluxo" in str(c).lower()), 0)
            idx_vendas = next(
                (i for i, c in enumerate(opcoes_metricas) if "venda" in str(c).lower() or "faturam" in str(c).lower()),
                0)
            idx_tickets = next((i for i, c in enumerate(opcoes_metricas) if
                                "ticket" in str(c).lower() or "transac" in str(c).lower() or "cupon" in str(c).lower()),
                               0)
            idx_pecas = next((i for i, c in enumerate(opcoes_metricas) if
                              "peca" in str(c).lower() or "produt" in str(c).lower() or "qtd" in str(
                                  c).lower() or "item" in str(c).lower()), 0)

            col_fluxo_sel = st.selectbox("Coluna de Fluxo / Pessoas:", opcoes_metricas, index=idx_fluxo)
            col_vendas_sel = st.selectbox("Coluna de Vendas / R$:", opcoes_metricas, index=idx_vendas)
            col_tickets_sel = st.selectbox("Coluna de Tickets / Qtd. Vendas:", opcoes_metricas, index=idx_tickets)
            col_pecas_sel = st.selectbox("Coluna de Peças / Produtos (p/ P.A.):", opcoes_metricas, index=idx_pecas)

            st.markdown("---")
            st.header("3. Granularidade do Relatório")
            tipo_visao = st.selectbox(
                "Visão dos Resultados:",
                ["Consolidado do Período", "Detalhamento Mês a Mês"]
            )

            st.markdown("---")
            st.header("4. Configuração do Calendário")
            dt_base_ini = st.date_input("Início Base", datetime.date(2025, 1, 1))
            dt_base_fim = st.date_input("Fim Base", datetime.date(2025, 7, 31))

            dt_atual_ini = st.date_input("Início Atual", datetime.date(2026, 1, 1))
            dt_atual_fim = st.date_input("Fim Atual", datetime.date(2026, 7, 31))

            st.markdown("---")
            st.header("5. Regras de Exclusão")
            ignorar_domingos = st.checkbox("Desconsiderar Domingos", value=True)
            ignorar_feriados = st.checkbox("Desconsiderar Feriados Nacionais", value=True)
            pct_corte = st.slider("Corte de Presença de Dados (%)", 50, 100, 82) / 100.0

            st.markdown("---")
            btn_processar = st.form_submit_button("🚀 Processar Análise", type="primary")

        if btn_processar:
            col_fluxo = None if col_fluxo_sel == "(Nenhum)" else col_fluxo_sel
            col_vendas = None if col_vendas_sel == "(Nenhum)" else col_vendas_sel
            col_tickets = None if col_tickets_sel == "(Nenhum)" else col_tickets_sel
            col_pecas = None if col_pecas_sel == "(Nenhum)" else col_pecas_sel

            if not col_fluxo and not col_vendas and not col_tickets and not col_pecas:
                st.error("⚠️ Selecione pelo menos uma métrica para análise.")
                st.stop()

            with st.spinner("Processando indicadores corporativos..."):
                df_clean = df_raw.copy()
                for c in [col_fluxo, col_vendas, col_tickets, col_pecas]:
                    if c:
                        df_clean[c] = pd.to_numeric(df_clean[c], errors='coerce').fillna(0)

                if tipo_visao == "Consolidado do Período":
                    res = engine.processar_base_comparavel_completa(
                        df=df_clean, col_id=col_id, col_nome=col_nome, col_data=col_data,
                        col_fluxo=col_fluxo, col_vendas=col_vendas, col_tickets=col_tickets, col_pecas=col_pecas,
                        dt_base_inicio=dt_base_ini, dt_base_fim=dt_base_fim,
                        dt_atual_inicio=dt_atual_ini, dt_atual_fim=dt_atual_fim,
                        pct_cobertura_min=pct_corte, ignorar_domingos=ignorar_domingos,
                        ignorar_feriados=ignorar_feriados
                    )
                    st.session_state["res_data"] = {
                        "tipo": "Consolidado", "res": res,
                        "col_fluxo": col_fluxo, "col_vendas": col_vendas, "col_tickets": col_tickets,
                        "col_pecas": col_pecas
                    }
                else:
                    res_m = engine.processar_base_comparavel_mensal_completa(
                        df=df_clean, col_id=col_id, col_nome=col_nome, col_data=col_data,
                        col_fluxo=col_fluxo, col_vendas=col_vendas, col_tickets=col_tickets, col_pecas=col_pecas,
                        dt_base_inicio=dt_base_ini, dt_base_fim=dt_base_fim,
                        dt_atual_inicio=dt_atual_ini, dt_atual_fim=dt_atual_fim,
                        pct_cobertura_min=pct_corte, ignorar_domingos=ignorar_domingos,
                        ignorar_feriados=ignorar_feriados
                    )
                    st.session_state["res_data"] = {
                        "tipo": "Mensal", "res_m": res_m,
                        "col_fluxo": col_fluxo, "col_vendas": col_vendas, "col_tickets": col_tickets,
                        "col_pecas": col_pecas
                    }

        # EXIBIÇÃO PERSISTENTE
        if "res_data" in st.session_state:
            data_cache = st.session_state["res_data"]
            col_fluxo = data_cache["col_fluxo"]
            col_vendas = data_cache["col_vendas"]
            col_tickets = data_cache["col_tickets"]
            col_pecas = data_cache["col_pecas"]

            # --- VISÃO CONSOLIDADA ---
            if data_cache["tipo"] == "Consolidado":
                res = data_cache["res"]
                k, df_resumo, df_auditoria = res["kpis"], res["df_resumo"], res["df_auditoria"]

                st.subheader("📌 Resumo Consolidado do Período")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Lojas Elegíveis", f"{k['total_lojas']} Lojas")
                if col_fluxo:
                    c2.metric("Evolução Fluxo (YoY)", f"{k['var_fluxo_total']:.2f}%",
                              f"Total: {k['tot_fluxo_atual']:,.0f}")
                if col_vendas:
                    c3.metric("Evolução Vendas (YoY)", f"{k['var_vendas_total']:.2f}%",
                              f"Total: R$ {k['tot_vendas_atual']:,.2f}")
                if col_fluxo and col_tickets:
                    c4.metric("Taxa de Conversão", f"{k['conv_total_atual']:.2f}%",
                              f"Var: {k['var_conv_pp']:+.2f} p.p.")
                if col_pecas and col_tickets:
                    c5.metric("P.A. (Peças/Ticket)", f"{k['pa_total_atual']:.2f}", f"Var: {k['var_pa_abs']:+.2f}")

                st.markdown("---")
                tab_ap, tab_rep = st.tabs(["📊 Performance por Loja", "⚠️ Auditoria de Exclusão"])

                with tab_ap:
                    df_disp = df_resumo.copy()
                    for col_c in df_disp.columns:
                        if "fluxo" in str(col_c).lower() or "ticket" in str(col_c).lower() or "pecas" in str(
                                col_c).lower():
                            if "YoY" not in str(col_c) and "Conv" not in str(col_c) and "PA_" not in str(col_c):
                                df_disp[col_c] = df_disp[col_c].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
                        elif "venda" in str(col_c).lower() or "tm_" in str(col_c).lower():
                            if "YoY" not in str(col_c):
                                df_disp[col_c] = df_disp[col_c].apply(
                                    lambda x: f"R$ {x:,.2f}" if pd.notnull(x) else "R$ 0.00")
                        if "YoY" in str(col_c) or "Conv_" in str(col_c):
                            df_disp[col_c] = df_disp[col_c].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "0.00%")
                        elif str(col_c) == "Var_Conv_pp":
                            df_disp[col_c] = df_disp[col_c].apply(
                                lambda x: f"{x:+.2f} p.p." if pd.notnull(x) else "0.00 p.p.")
                        elif "PA_" in str(col_c) or "Var_PA" in str(col_c):
                            df_disp[col_c] = df_disp[col_c].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "0.00")

                    st.dataframe(df_disp, use_container_width=True)

                with tab_rep:
                    if not df_auditoria.empty:
                        st.warning(f"Total de {len(df_auditoria)} lojas desconsideradas.")
                        st.dataframe(df_auditoria, use_container_width=True)
                    else:
                        st.success("🎉 Nenhuma loja foi excluída!")

                # EXPORTAÇÃO EXCEL CONSOLIDADO
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_resumo.to_excel(writer, sheet_name='Base_Comparavel', index=False)
                    if not df_auditoria.empty:
                        df_auditoria.to_excel(writer, sheet_name='Lojas_Excluidas', index=False)

                st.download_button(
                    label="📥 Exportar Relatório Consolidado (.xlsx)",
                    data=buffer.getvalue(), file_name="base_comparavel_consolidado.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            # --- VISÃO MÊS A MÊS ---
            else:
                res_m = data_cache["res_m"]
                df_tot = res_m["df_totais_mensais"].copy()
                df_lojas = res_m["df_evolucao_lojas"].copy()
                df_aud_m = res_m["df_auditoria_mensal"].copy()

                st.subheader("📊 Resumo Executivo Mês a Mês")

                df_tot_disp = df_tot.copy()
                df_tot_disp["Fluxo Atual"] = df_tot_disp["Fluxo Atual"].apply(lambda x: f"{x:,.0f}")
                df_tot_disp["Fluxo YoY (%)"] = df_tot_disp["Fluxo YoY (%)"].apply(lambda x: f"{x:.2f}%")
                df_tot_disp["Vendas Atual (R$)"] = df_tot_disp["Vendas Atual (R$)"].apply(lambda x: f"R$ {x:,.2f}")
                df_tot_disp["Vendas YoY (%)"] = df_tot_disp["Vendas YoY (%)"].apply(lambda x: f"{x:.2f}%")
                df_tot_disp["Conversão (%)"] = df_tot_disp["Conversão (%)"].apply(lambda x: f"{x:.2f}%")
                if "P.A. (Peças/Ticket)" in df_tot_disp.columns:
                    df_tot_disp["P.A. (Peças/Ticket)"] = df_tot_disp["P.A. (Peças/Ticket)"].apply(lambda x: f"{x:.2f}")

                st.dataframe(df_tot_disp, use_container_width=True)

                # 🎨 FORMULÁRIO DE CUSTOMIZAÇÃO RÁPIDA (COM BOTÃO OK)
                st.markdown("---")
                with st.expander("🎨 Customizar Estilo e Cores do Gráfico (Sem recarregar dados)", expanded=False):
                    with st.form(key="form_estilo_grafico"):
                        c_style1, c_style2, c_style3, c_style4 = st.columns(4)

                        with c_style1:
                            tipo_grafico = st.selectbox("Formato do Gráfico:",
                                                        ["Linhas", "Colunas (Barras Verticais)", "Área Preenchida",
                                                         "Barras Horizontais"])
                        with c_style2:
                            estilo_linha = st.selectbox("Formato das Linhas:",
                                                        ["Suavizadas (Curvas)", "Retas (Angulares)"])
                        with c_style3:
                            fundo_grafico = st.selectbox("Fundo do Gráfico:",
                                                         ["Transparente", "Escuro Corporativo", "Claro (Clean)"])
                        with c_style4:
                            mostrar_rotulo = st.checkbox("Exibir Rótulos de Dados", value=True)

                        st.caption("Ajuste as cores individuais das métricas:")
                        c_color1, c_color2, c_color3, c_color4 = st.columns(4)
                        with c_color1:
                            cor_vendas = st.color_picker("Cor Vendas YoY (%)", "#2E7D32")
                        with c_color2:
                            cor_fluxo = st.color_picker("Cor Fluxo YoY (%)", "#1E88E5")
                        with c_color3:
                            cor_conv = st.color_picker("Cor Conversão (%)", "#FB8C00")
                        with c_color4:
                            cor_pa = st.color_picker("Cor P.A. (Peças/Ticket)", "#8E24AA")

                        btn_aplicar_estilo = st.form_submit_button("🎨 Aplicar Estilo ao Gráfico", type="secondary")

                # VALORES DE CONFIGURAÇÃO PADRÃO (SE O FORM NÃO FOR CLICADO)
                if "tipo_grafico" not in locals():
                    tipo_grafico, estilo_linha, fundo_grafico, mostrar_rotulo = "Linhas", "Suavizadas (Curvas)", "Transparente", True
                    cor_vendas, cor_fluxo, cor_conv, cor_pa = "#2E7D32", "#1E88E5", "#FB8C00", "#8E24AA"

                fig = go.Figure()
                shape_line = 'spline' if estilo_linha == "Suavizadas (Curvas)" else 'linear'

                if fundo_grafico == "Transparente":
                    paper_bg, plot_bg = "rgba(0,0,0,0)", "rgba(0,0,0,0)"
                    template_theme = "plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white"
                elif fundo_grafico == "Escuro Corporativo":
                    paper_bg, plot_bg = "#111827", "#1F2937"
                    template_theme = "plotly_dark"
                else:
                    paper_bg, plot_bg = "#FFFFFF", "#F9FAFB"
                    template_theme = "plotly_white"

                # TRACE VENDAS YOY
                if col_vendas and "Vendas YoY (%)" in df_tot.columns:
                    if tipo_grafico == "Linhas":
                        fig.add_trace(go.Scatter(x=df_tot["Mes"], y=df_tot["Vendas YoY (%)"], mode='lines+markers+text',
                                                 name='Vendas YoY (%)',
                                                 line=dict(color=cor_vendas, width=3, shape=shape_line),
                                                 text=[f"{val:.2f}%" for val in
                                                       df_tot["Vendas YoY (%)"]] if mostrar_rotulo else None,
                                                 textposition="top center"))
                    elif tipo_grafico == "Colunas (Barras Verticais)":
                        fig.add_trace(go.Bar(x=df_tot["Mes"], y=df_tot["Vendas YoY (%)"], marker_color=cor_vendas,
                                             name='Vendas YoY (%)', text=[f"{val:.2f}%" for val in df_tot[
                                "Vendas YoY (%)"]] if mostrar_rotulo else None, textposition="auto"))
                    elif tipo_grafico == "Área Preenchida":
                        fig.add_trace(go.Scatter(x=df_tot["Mes"], y=df_tot["Vendas YoY (%)"], fill='tozeroy',
                                                 mode='lines+markers+text', name='Vendas YoY (%)',
                                                 line=dict(color=cor_vendas, width=3, shape=shape_line),
                                                 text=[f"{val:.2f}%" for val in
                                                       df_tot["Vendas YoY (%)"]] if mostrar_rotulo else None,
                                                 textposition="top center"))

                # TRACE FLUXO YOY
                if col_fluxo and "Fluxo YoY (%)" in df_tot.columns:
                    if tipo_grafico == "Linhas":
                        fig.add_trace(go.Scatter(x=df_tot["Mes"], y=df_tot["Fluxo YoY (%)"], mode='lines+markers+text',
                                                 name='Fluxo YoY (%)',
                                                 line=dict(color=cor_fluxo, width=3, shape=shape_line),
                                                 text=[f"{val:.2f}%" for val in
                                                       df_tot["Fluxo YoY (%)"]] if mostrar_rotulo else None,
                                                 textposition="top center"))
                    elif tipo_grafico == "Colunas (Barras Verticais)":
                        fig.add_trace(go.Bar(x=df_tot["Mes"], y=df_tot["Fluxo YoY (%)"], marker_color=cor_fluxo,
                                             name='Fluxo YoY (%)', text=[f"{val:.2f}%" for val in df_tot[
                                "Fluxo YoY (%)"]] if mostrar_rotulo else None, textposition="auto"))
                    elif tipo_grafico == "Área Preenchida":
                        fig.add_trace(go.Scatter(x=df_tot["Mes"], y=df_tot["Fluxo YoY (%)"], fill='tozeroy',
                                                 mode='lines+markers+text', name='Fluxo YoY (%)',
                                                 line=dict(color=cor_fluxo, width=3, shape=shape_line),
                                                 text=[f"{val:.2f}%" for val in
                                                       df_tot["Fluxo YoY (%)"]] if mostrar_rotulo else None,
                                                 textposition="top center"))

                # TRACE CONVERSÃO %
                if col_fluxo and col_tickets and "Conversão (%)" in df_tot.columns:
                    if tipo_grafico == "Linhas":
                        fig.add_trace(go.Scatter(x=df_tot["Mes"], y=df_tot["Conversão (%)"], mode='lines+markers+text',
                                                 name='Conversão (%)',
                                                 line=dict(color=cor_conv, width=3, shape=shape_line),
                                                 text=[f"{val:.2f}%" for val in
                                                       df_tot["Conversão (%)"]] if mostrar_rotulo else None,
                                                 textposition="top center"))
                    elif tipo_grafico == "Colunas (Barras Verticais)":
                        fig.add_trace(go.Bar(x=df_tot["Mes"], y=df_tot["Conversão (%)"], marker_color=cor_conv,
                                             name='Conversão (%)', text=[f"{val:.2f}%" for val in df_tot[
                                "Conversão (%)"]] if mostrar_rotulo else None, textposition="auto"))
                    elif tipo_grafico == "Área Preenchida":
                        fig.add_trace(go.Scatter(x=df_tot["Mes"], y=df_tot["Conversão (%)"], fill='tozeroy',
                                                 mode='lines+markers+text', name='Conversão (%)',
                                                 line=dict(color=cor_conv, width=3, shape=shape_line),
                                                 text=[f"{val:.2f}%" for val in
                                                       df_tot["Conversão (%)"]] if mostrar_rotulo else None,
                                                 textposition="top center"))

                # TRACE P.A.
                if col_pecas and col_tickets and "P.A. (Peças/Ticket)" in df_tot.columns:
                    if tipo_grafico == "Linhas":
                        fig.add_trace(
                            go.Scatter(x=df_tot["Mes"], y=df_tot["P.A. (Peças/Ticket)"], mode='lines+markers+text',
                                       name='P.A. (Peças/Ticket)', line=dict(color=cor_pa, width=3, shape=shape_line),
                                       text=[f"{val:.2f}" for val in
                                             df_tot["P.A. (Peças/Ticket)"]] if mostrar_rotulo else None,
                                       textposition="top center"))
                    elif tipo_grafico == "Colunas (Barras Verticais)":
                        fig.add_trace(go.Bar(x=df_tot["Mes"], y=df_tot["P.A. (Peças/Ticket)"], marker_color=cor_pa,
                                             name='P.A. (Peças/Ticket)', text=[f"{val:.2f}" for val in df_tot[
                                "P.A. (Peças/Ticket)"]] if mostrar_rotulo else None, textposition="auto"))

                fig.update_layout(
                    title="Comparativo Mês a Mês (Clique na legenda para ocultar/exibir)",
                    xaxis_title="Mês de Referência",
                    yaxis_title="Percentual (%) / Valor",
                    template=template_theme,
                    paper_bgcolor=paper_bg,
                    plot_bgcolor=plot_bg,
                    height=480,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=20, r=20, t=60, b=20)
                )

                st.plotly_chart(fig, use_container_width=True)

                st.markdown("---")
                tab_m_ap, tab_m_rep = st.tabs(["📋 Evolução por Loja (Mês a Mês)", "⚠️ Auditoria Mensal"])

                with tab_m_ap:
                    for c in df_lojas.columns:
                        if "Var_" in c or "Conv_" in c:
                            df_lojas[c] = df_lojas[c].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "0.00%")
                        elif "PA_" in c:
                            df_lojas[c] = df_lojas[c].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "0.00")
                    st.dataframe(df_lojas, use_container_width=True)

                with tab_m_rep:
                    if not df_aud_m.empty:
                        st.warning("Lojas excluídas em cada competência mensal:")
                        st.dataframe(df_aud_m, use_container_width=True)
                    else:
                        st.success("🎉 Nenhuma loja excluída em nenhum dos meses!")

                # EXPORTAÇÃO EXCEL MENSAL
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_tot.to_excel(writer, sheet_name='Totais_Mensais', index=False)
                    df_lojas.to_excel(writer, sheet_name='Evolucao_Lojas', index=False)
                    if not df_aud_m.empty:
                        df_aud_m.to_excel(writer, sheet_name='Lojas_Excluidas_Mensal', index=False)

                st.download_button(
                    label="📥 Exportar Relatório Mensal (.xlsx)",
                    data=buffer.getvalue(), file_name="base_comparavel_mensal.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("👈 Mapeie os campos no menu lateral e clique em **🚀 Processar Análise**.")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
else:
    st.info("Aguardando upload da base no menu lateral.")