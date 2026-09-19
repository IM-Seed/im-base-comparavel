"""
core_engine.py — Motor de cálculo da Base Comparável.

Mudanças em relação à versão anterior:
  * Feriados vêm da biblioteca `holidays` (sem lista fixa por ano).
    Por padrão usa só os feriados nacionais (mesmo comportamento de antes),
    mas agora aceita também o estado (UF) e os pontos facultativos.
  * Os cálculos repetidos (variação YoY de cada métrica, totais e KPIs)
    foram reunidos em funções auxiliares.
  * Nomes de colunas e formato dos retornos continuam iguais, então o
    app.py funciona sem alterações.

Dependência nova: pip install holidays
"""

import datetime
from functools import lru_cache
from typing import Iterable, Optional

import holidays
import numpy as np
import pandas as pd


# =====================================================================
# 0. LEITURA DE ARQUIVOS
# =====================================================================

def carregar_dados(file_stream, filename: str) -> pd.DataFrame:
    if filename.endswith('.csv'):
        df = pd.read_csv(file_stream)
    elif filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_stream)
    else:
        raise ValueError("Formato não suportado. Utilize arquivos CSV ou Excel.")
    return df


# =====================================================================
# 1. CALENDÁRIO (feriados e dias operacionais)
# =====================================================================

@lru_cache(maxsize=32)
def _feriados_em_cache(anos: tuple, uf: Optional[str], incluir_facultativos: bool) -> frozenset:
    categorias = ("public", "optional") if incluir_facultativos else ("public",)
    calendario = holidays.Brazil(subdiv=uf, years=anos, categories=categorias)
    return frozenset(calendario.keys())


def obter_feriados(anos: Iterable[int], uf: Optional[str] = None,
                   incluir_facultativos: bool = False) -> set:
    """
    Devolve o conjunto de datas (datetime.date) de feriados dos anos informados.

    uf: sigla do estado (ex.: "SP") para incluir feriados estaduais. None = só nacionais.
    incluir_facultativos: inclui pontos facultativos (Carnaval, Corpus Christi,
        vésperas de Natal e Ano-Novo etc.).
    """
    anos_unicos = tuple(sorted({int(a) for a in anos}))
    return set(_feriados_em_cache(anos_unicos, uf, incluir_facultativos))


def filtrar_dias_operacionais(df: pd.DataFrame, col_data: str, ignorar_domingos: bool = True,
                              ignorar_feriados: bool = True, uf_feriados: Optional[str] = None,
                              incluir_facultativos: bool = False) -> pd.DataFrame:
    df_filtered = df.copy()
    df_filtered[col_data] = pd.to_datetime(df_filtered[col_data], errors='coerce')

    if ignorar_domingos:
        df_filtered = df_filtered[df_filtered[col_data].dt.dayofweek != 6]

    if ignorar_feriados:
        # Os anos vêm dos próprios dados: nada para editar na virada do ano.
        anos = df_filtered[col_data].dt.year.dropna().astype(int).unique()
        feriados = obter_feriados(anos, uf_feriados, incluir_facultativos)
        df_filtered = df_filtered[~df_filtered[col_data].dt.date.isin(feriados)]

    return df_filtered


def obter_dias_operacionais_intervalo(dt_inicio: datetime.date, dt_fim: datetime.date,
                                      ignorar_domingos: bool, ignorar_feriados: bool,
                                      uf_feriados: Optional[str] = None,
                                      incluir_facultativos: bool = False) -> int:
    dias = [d.date() for d in pd.date_range(start=dt_inicio, end=dt_fim)
            if not (ignorar_domingos and d.dayofweek == 6)]

    if ignorar_feriados:
        feriados = obter_feriados(range(dt_inicio.year, dt_fim.year + 1),
                                  uf_feriados, incluir_facultativos)
        dias = [d for d in dias if d not in feriados]

    return len(dias)


# =====================================================================
# 2. FUNÇÕES AUXILIARES DE CÁLCULO
# =====================================================================

def _variacao_pct(atual, base):
    """Variação percentual (atual x base). Retorna 0 onde a base é zero."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(base > 0, (atual - base) / base * 100, 0.0)


def _razao(numerador, denominador, escala: float = 1.0):
    """Numerador / denominador (x escala). Retorna 0 onde o denominador é zero."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(denominador > 0, numerador / denominador * escala, 0.0)


def _soma(df: pd.DataFrame, coluna: Optional[str], sufixo: str) -> float:
    return df[f"{coluna}{sufixo}"].sum() if coluna else 0


def _var_pct_total(atual: float, base: float) -> float:
    return (atual - base) / base * 100 if base > 0 else 0.0


# =====================================================================
# 3. PROCESSAMENTO CONSOLIDADO COMPLETO (COM P.A.)
# =====================================================================

def processar_base_comparavel_completa(
        df: pd.DataFrame, col_id: str, col_nome: str, col_data: str,
        col_fluxo: str, col_vendas: str, col_tickets: str, col_pecas: str,
        dt_base_inicio: datetime.date, dt_base_fim: datetime.date,
        dt_atual_inicio: datetime.date, dt_atual_fim: datetime.date,
        pct_cobertura_min: float = 0.82, ignorar_domingos: bool = True, ignorar_feriados: bool = True,
        uf_feriados: Optional[str] = None, incluir_facultativos: bool = False
) -> dict:
    df_work = df.copy()
    df_work[col_data] = pd.to_datetime(df_work[col_data], errors='coerce')
    df_operacional = filtrar_dias_operacionais(
        df_work, col_data, ignorar_domingos, ignorar_feriados, uf_feriados, incluir_facultativos)

    dias_esperados_base = obter_dias_operacionais_intervalo(
        dt_base_inicio, dt_base_fim, ignorar_domingos, ignorar_feriados, uf_feriados, incluir_facultativos)
    dias_esperados_atual = obter_dias_operacionais_intervalo(
        dt_atual_inicio, dt_atual_fim, ignorar_domingos, ignorar_feriados, uf_feriados, incluir_facultativos)

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

    # --- Auditoria: lojas que ficaram de fora da base comparável ---
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

    cols_met = [c for c in [col_fluxo, col_vendas, col_tickets, col_pecas] if c is not None]

    grp_base = df_comp_base.groupby([col_id, col_nome])[cols_met].sum().reset_index()
    grp_atual = df_comp_atual.groupby([col_id, col_nome])[cols_met].sum().reset_index()

    df_resumo = pd.merge(grp_base, grp_atual, on=[col_id, col_nome], suffixes=('_base', '_atual'), how='outer').fillna(0)

    # --- Evolução YoY de cada métrica ---
    for rotulo, col in [("Fluxo", col_fluxo), ("Vendas", col_vendas), ("Tickets", col_tickets), ("Pecas", col_pecas)]:
        if col:
            df_resumo[f'Var_{rotulo}_YoY (%)'] = _variacao_pct(df_resumo[f"{col}_atual"], df_resumo[f"{col}_base"])

    # --- Taxa de conversão real (tickets / fluxo) ---
    if col_fluxo and col_tickets:
        df_resumo['Conv_Base (%)'] = _razao(df_resumo[f"{col_tickets}_base"], df_resumo[f"{col_fluxo}_base"], 100)
        df_resumo['Conv_Atual (%)'] = _razao(df_resumo[f"{col_tickets}_atual"], df_resumo[f"{col_fluxo}_atual"], 100)
        df_resumo['Var_Conv_pp'] = df_resumo['Conv_Atual (%)'] - df_resumo['Conv_Base (%)']

    # --- Ticket médio (vendas R$ / tickets) ---
    if col_vendas and col_tickets:
        df_resumo['TM_Base (R$)'] = _razao(df_resumo[f"{col_vendas}_base"], df_resumo[f"{col_tickets}_base"])
        df_resumo['TM_Atual (R$)'] = _razao(df_resumo[f"{col_vendas}_atual"], df_resumo[f"{col_tickets}_atual"])

    # --- P.A. — produtos por atendimento (peças / tickets) ---
    if col_pecas and col_tickets:
        df_resumo['PA_Base'] = _razao(df_resumo[f"{col_pecas}_base"], df_resumo[f"{col_tickets}_base"])
        df_resumo['PA_Atual'] = _razao(df_resumo[f"{col_pecas}_atual"], df_resumo[f"{col_tickets}_atual"])
        df_resumo['Var_PA_Abs'] = df_resumo['PA_Atual'] - df_resumo['PA_Base']

    # --- Totais da rede ---
    tot_fluxo_base, tot_fluxo_atual = _soma(df_resumo, col_fluxo, "_base"), _soma(df_resumo, col_fluxo, "_atual")
    tot_vendas_base, tot_vendas_atual = _soma(df_resumo, col_vendas, "_base"), _soma(df_resumo, col_vendas, "_atual")
    tot_tick_base, tot_tick_atual = _soma(df_resumo, col_tickets, "_base"), _soma(df_resumo, col_tickets, "_atual")
    tot_pecas_base, tot_pecas_atual = _soma(df_resumo, col_pecas, "_base"), _soma(df_resumo, col_pecas, "_atual")

    conv_total_base = (tot_tick_base / tot_fluxo_base * 100) if tot_fluxo_base > 0 else 0.0
    conv_total_atual = (tot_tick_atual / tot_fluxo_atual * 100) if tot_fluxo_atual > 0 else 0.0

    pa_total_base = (tot_pecas_base / tot_tick_base) if tot_tick_base > 0 else 0.0
    pa_total_atual = (tot_pecas_atual / tot_tick_atual) if tot_tick_atual > 0 else 0.0

    return {
        "df_resumo": df_resumo, "df_auditoria": df_auditoria,
        "kpis": {
            "total_lojas": len(lojas_elegiveis),
            "tot_fluxo_atual": tot_fluxo_atual,
            "var_fluxo_total": _var_pct_total(tot_fluxo_atual, tot_fluxo_base),
            "tot_vendas_atual": tot_vendas_atual,
            "var_vendas_total": _var_pct_total(tot_vendas_atual, tot_vendas_base),
            "tot_tick_atual": tot_tick_atual,
            "var_tick_total": _var_pct_total(tot_tick_atual, tot_tick_base),
            "conv_total_atual": conv_total_atual,
            "var_conv_pp": conv_total_atual - conv_total_base,
            "pa_total_atual": pa_total_atual,
            "var_pa_abs": pa_total_atual - pa_total_base
        }
    }


# =====================================================================
# 4. PROCESSAMENTO MÊS A MÊS COMPLETO (COM P.A.)
# =====================================================================

def processar_base_comparavel_mensal_completa(
        df: pd.DataFrame, col_id: str, col_nome: str, col_data: str,
        col_fluxo: str, col_vendas: str, col_tickets: str, col_pecas: str,
        dt_base_inicio: datetime.date, dt_base_fim: datetime.date,
        dt_atual_inicio: datetime.date, dt_atual_fim: datetime.date,
        pct_cobertura_min: float = 0.82, ignorar_domingos: bool = True, ignorar_feriados: bool = True,
        uf_feriados: Optional[str] = None, incluir_facultativos: bool = False
) -> dict:
    datas_base = pd.date_range(start=dt_base_inicio, end=dt_base_fim, freq='MS')
    datas_atual = pd.date_range(start=dt_atual_inicio, end=dt_atual_fim, freq='MS')

    n_meses = min(len(datas_base), len(datas_atual))
    if n_meses == 0:
        raise ValueError(
            "Os períodos precisam incluir pelo menos um mês iniciado no dia 1 "
            "(a visão mês a mês parte do primeiro dia de cada mês)."
        )

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
            col_fluxo=col_fluxo, col_vendas=col_vendas, col_tickets=col_tickets, col_pecas=col_pecas,
            dt_base_inicio=b_ini, dt_base_fim=b_fim,
            dt_atual_inicio=a_ini, dt_atual_fim=a_fim,
            pct_cobertura_min=pct_cobertura_min, ignorar_domingos=ignorar_domingos,
            ignorar_feriados=ignorar_feriados,
            uf_feriados=uf_feriados, incluir_facultativos=incluir_facultativos
        )

        df_m = res_m["df_resumo"].copy()
        mes_label = a_ini.strftime('%m/%Y')

        cols_sub = [col_id, col_nome]
        if col_fluxo: cols_sub.append('Var_Fluxo_YoY (%)')
        if col_vendas: cols_sub.append('Var_Vendas_YoY (%)')
        if col_fluxo and col_tickets: cols_sub.append('Conv_Atual (%)')
        if col_pecas and col_tickets: cols_sub.append('PA_Atual')

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
            "P.A. (Peças/Ticket)": res_m["kpis"]["pa_total_atual"],
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