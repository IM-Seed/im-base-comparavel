import streamlit as st
import pandas as pd
import io
import datetime
import core_engine as engine

st.set_page_config(page_title="Base Comparável Dinâmica | IM", layout="wide", page_icon="📅")

URL_LOGO_SEED = "http://seeddigital.com.br/images/Logo%20Seed%20Registrado.jpg"
try:
    st.sidebar.image(URL_LOGO_SEED, use_container_width=True)
except Exception:
    pass

st.title("📅 Validador de Base Comparável (Campanhas & SSS)")
st.caption("Análise de Performance, Calendário Corporativo e Elegibilidade de Lojas")

# 1. VALIDAÇÃO DE ACESSO
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

# 2. UPLOAD DE ARQUIVOS
st.sidebar.markdown("---")
st.sidebar.header("1. Upload de Arquivos")
uploaded_file = st.sidebar.file_uploader("Suba a base (CSV ou Excel)", type=["csv", "xlsx"])

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

            col_fluxo_sel = st.selectbox("Coluna de Fluxo / Pessoas:", opcoes_metricas, index=idx_fluxo)
            col_vendas_sel = st.selectbox("Coluna de Vendas / R$:", opcoes_metricas, index=idx_vendas)
            col_tickets_sel = st.selectbox("Coluna de Tickets / Qtd. Vendas:", opcoes_metricas, index=idx_tickets)

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

            if not col_fluxo and not col_vendas and not col_tickets:
                st.error("⚠️ Selecione pelo menos uma métrica (Fluxo, Vendas ou Tickets).")
                st.stop()

            with st.spinner("Processando indicadores corporativos..."):
                df_clean = df_raw.copy()
                for c in [col_fluxo, col_vendas, col_tickets]:
                    if c:
                        df_clean[c] = pd.to_numeric(df_clean[c], errors='coerce').fillna(0)

                # OPÇÃO 1: VISÃO CONSOLIDADA DO PERÍODO
                if tipo_visao == "Consolidado do Período":
                    res = engine.processar_base_comparavel_completa(
                        df=df_clean, col_id=col_id, col_nome=col_nome, col_data=col_data,
                        col_fluxo=col_fluxo, col_vendas=col_vendas, col_tickets=col_tickets,
                        dt_base_inicio=dt_base_ini, dt_base_fim=dt_base_fim,
                        dt_atual_inicio=dt_atual_ini, dt_atual_fim=dt_atual_fim,
                        pct_cobertura_min=pct_corte, ignorar_domingos=ignorar_domingos,
                        ignorar_feriados=ignorar_feriados
                    )
                    k, df_resumo, df_auditoria = res["kpis"], res["df_resumo"], res["df_auditoria"]

                    st.subheader("📌 Resumo Consolidado do Período")
                    c1, c2, c3, c4 = st.columns(4)
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
                    elif col_tickets:
                        c4.metric("Qtd. Tickets (YoY)", f"{k['var_tick_total']:.2f}%",
                                  f"Total: {k['tot_tick_atual']:,.0f}")

                    st.markdown("---")
                    tab_ap, tab_rep = st.tabs(["📊 Performance por Loja", "⚠️ Auditoria de Exclusão"])

                    with tab_ap:
                        df_disp = df_resumo.copy()
                        for col_c in df_disp.columns:
                            if "fluxo" in str(col_c).lower() or "ticket" in str(col_c).lower():
                                if "YoY" not in str(col_c) and "Conv" not in str(col_c):
                                    df_disp[col_c] = df_disp[col_c].apply(
                                        lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
                            elif "venda" in str(col_c).lower() or "tm_" in str(col_c).lower():
                                if "YoY" not in str(col_c):
                                    df_disp[col_c] = df_disp[col_c].apply(
                                        lambda x: f"R$ {x:,.2f}" if pd.notnull(x) else "R$ 0.00")
                            if "YoY" in str(col_c) or "Conv_" in str(col_c):
                                df_disp[col_c] = df_disp[col_c].apply(
                                    lambda x: f"{x:.2f}%" if pd.notnull(x) else "0.00%")
                            elif str(col_c) == "Var_Conv_pp":
                                df_disp[col_c] = df_disp[col_c].apply(
                                    lambda x: f"{x:+.2f} p.p." if pd.notnull(x) else "0.00 p.p.")

                        st.dataframe(df_disp, use_container_width=True)

                    with tab_rep:
                        if not df_auditoria.empty:
                            st.warning(f"Total de {len(df_auditoria)} lojas desconsideradas.")
                            st.dataframe(df_auditoria, use_container_width=True)
                        else:
                            st.success("🎉 Nenhuma loja foi excluída!")

                # OPÇÃO 2: DETALHAMENTO MÊS A MÊS
                else:
                    res_m = engine.processar_base_comparavel_mensal_completa(
                        df=df_clean, col_id=col_id, col_nome=col_nome, col_data=col_data,
                        col_fluxo=col_fluxo, col_vendas=col_vendas, col_tickets=col_tickets,
                        dt_base_inicio=dt_base_ini, dt_base_fim=dt_base_fim,
                        dt_atual_inicio=dt_atual_ini, dt_atual_fim=dt_atual_fim,
                        pct_cobertura_min=pct_corte, ignorar_domingos=ignorar_domingos,
                        ignorar_feriados=ignorar_feriados
                    )

                    df_tot = res_m["df_totais_mensais"].copy()
                    df_lojas = res_m["df_evolucao_lojas"].copy()
                    df_aud_m = res_m["df_auditoria_mensal"].copy()

                    st.subheader("📊 Resumo Executivo Mês a Mês")

                    # Formatação dos totais da rede
                    df_tot_disp = df_tot.copy()
                    df_tot_disp["Fluxo Atual"] = df_tot_disp["Fluxo Atual"].apply(lambda x: f"{x:,.0f}")
                    df_tot_disp["Fluxo YoY (%)"] = df_tot_disp["Fluxo YoY (%)"].apply(lambda x: f"{x:.2f}%")
                    df_tot_disp["Vendas Atual (R$)"] = df_tot_disp["Vendas Atual (R$)"].apply(lambda x: f"R$ {x:,.2f}")
                    df_tot_disp["Vendas YoY (%)"] = df_tot_disp["Vendas YoY (%)"].apply(lambda x: f"{x:.2f}%")
                    df_tot_disp["Conversão (%)"] = df_tot_disp["Conversão (%)"].apply(lambda x: f"{x:.2f}%")

                    st.dataframe(df_tot_disp, use_container_width=True)

                    # Gráfico de tendência
                    if col_vendas and col_fluxo:
                        st.line_chart(df_tot.set_index("Mes")[["Vendas YoY (%)", "Fluxo YoY (%)"]])
                    elif col_vendas:
                        st.line_chart(df_tot.set_index("Mes")[["Vendas YoY (%)"]])
                    elif col_fluxo:
                        st.line_chart(df_tot.set_index("Mes")[["Fluxo YoY (%)"]])

                    st.markdown("---")
                    tab_m_ap, tab_m_rep = st.tabs(["📋 Evolução por Loja (Mês a Mês)", "⚠️ Auditoria Mensal"])

                    with tab_m_ap:
                        # Formatação visual das colunas de evolução mensal
                        for c in df_lojas.columns:
                            if "Var_" in c or "Conv_" in c:
                                df_lojas[c] = df_lojas[c].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "0.00%")
                        st.dataframe(df_lojas, use_container_width=True)

                    with tab_m_rep:
                        if not df_aud_m.empty:
                            st.warning("Lojas excluídas em cada competência mensal:")
                            st.dataframe(df_aud_m, use_container_width=True)
                        else:
                            st.success("🎉 Nenhuma loja excluída em nenhum dos meses!")

                # EXPORTAÇÃO EXCEL
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    if tipo_visao == "Consolidado do Período":
                        df_resumo.to_excel(writer, sheet_name='Base_Comparavel', index=False)
                        if not df_auditoria.empty:
                            df_auditoria.to_excel(writer, sheet_name='Lojas_Excluidas', index=False)
                    else:
                        df_tot.to_excel(writer, sheet_name='Totais_Mensais', index=False)
                        df_lojas.to_excel(writer, sheet_name='Evolucao_Lojas', index=False)
                        if not df_aud_m.empty:
                            df_aud_m.to_excel(writer, sheet_name='Lojas_Excluidas_Mensal', index=False)

                st.download_button(
                    label="📥 Exportar Relatório (.xlsx)",
                    data=buffer.getvalue(),
                    file_name="base_comparavel.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("👈 Mapeie os campos no menu lateral e clique em **🚀 Processar Análise**.")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
else:
    st.info("Aguardando upload da base no menu lateral.")