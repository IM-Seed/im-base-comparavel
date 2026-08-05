import streamlit as st
import pandas as pd
import io
import datetime
import core_engine as engine

st.set_page_config(page_title="Base Comparável Dinâmica | IM", layout="wide", page_icon="📅")

# --- LOGO DA SEED NA BARRA LATERAL ---
URL_LOGO_SEED = "http://seeddigital.com.br/images/Logo%20Seed%20Registrado.jpg"

try:
    st.sidebar.image(URL_LOGO_SEED, use_container_width=True)
except Exception:
    pass

st.title("📅 Validador de Base Comparável por Calendário (Campanhas & SSS)")
st.caption("Ferramenta Interna de Insights & Market Intelligence")

# --- REGISTRO DE IDENTIFICAÇÃO DO USUÁRIO ---
st.sidebar.header("🔑 Identificação do Usuário")
user_email = st.sidebar.text_input("E-mail do Analista (IM):", placeholder="seu.nome@empresa.com.br")

if not user_email or "@" not in user_email:
    st.warning("👈 Por favor, informe seu e-mail corporativo no menu lateral para liberar o acesso ao sistema.")
    st.stop()  # Interrompe a execução até que o e-mail seja informado

# 1. UPLOAD DE ARQUIVOS
st.sidebar.markdown("---")
st.sidebar.header("1. Upload de Arquivos")
uploaded_file = st.sidebar.file_uploader("Suba a base (CSV ou Excel)", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        df_raw = engine.carregar_dados(uploaded_file, uploaded_file.name)
        cols = list(df_raw.columns)

        # 2. PARÂMETROS
        with st.sidebar.form(key="form_parametros"):
            st.header("2. Mapeamento de Colunas")
            col_id = st.selectbox("ID da Loja (Chave Única):", cols)
            col_nome = st.selectbox("Nome da Loja (Rótulo):", cols)
            col_data = st.selectbox("Coluna de Data:", cols)
            col_metrica = st.selectbox("Métrica (Coluna de Dados):", cols)

            tipo_metrica = st.radio(
                "Tipo de Métrica:",
                ["Fluxo / Volume (Número Inteiro)", "Faturamento / Vendas (R$)"]
            )

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
            btn_processar = st.form_submit_button("🚀 Processar Base Comparável", type="primary")

        if btn_processar:
            # REGISTRO DO LOG NO CONSOLE/SERVIDOR
            data_hora_acesso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"[LOG ACESSO] {data_hora_acesso} | Usuário: {user_email} | Arquivo: {uploaded_file.name} | Visão: {tipo_visao}")

            with st.spinner("Processando dados e aplicando regras de elegibilidade..."):

                if tipo_metrica == "Faturamento / Vendas (R$)":
                    fmt_moeda = "R$ {:,.2f}"
                    fmt_total = "R$ {:,.2f}"
                    fmt_tabela_valor = "{:,.2f}"
                else:
                    fmt_moeda = "{:,.0f}"
                    fmt_total = "{:,.0f}"
                    fmt_tabela_valor = "{:,.0f}"

                # VISÃO CONSOLIDADA
                if tipo_visao == "Consolidado do Período":
                    res = engine.processar_base_comparavel(
                        df=df_raw, col_id=col_id, col_nome=col_nome, col_data=col_data, col_metrica=col_metrica,
                        dt_base_inicio=dt_base_ini, dt_base_fim=dt_base_fim,
                        dt_atual_inicio=dt_atual_ini, dt_atual_fim=dt_atual_fim,
                        pct_cobertura_min=pct_corte,
                        ignorar_domingos=ignorar_domingos, ignorar_feriados=ignorar_feriados
                    )
                    k = res["kpis"]
                    df_resumo = res["df_resumo"]
                    df_auditoria = res["df_auditoria"]

                    st.subheader("📌 Resumo Consolidado do Período")
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Lojas Elegíveis", f"{k['total_lojas_comparaveis']} Lojas")
                    m2.metric(f"Base: {k['label_base']}", f"{k['dias_esperados_base']} dias úteis",
                              f"SLA {pct_corte * 100:.0f}%: {k['dias_minimos_base']} dias")
                    m3.metric(f"Atual: {k['label_atual']}", f"{k['dias_esperados_atual']} dias úteis",
                              f"SLA {pct_corte * 100:.0f}%: {k['dias_minimos_atual']} dias")
                    m4.metric("Crescimento YoY (SSS)", f"{k['var_pct_total']:.2f}%",
                              f"Total Atual: {fmt_total.format(k['tot_atual'])}")

                    st.markdown("---")

                    tab_aprovadas, tab_reprovadas = st.tabs(
                        ["✅ Lojas Comparáveis (Aprovadas)", "⚠️ Auditoria de Exclusão (Motivo da Reprovação)"])

                    with tab_aprovadas:
                        st.dataframe(
                            df_resumo.style.format({
                                "Valor_Periodo_Base": fmt_tabela_valor,
                                "Valor_Periodo_Atual": fmt_tabela_valor,
                                "Var_Abs_YoY": fmt_tabela_valor,
                                "Var_Pct_YoY": "{:.2f}%"
                            }),
                            use_container_width=True
                        )

                    with tab_reprovadas:
                        if not df_auditoria.empty:
                            st.warning(f"Total de {len(df_auditoria)} lojas desconsideradas da base comparável.")
                            st.dataframe(df_auditoria, use_container_width=True)
                        else:
                            st.success("🎉 Nenhuma loja foi excluída! Todas cumpriram a meta de dias ativos.")

                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_resumo.to_excel(writer, sheet_name='Consolidado_Aprovadas', index=False)
                        if not df_auditoria.empty:
                            df_auditoria.to_excel(writer, sheet_name='Auditoria_Exclusoes', index=False)

                    st.download_button(
                        label="📥 Exportar Consolidado (.xlsx)",
                        data=buffer.getvalue(),
                        file_name="base_comparavel_consolidada.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                # VISÃO MÊS A MÊS
                else:
                    res_m = engine.processar_base_comparavel_mensal(
                        df=df_raw, col_id=col_id, col_nome=col_nome, col_data=col_data, col_metrica=col_metrica,
                        dt_base_inicio=dt_base_ini, dt_base_fim=dt_base_fim,
                        dt_atual_inicio=dt_atual_ini, dt_atual_fim=dt_atual_fim,
                        pct_cobertura_min=pct_corte,
                        ignorar_domingos=ignorar_domingos, ignorar_feriados=ignorar_feriados
                    )

                    df_totais = res_m["df_totais_mensais"]
                    df_aud_mensal = res_m["df_auditoria_mensal"]

                    st.subheader("📊 Resumo Executivo Mês a Mês")
                    st.dataframe(
                        df_totais.style.format({
                            "Total Base": fmt_moeda,
                            "Total Atual": fmt_moeda,
                            "YoY (%)": "{:.2f}%"
                        }),
                        use_container_width=True
                    )

                    st.markdown("#### 📈 Evolução do Crescimento YoY (%) no Tempo")
                    chart_data = df_totais.set_index("Mes")[["YoY (%)"]]
                    st.line_chart(chart_data)

                    st.markdown("---")

                    tab_m_aprovadas, tab_m_reprovadas = st.tabs(
                        ["📋 Evolução por Loja (Aprovadas)", "⚠️ Auditoria de Exclusão Mensal"])

                    with tab_m_aprovadas:
                        df_lojas = res_m["df_evolucao_lojas"].copy()
                        format_dict = {}
                        for col in df_lojas.columns:
                            if col.startswith("YoY_"):
                                format_dict[col] = "{:.2f}%"
                            elif col.startswith(("Base_", "Atual_")):
                                format_dict[col] = fmt_tabela_valor

                        st.dataframe(
                            df_lojas.style.format(format_dict),
                            use_container_width=True
                        )

                    with tab_m_reprovadas:
                        if not df_aud_mensal.empty:
                            st.warning(
                                "Detalhamento de lojas e meses em que houve descumprimento do SLA de dados (abaixo de 82%):")
                            st.dataframe(df_aud_mensal, use_container_width=True)
                        else:
                            st.success("🎉 Todas as lojas cumpriram a meta em todos os meses!")

                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_totais.to_excel(writer, sheet_name='Resumo_Mensal', index=False)
                        res_m["df_evolucao_lojas"].to_excel(writer, sheet_name='Evolucao_Lojas', index=False)
                        if not df_aud_mensal.empty:
                            df_aud_mensal.to_excel(writer, sheet_name='Auditoria_Exclusoes_Mensal', index=False)

                    st.download_button(
                        label="📥 Exportar Detalhamento Mês a Mês (.xlsx)",
                        data=buffer.getvalue(),
                        file_name="base_comparavel_mes_a_mes.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        else:
            st.info("👈 Selecione o tipo de métrica, ajuste os parâmetros e clique em **🚀 Processar Base Comparável**.")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
else:
    st.info("Aguardando upload da base no menu lateral.")