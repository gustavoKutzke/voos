
import warnings
warnings.simplefilter("ignore", category=FutureWarning)

from pathlib import Path

import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


# CONFIG

st.set_page_config(
    page_title="Dashboard de Voos no Brasil",
    page_icon="✈️",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "dataset"

PALETA_TOP = "#006699"
PALETA_BASE = "#88c7dc"

DIA_PT = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}
ORD_DIA_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
ORD_PERIODO = ["Madrugada", "Manhã", "Tarde", "Noite"]


# HELPERS (CSV flexível)

def _guess_sep(file: Path) -> str:
    try:
        head = file.read_text(encoding="utf-8", errors="ignore")[:4096]
    except Exception:
        return ";"
    return ";" if head.count(";") >= head.count(",") else ","

def _read_csv_flex(path: Path, sep=None) -> pd.DataFrame:
    if sep is None:
        sep = _guess_sep(path)
    for enc in ("utf-8", "utf-8-sig", "latin1", "cp1252"):
        try:
            return pd.read_csv(path, sep=sep, encoding=enc, engine="python")
        except Exception:
            pass
    for enc in ("utf-16", "utf-16-le", "utf-16-be"):
        try:
            return pd.read_csv(path, sep=sep, encoding=enc, engine="python")
        except Exception:
            pass
    raise RuntimeError(f"Não consegui decodificar {path.name} com encodings comuns.")


# CARGA (cache)

@st.cache_data(show_spinner=True)
def carregar_dados() -> pd.DataFrame:
    # merges por ano
    candidatos = {
        2022: DATA_DIR / "merge_2022.csv",
        2023: DATA_DIR / "merge_2023.csv",
        2024: DATA_DIR / "merge_2024.csv",
        2025: DATA_DIR / "merge_2025.csv",
    }
    bolsas = []
    for ano, caminho in candidatos.items():
        if caminho.exists():
            df = _read_csv_flex(caminho, sep=";")
            df["ano"] = ano
            if "Código Justificativa" in df.columns:
                df["Código Justificativa"] = df["Código Justificativa"].astype(str)
            bolsas.append(df)

    if not bolsas:
        st.error("Nenhum arquivo merge_*.csv encontrado em dataset/. O dashboard não pode continuar.")
        st.stop()

    voos = pd.concat(bolsas, ignore_index=True, sort=False)

    # aeroportos 
    aeroportos_path = DATA_DIR / "airport-codes.csv"
    if aeroportos_path.exists():
        try:
            aero_raw = _read_csv_flex(aeroportos_path, sep=";")
            aero_br = aero_raw.loc[aero_raw["iso_country"] == "BR", ["ident", "name"]].copy()
        except Exception as e:
            st.warning(f"airport-codes.csv indisponível ({e}). Mostrarei códigos ICAO.")
            aero_br = pd.DataFrame(columns=["ident", "name"])
    else:
        st.warning("airport-codes.csv não encontrado. Mostrarei códigos ICAO.")
        aero_br = pd.DataFrame(columns=["ident", "name"])

    # companhias 
    cia_path = DATA_DIR / "airlines-codes.csv"
    if cia_path.exists():
        try:
            cia = _read_csv_flex(cia_path, sep=";")
            ren = {c.lower(): c for c in cia.columns}
            col_sigla = ren.get("sigla", "Sigla") if "Sigla" in cia.columns else "sigla"
            col_nome  = ren.get("nome",  "Nome")  if "Nome"  in cia.columns else "nome"
            cia = cia.rename(columns={col_sigla: "Sigla", col_nome: "Nome"})[["Sigla", "Nome"]].copy()
        except Exception as e:
            st.warning(f"airlines-codes.csv indisponível ({e}). Usarei o código da cia.")
            cia = pd.DataFrame(columns=["Sigla", "Nome"])
    else:
        st.warning("airlines-codes.csv não encontrado. Usarei o código da cia.")
        cia = pd.DataFrame(columns=["Sigla", "Nome"])

    # mantém só voos realizados
    df = voos.loc[voos["Situação Voo"] == "REALIZADO"].copy()

    
    if not aero_br.empty:
        br_idents = set(aero_br["ident"].astype(str))
        br_mask = df["ICAO Aeródromo Origem"].astype(str).isin(br_idents)
    else:
        
        br_mask = df["ICAO Aeródromo Origem"].astype(str).str.startswith(("SB", "SD", "SN", "SS"))
    df = df.loc[br_mask].copy()

    # juntar nomes de aeroportos 
    if not aero_br.empty:
        df = df.merge(
            aero_br.rename(columns={"ident": "ident_join", "name": "nome_aeroporto_origem"}),
            left_on="ICAO Aeródromo Origem",
            right_on="ident_join",
            how="left",
        )
        df["nome_aeroporto_origem"] = df["nome_aeroporto_origem"].fillna(df["ICAO Aeródromo Origem"])
    else:
        df["nome_aeroporto_origem"] = df["ICAO Aeródromo Origem"]

    # juntar nomes de companhias
    if not cia.empty:
        df = df.merge(cia, left_on="ICAO Empresa Aérea", right_on="Sigla", how="left")
        df["Nome"] = df["Nome"].fillna(df["ICAO Empresa Aérea"])
    else:
        df["Nome"] = df["ICAO Empresa Aérea"]

    # datas & features
    for c in ["Partida Prevista", "Partida Real", "Chegada Prevista", "Chegada Real"]:
        df[c] = pd.to_datetime(df[c], format="%d/%m/%Y %H:%M", errors="coerce")

    df = df.dropna(subset=["Partida Prevista", "Partida Real"]).copy()

    df["atraso_partida_min"] = (df["Partida Real"] - df["Partida Prevista"]).dt.total_seconds() / 60.0
    df["voo_atrasado"] = (df["atraso_partida_min"] > 15).astype(int)

    df["dia_da_semana"] = df["Partida Prevista"].dt.weekday.map(DIA_PT)

    h = df["Partida Prevista"].dt.hour
    df["periodo_dia"] = pd.cut(h, bins=[-1, 6, 12, 18, 24], labels=ORD_PERIODO, right=False)

    return df


# Carga

df_realizados = carregar_dados()


# UI: título + filtros

st.title("✈️ Dashboard de Atrasos de Voos no Brasil")

st.sidebar.header("Filtros")
anos_disponiveis = sorted(df_realizados["ano"].dropna().unique().tolist())
anos_selecionados = st.sidebar.multiselect(
    "Selecione o(s) ano(s)", options=anos_disponiveis, default=anos_disponiveis
)
if not anos_selecionados:
    st.sidebar.warning("Selecione pelo menos um ano.")
    st.stop()

df_filtrado = df_realizados[df_realizados["ano"].isin(anos_selecionados)].copy()


# KPIs

st.header("Visão Geral do Período Selecionado")
total_voos = len(df_filtrado)
total_atrasos = int(df_filtrado["voo_atrasado"].sum())
perc = (total_atrasos / total_voos * 100) if total_voos else 0.0

c1, c2, c3 = st.columns(3)
c1.metric("Total de Voos Realizados", f"{total_voos:,}".replace(",", "."))
c2.metric("Atrasos na Partida (>15 min)", f"{total_atrasos:,}".replace(",", "."))
c3.metric("Percentual de Atrasos", f"{perc:.2f}%")

st.divider()


# ANÁLISES

st.header("Análises Detalhadas")

# Top aeroportos por atraso 
st.subheader("🏆 Top 10 Aeroportos com Mais Atrasos na Partida")
top_aer = (
    df_filtrado.groupby("nome_aeroporto_origem", as_index=False)["voo_atrasado"]
    .sum()
    .sort_values("voo_atrasado", ascending=False)
    .head(10)
)
if len(top_aer):
    fig, ax = plt.subplots(figsize=(10, 6))
    cores = [PALETA_BASE] * len(top_aer)
    if len(cores):
        cores[0] = PALETA_TOP
    sns.barplot(
        data=top_aer, x="voo_atrasado", y="nome_aeroporto_origem",
        ax=ax, orient="h", palette=cores,
    )
    for i, v in enumerate(top_aer["voo_atrasado"]):
        ax.text(v, i, f" {int(v):,}".replace(",", "."), va="center")
    ax.set_title("Top 10 Aeroportos por Volume Total de Atrasos (anos selecionados)")
    ax.set_xlabel("")
    ax.set_ylabel("Aeroporto")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    sns.despine(left=True, bottom=True)
    st.pyplot(fig)
else:
    st.info("Sem dados para o filtro atual.")

# Comparativo por companhia e ano 
st.subheader("✈️ Comparativo Anual de Atrasos (Top 10 Companhias)")
if len(anos_selecionados) > 1:
    ranking_cia = (
        df_filtrado.groupby("Nome", as_index=False)["voo_atrasado"]
        .sum()
        .sort_values("voo_atrasado", ascending=False)
        .head(10)["Nome"]
        .tolist()
    )
    df_comp = df_filtrado[df_filtrado["Nome"].isin(ranking_cia)]
    comp = (
        df_comp.groupby(["ano", "Nome"], as_index=False)["voo_atrasado"]
        .sum()
        .sort_values(["ano", "voo_atrasado"], ascending=[True, False])
    )
    if len(comp):
        fig, ax = plt.subplots(figsize=(12, 7))
        sns.barplot(data=comp, x="Nome", y="voo_atrasado", hue="ano", ax=ax, palette="viridis")
        ax.set_title("Comparativo de Atrasos na Partida por Ano (Top 10 Companhias)")
        ax.set_xlabel("Companhia Aérea")
        ax.set_ylabel("Número Total de Voos Atrasados")
        ax.grid(axis="y", linestyle="--", linewidth=0.7)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.info("Não há dados de atrasos de companhias para os anos selecionados.")
else:
    st.info("Selecione mais de um ano para ver a comparação entre companhias.")

#  Dia da semana & Período do dia 
st.subheader("📅 Atrasos por Dia da Semana e Período do Dia")
c_esq, c_dir = st.columns(2)

with c_esq:
    st.markdown("##### Por Dia da Semana")
    por_dia = df_filtrado.groupby("dia_da_semana", as_index=False)["voo_atrasado"].sum()
    por_dia["ord"] = por_dia["dia_da_semana"].map({n: i for i, n in enumerate(ORD_DIA_PT)})
    por_dia = por_dia.sort_values("ord")
    if len(por_dia):
        fig, ax = plt.subplots()
        sns.barplot(data=por_dia, x="dia_da_semana", y="voo_atrasado", ax=ax, palette="magma")
        ax.set_title("Total de Atrasos por Dia da Semana")
        ax.set_xlabel("Dia da Semana")
        ax.set_ylabel("Número de Voos Atrasados")
        ax.set_xticklabels(ORD_DIA_PT, rotation=45)
        st.pyplot(fig)

with c_dir:
    st.markdown("##### Por Período do Dia")
    por_per = df_filtrado.groupby("periodo_dia", as_index=False)["voo_atrasado"].sum()
    por_per["ord"] = por_per["periodo_dia"].map({n: i for i, n in enumerate(ORD_PERIODO)})
    por_per = por_per.sort_values("ord")
    if len(por_per):
        fig, ax = plt.subplots()
        sns.barplot(data=por_per, x="periodo_dia", y="voo_atrasado", ax=ax, palette="plasma")
        ax.set_title("Total de Atrasos por Período do Dia")
        ax.set_xlabel("Período")
        ax.set_ylabel("Número de Voos Atrasados")
        plt.xticks(rotation=45)
        st.pyplot(fig)

st.divider()


# Tendências (somente AUMENTO)

st.header("📈 Tendência de Aumentos de Atrasos (2022–2024)")
necessarios = {2022, 2023, 2024}
presentes = set(df_filtrado["ano"].unique().tolist())
if necessarios.issubset(presentes):
    piv = (
        df_filtrado.pivot_table(
            index="nome_aeroporto_origem",
            columns="ano",
            values="voo_atrasado",
            aggfunc="sum",
        )
        .fillna(0)
        .copy()
    )
    for a in necessarios:
        if a not in piv.columns:
            piv[a] = 0

    # aumento consistente
    cond_up = (piv[2023] >= piv[2022]) & (piv[2024] > piv[2023])
    df_up = piv[cond_up].copy()
    df_up["Variacao_Total"] = df_up[2024] - df_up[2022]
    df_up = df_up.sort_values("Variacao_Total", ascending=False)

    if len(df_up):
        top = df_up.head(10)
        fig, ax = plt.subplots(figsize=(8, 5))
        sns.barplot(x=top["Variacao_Total"], y=top.index, ax=ax, palette="Reds_r", orient="h")
        ax.set_title("Top 10 piores tendências (mais aumentaram atrasos de 2022 para 2024)")
        ax.set_xlabel("Nº de atrasos a mais (2024 vs 2022)")
        ax.set_ylabel("Aeroporto")
        st.pyplot(fig)
        with st.expander("Ver dados"):
            st.dataframe(df_up)
    else:
        st.info("Nenhum aeroporto apresentou tendência consistente de aumento.")
else:
    st.info("Para ver a tendência, selecione 2022, 2023 e 2024.")
