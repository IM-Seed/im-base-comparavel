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


def processar_base_comparavel(
        df: pd.DataFrame,
        col_id: str,
        col_nome: str,
        col_data: str,
        col_metrica: str,
        dt_base_inicio: datetime.date,
        dt_base_fim: datetime.date,
        dt_atual_inicio: datetime.date,
        dt_atual_fim: datetime.date,
        pct_cobertura_min: float = 0.82,
        ignorar_domingos: bool = True,
        ignorar_feriados: bool = True
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

    # --- GERADOR DE MOTIVOS DE AUDITORIA DE EXCLUSÃO ---
    todas_lojas = df_work[[col_id, col_nome]].drop_duplicates()
    auditoria = []

    for _, row in todas_lojas.iterrows():
        l_id = row[col_id]
        l_nome = row[col_nome]

        d_base = dias_loja_base.get(l_id, 0)
        d_atual = dias_loja_atual.get(l_id, 0)

        reprovou_base = d_base < dias_minimos_base
        reprovou_atual = d_atual < dias_minimos_atual

        if reprovou_base or reprovou_atual:
            motivos = []
            if reprovou_base:
                motivos.append(
                    f"Período Base: apenas {d_base} dia(s) com dados (exigido mín. de {dias_minimos_base} dias de {dias_esperados_base} úteis)")
            if reprovou_atual:
                motivos.append(
                    f"Período Atual: apenas {d_atual} dia(s) com dados (exigido mín. de {dias_minimos_atual} dias de {dias_esperados_atual} úteis)")

            auditoria.append({
                col_id: l_id,
                col_nome: l_nome,
                "Dias Ativos (Base)": f"{d_base} / {dias_esperados_base}",
                "Dias Ativos (Atual)": f"{d_atual} / {dias_esperados_atual}",
                "Status": "Reprovada",
                "Motivo da Exclusão": " | ".join(motivos)
            })

    df_auditoria = pd.DataFrame(auditoria)

    # Processamento Aprovadas
    df_comp_base = df_base[df_base[col_id].isin(lojas_elegiveis)]
    df_comp_atual = df_atual[df_atual[col_id].isin(lojas_elegiveis)]

    grp_base = df_comp_base.groupby([col_id, col_nome])[col_metrica].sum().reset_index()
    grp_atual = df_comp_atual.groupby([col_id, col_nome])[col_metrica].sum().reset_index()

    lbl_base = f"{dt_base_inicio.strftime('%d/%m/%Y')} a {dt_base_fim.strftime('%d/%m/%Y')}"
    lbl_atual = f"{dt_atual_inicio.strftime('%d/%m/%Y')} a {dt_atual_fim.strftime('%d/%m/%Y')}"

    df_resumo = pd.merge(grp_base, grp_atual, on=[col_id, col_nome], suffixes=('_base', '_atual'), how='outer').fillna(
        0)
    df_resumo.rename(
        columns={f"{col_metrica}_base": "Valor_Periodo_Base", f"{col_metrica}_atual": "Valor_Periodo_Atual"},
        inplace=True)

    df_resumo['Dias_Ativos_Base'] = df_resumo[col_id].map(dias_loja_base).fillna(0).astype(int)
    df_resumo['Dias_Ativos_Atual'] = df_resumo[col_id].map(dias_loja_atual).fillna(0).astype(int)

    df_resumo['Var_Abs_YoY'] = df_resumo['Valor_Periodo_Atual'] - df_resumo['Valor_Periodo_Base']
    df_resumo['Var_Pct_YoY'] = np.where(df_resumo['Valor_Periodo_Base'] > 0,
                                        (df_resumo['Var_Abs_YoY'] / df_resumo['Valor_Periodo_Base']) * 100, 0.0)

    tot_base = df_resumo['Valor_Periodo_Base'].sum()
    tot_atual = df_resumo['Valor_Periodo_Atual'].sum()
    var_abs_total = tot_atual - tot_base
    var_pct_total = ((var_abs_total / tot_base) * 100) if tot_base > 0 else 0.0

    return {
        "df_resumo": df_resumo,
        "df_auditoria": df_auditoria,
        "kpis": {
            "total_lojas_comparaveis": len(lojas_elegiveis),
            "dias_esperados_base": dias_esperados_base,
            "dias_minimos_base": dias_minimos_base,
            "dias_esperados_atual": dias_esperados_atual,
            "dias_minimos_atual": dias_minimos_atual,
            "tot_base": tot_base,
            "tot_atual": tot_atual,
            "var_pct_total": var_pct_total,
            "label_base": lbl_base,
            "label_atual": lbl_atual
        }
    }


def processar_base_comparavel_mensal(
        df: pd.DataFrame,
        col_id: str,
        col_nome: str,
        col_data: str,
        col_metrica: str,
        dt_base_inicio: datetime.date,
        dt_base_fim: datetime.date,
        dt_atual_inicio: datetime.date,
        dt_atual_fim: datetime.date,
        pct_cobertura_min: float = 0.82,
        ignorar_domingos: bool = True,
        ignorar_feriados: bool = True
) -> dict:
    datas_base = pd.date_range(start=dt_base_inicio, end=dt_base_fim, freq='MS')
    datas_atual = pd.date_range(start=dt_atual_inicio, end=dt_atual_fim, freq='MS')

    n_meses = min(len(datas_base), len(datas_atual))

    lista_dfs_mensais = []
    totais_mensais = []
    lista_auditorias = []

    for i in range(n_meses):
        b_ini = datas_base[i].date()
        b_fim = (datas_base[i] + pd.offsets.MonthEnd(1)).date()
        if b_fim > dt_base_fim: b_fim = dt_base_fim

        a_ini = datas_atual[i].date()
        a_fim = (datas_atual[i] + pd.offsets.MonthEnd(1)).date()
        if a_fim > dt_atual_fim: a_fim = dt_atual_fim

        res_m = processar_base_comparavel(
            df=df, col_id=col_id, col_nome=col_nome, col_data=col_data, col_metrica=col_metrica,
            dt_base_inicio=b_ini, dt_base_fim=b_fim,
            dt_atual_inicio=a_ini, dt_atual_fim=a_fim,
            pct_cobertura_min=pct_cobertura_min,
            ignorar_domingos=ignorar_domingos, ignorar_feriados=ignorar_feriados
        )

        df_m = res_m["df_resumo"].copy()

        df_sub = df_m[[col_id, col_nome, "Valor_Periodo_Base", "Valor_Periodo_Atual", "Var_Pct_YoY"]].copy()
        df_sub.columns = [
            col_id, col_nome,
            f"Base_{b_ini.strftime('%m/%Y')}",
            f"Atual_{a_ini.strftime('%m/%Y')}",
            f"YoY_{a_ini.strftime('%m/%Y')}"
        ]

        lista_dfs_mensais.append(df_sub)

        # Consolida auditoria mensal
        if not res_m["df_auditoria"].empty:
            df_aud_m = res_m["df_auditoria"].copy()
            df_aud_m["Mês Ref."] = a_ini.strftime("%b/%Y")
            lista_auditorias.append(df_aud_m)

        totais_mensais.append({
            "Mes": a_ini.strftime("%b/%Y"),
            "Total Base": res_m["kpis"]["tot_base"],
            "Total Atual": res_m["kpis"]["tot_atual"],
            "YoY (%)": res_m["kpis"]["var_pct_total"],
            "Lojas Comparáveis": res_m["kpis"]["total_lojas_comparaveis"]
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