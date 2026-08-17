import pandas as pd
import numpy as np
import datetime

FERIADOS_NACIONAIS = [
    "2025-01-01", "2025-04-18", "2025-04-21", "2025-05-01", "2025-09-07", "2025-10-12", "2025-11-02", "2025-11-15",
    "2025-11-20", "2025-12-25",
    "2026-01-01", "2026-04-03", "2026-04-21", "2026-05-01", "2026-09-07", "2026-10-12", "2026-11-02", "2026-11-15",
    "2026-11-20", "2026-12-25",
]


def carregar_dados(file_stream, filename: str) -> pd.DataFrame:
    if filename.endswith('.csv'):
        df = pd.read_csv(file_stream)
    elif filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_stream)
    else:
        raise ValueError("Formato não suportado. Utilize arquivos CSV ou Excel.")
    return df


def filtrar_dias_operacionais(df: pd.DataFrame, col_data: str, ignorar_domingos: bool = True,
                              ignorar_feriados: bool = True) -> pd.DataFrame:
    df_filtered = df.copy()
    df_filtered[col_data] = pd.to_datetime(df_filtered[col_data])

    if ignorar_domingos:
        df_filtered = df_filtered[df_filtered[col_data].dt.dayofweek != 6]

    if ignorar_feriados:
        feriados_dt = pd.to_datetime(FERIADOS_NACIONAIS)
        df_filtered = df_filtered[~df_filtered[col_data].dt.floor('D').isin(feriados_dt)]

    return df_filtered


def obter_dias_operacionais_intervalo(dt_inicio: datetime.date, dt_fim: datetime.date, ignorar_domingos: bool,
                                      ignorar_feriados: bool) -> int:
    datas = pd.date_range(start=dt_inicio, end=dt_fim)
    df_dias = pd.DataFrame({'data': datas})

    if ignorar_domingos:
        df_dias = df_dias[df_dias['data'].dt.dayofweek != 6]
    if ignorar_feriados:
        feriados_dt = pd.to_datetime(FERIADOS_NACIONAIS)
        df_dias = df_dias[~df_dias['data'].dt.floor('D').isin(feriados_dt)]

    return len(df_dias)


# --- 1. PROCESSAMENTO CONSOLIDADO COMPLETO ---
def processar_base_comparavel_completa(
        df: pd.DataFrame, col_id: str, col_nome: str, col_data: str,
        col_fluxo: str, col_vendas: str, col_tickets: str,
        dt_base_inicio: datetime.date, dt_base_fim: datetime.date,
        dt_atual_inicio: datetime.date, dt_atual_fim: datetime.date,
        pct_cobertura_min: float = 0.82, ignorar_domingos: bool = True, ignorar_feriados: bool = True
) -> dict:
    df_work = df.copy()
    df_work[col_data] = pd.to_datetime(df_work[col_data])
    df_operacional = filtrar_dias_operacionais(df_work, col_data, ignorar_domingos, ignorar_feriados)

    dias_esperados_base = obter_dias_operacionais_intervalo(dt_base_inicio, dt_base_fim, ignorar_domingos,
                                                            ignorar_feriados)
    dias_esperados_atual = obter_dias_operacionais_intervalo(dt_atual_inicio, dt_atual_fim, ignorar_domingos,
                                                             ignorar_feriados)

    dias_minimos_base = int(np.ceil(dias_esperados_base * pct_cobertura_min))
    dias_minimos_atual = int(np.ceil(dias_esperados_atual * pct_cobertura_min))

    dt_b_start, dt_b_end = pd.to_datetime(dt_base_inicio), pd.to_datetime(dt_base_fim)
    dt_a_start, dt_a_end = pd.to_datetime(dt_atual_inicio), pd.to_datetime(dt_atual_fim)

    df_base = df_operacional[(df_operacional[col_data] >= dt_b_start) & (df_operacional[col_data] <= dt_b_end)]
    df_atual = df_operacional[(df_operacional[col_data] >= dt_a_start) & (df_operacional[col_data] <= dt_a_end)]

    dias_loja_base = df_base.groupby(col_id)[col_data].apply(lambda x: x.dt.date.nunique())
    dias_loja_atual = df_atual.groupby(col_id)[col_data].apply(lambda x: x.dt.date.nunique())

    lojas_ok_base = set(dias_loja_base[dias_loja_base >= dias_minimos_base].index)
    lojas_ok_atual = set(dias_loja_atual[dias_loja_atual >= dias_minimos_atual].index)
    lojas_elegiveis = lojas_ok_base.intersection(lojas_ok_atual)

    todas_lojas = df_work[[col_id, col_nome]].drop_duplicates()
    auditoria = []
    for _, row in todas_lojas.iterrows():
        l_id, l_nome = row[col_id], row[col_nome]
        d_base, d_atual = dias_loja_base.get(l_id, 0), dias_loja_atual.get(l_id, 0)
        if d_base < dias_minimos_base or d_atual < dias_minimos_atual:
            auditoria.append({col_id: l_id, col_nome: l_nome, "Dias Base": f"{d_base}/{dias_esperados_base}",
                              "Dias Atual": f"{d_atual}/{dias_esperados_atual}"})
    df_auditoria = pd.DataFrame(auditoria)

    df_comp_base = df_base[df_base[col_id].isin(lojas_elegiveis)]
    df_comp_atual = df_atual[df_atual[col_id].isin(lojas_elegiveis)]

    cols_met = [c for c in [col_fluxo, col_vendas, col_tickets] if c is not None]

    grp_base = df_comp_base.groupby([col_id, col_nome])[cols_met].sum().reset_index()
    grp_atual = df_comp_atual.groupby([col_id, col_nome])[cols_met].sum().reset_index()

    df_resumo = pd.merge(grp_base, grp_atual, on=[col_id, col_nome], suffixes=('_base', '_atual'), how='outer').fillna(
        0)

    if col_fluxo:
        df_resumo['Var_Fluxo_YoY (%)'] = np.where(df_resumo[f"{col_fluxo}_base"] > 0, (
                    (df_resumo[f"{col_fluxo}_atual"] - df_resumo[f"{col_fluxo}_base"]) / df_resumo[
                f"{col_fluxo}_base"]) * 100, 0.0)
    if col_vendas:
        df_resumo['Var_Vendas_YoY (%)'] = np.where(df_resumo[f"{col_vendas}_base"] > 0, (
                    (df_resumo[f"{col_vendas}_atual"] - df_resumo[f"{col_vendas}_base"]) / df_resumo[
                f"{col_vendas}_base"]) * 100, 0.0)
    if col_tickets:
        df_resumo['Var_Tickets_YoY (%)'] = np.where(df_resumo[f"{col_tickets}_base"] > 0, (
                    (df_resumo[f"{col_tickets}_atual"] - df_resumo[f"{col_tickets}_base"]) / df_resumo[
                f"{col_tickets}_base"]) * 100, 0.0)

    if col_fluxo and col_tickets:
        df_resumo['Conv_Base (%)'] = np.where(df_resumo[f"{col_fluxo}_base"] > 0,
                                              (df_resumo[f"{col_tickets}_base"] / df_resumo[f"{col_fluxo}_base"]) * 100,
                                              0.0)
        df_resumo['Conv_Atual (%)'] = np.where(df_resumo[f"{col_fluxo}_atual"] > 0, (
                    df_resumo[f"{col_tickets}_atual"] / df_resumo[f"{col_fluxo}_atual"]) * 100, 0.0)
        df_resumo['Var_Conv_pp'] = df_resumo['Conv_Atual (%)'] - df_resumo['Conv_Base (%)']

    if col_vendas and col_tickets:
        df_resumo['TM_Base (R$)'] = np.where(df_resumo[f"{col_tickets}_base"] > 0,
                                             df_resumo[f"{col_vendas}_base"] / df_resumo[f"{col_tickets}_base"], 0.0)
        df_resumo['TM_Atual (R$)'] = np.where(df_resumo[f"{col_tickets}_atual"] > 0,
                                              df_resumo[f"{col_vendas}_atual"] / df_resumo[f"{col_tickets}_atual"], 0.0)

    tot_fluxo_base = df_resumo[f"{col_fluxo}_base"].sum() if col_fluxo else 0
    tot_fluxo_atual = df_resumo[f"{col_fluxo}_atual"].sum() if col_fluxo else 0
    tot_vendas_base = df_resumo[f"{col_vendas}_base"].sum() if col_vendas else 0
    tot_vendas_atual = df_resumo[f"{col_vendas}_atual"].sum() if col_vendas else 0
    tot_tick_base = df_resumo[f"{col_tickets}_base"].sum() if col_tickets else 0
    tot_tick_atual = df_resumo[f"{col_tickets}_atual"].sum() if col_tickets else 0

    conv_total_base = (tot_tick_base / tot_fluxo_base * 100) if tot_fluxo_base > 0 else 0.0
    conv_total_atual = (tot_tick_atual / tot_fluxo_atual * 100) if tot_fluxo_atual > 0 else 0.0

    return {
        "df_resumo": df_resumo, "df_auditoria": df_auditoria,
        "kpis": {
            "total_lojas": len(lojas_elegiveis),
            "tot_fluxo_atual": tot_fluxo_atual,
            "var_fluxo_total": ((tot_fluxo_atual - tot_fluxo_base) / tot_fluxo_base * 100) if tot_fluxo_base > 0 else 0,
            "tot_vendas_atual": tot_vendas_atual,
            "var_vendas_total": (
                        (tot_vendas_atual - tot_vendas_base) / tot_vendas_base * 100) if tot_vendas_base > 0 else 0,
            "tot_tick_atual": tot_tick_atual,
            "var_tick_total": ((tot_tick_atual - tot_tick_base) / tot_tick_base * 100) if tot_tick_base > 0 else 0,
            "conv_total_atual": conv_total_atual,
            "var_conv_pp": conv_total_atual - conv_total_base
        }
    }


# --- 2. PROCESSAMENTO MÊS A MÊS ---
def processar_base_comparavel_mensal_completa(
        df: pd.DataFrame, col_id: str, col_nome: str, col_data: str,
        col_fluxo: str, col_vendas: str, col_tickets: str,
        dt_base_inicio: datetime.date, dt_base_fim: datetime.date,
        dt_atual_inicio: datetime.date, dt_atual_fim: datetime.date,
        pct_cobertura_min: float = 0.82, ignorar_domingos: bool = True, ignorar_feriados: bool = True
) -> dict:
    datas_base = pd.date_range(start=dt_base_inicio, end=dt_base_fim, freq='MS')
    datas_atual = pd.date_range(start=dt_atual_inicio, end=dt_atual_fim, freq='MS')

    n_meses = min(len(datas_base), len(datas_atual))
    lista_dfs_mensais, totais_mensais, lista_auditorias = [], [], []

    for i in range(n_meses):
        b_ini = datas_base[i].date()
        b_fim = (datas_base[i] + pd.offsets.MonthEnd(1)).date()
        if b_fim > dt_base_fim: b_fim = dt_base_fim

        a_ini = datas_atual[i].date()
        a_fim = (datas_atual[i] + pd.offsets.MonthEnd(1)).date()
        if a_fim > dt_atual_fim: a_fim = dt_atual_fim

        res_m = processar_base_comparavel_completa(
            df=df, col_id=col_id, col_nome=col_nome, col_data=col_data,
            col_fluxo=col_fluxo, col_vendas=col_vendas, col_tickets=col_tickets,
            dt_base_inicio=b_ini, dt_base_fim=b_fim,
            dt_atual_inicio=a_ini, dt_atual_fim=a_fim,
            pct_cobertura_min=pct_cobertura_min, ignorar_domingos=ignorar_domingos, ignorar_feriados=ignorar_feriados
        )

        df_m = res_m["df_resumo"].copy()
        mes_label = a_ini.strftime('%m/%Y')

        # Seleciona as variações principais do mês
        cols_sub = [col_id, col_nome]
        if col_fluxo: cols_sub.append('Var_Fluxo_YoY (%)')
        if col_vendas: cols_sub.append('Var_Vendas_YoY (%)')
        if col_fluxo and col_tickets: cols_sub.append('Conv_Atual (%)')

        df_sub = df_m[cols_sub].copy()
        df_sub.columns = [c if c in [col_id, col_nome] else f"{c}_{mes_label}" for c in cols_sub]

        lista_dfs_mensais.append(df_sub)

        if not res_m["df_auditoria"].empty:
            df_aud_m = res_m["df_auditoria"].copy()
            df_aud_m["Mês Ref."] = a_ini.strftime("%b/%Y")
            lista_auditorias.append(df_aud_m)

        totais_mensais.append({
            "Mes": a_ini.strftime("%b/%Y"),
            "Fluxo Atual": res_m["kpis"]["tot_fluxo_atual"],
            "Fluxo YoY (%)": res_m["kpis"]["var_fluxo_total"],
            "Vendas Atual (R$)": res_m["kpis"]["tot_vendas_atual"],
            "Vendas YoY (%)": res_m["kpis"]["var_vendas_total"],
            "Conversão (%)": res_m["kpis"]["conv_total_atual"],
            "Lojas Comparáveis": res_m["kpis"]["total_lojas"]
        })

    df_evolucao = lista_dfs_mensais[0]
    for df_prox in lista_dfs_mensais[1:]:
        df_evolucao = pd.merge(df_evolucao, df_prox, on=[col_id, col_nome], how='outer').fillna(0)

    df_totais = pd.DataFrame(totais_mensais)
    df_auditoria_mensal = pd.concat(lista_auditorias, ignore_index=True) if lista_auditorias else pd.DataFrame()

    return {
        "df_evolucao_lojas": df_evolucao,
        "df_totais_mensais": df_totais,
        "df_auditoria_mensal": df_auditoria_mensal
    }
