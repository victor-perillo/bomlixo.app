import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
import os

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(page_title="Bomlixo | Dashboard Operacional", layout="wide")

# Cores Profissionais
C_VENDA, C_PROD, C_ESTQ = '#3498db', '#2ecc71', '#e74c3c'

@st.cache_data
def load_data(file_name):
    if not os.path.exists(file_name):
        return pd.DataFrame()
    try:
        return pd.read_csv(file_name, sep='\t', encoding='utf-8', low_memory=False)
    except:
        return pd.read_csv(file_name, sep='\t', encoding='latin1', low_memory=False)

# --- TRATAMENTO DE DADOS ---
def clean_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(',', '.').replace('nan', '0'), errors='coerce').fillna(0)

# --- SIDEBAR (FILTROS) ---
st.sidebar.markdown("### 📅 Período de Análise")
data_range = st.sidebar.date_input("Intervalo", value=(date(2025, 1, 1), date(2025, 1, 31)), format="DD/MM/YYYY")

if not (isinstance(data_range, tuple) and len(data_range) == 2):
    st.stop()
d_inicio, d_fim = data_range

# --- PROCESSAMENTO ---
df_item = load_data('item.txt')
df_mov = load_data('MovtoItem.txt')
df_notas = load_data('Notas.txt')

if not df_mov.empty:
    df_mov['dt-movto'] = pd.to_datetime(df_mov['dt-movto'], format='%d/%m/%y', errors='coerce')
    df_mov['it-codigo'] = df_mov['it-codigo'].astype(str).str.strip()
    df_mov['qtd-faturada'] = clean_numeric(df_mov['qtd-faturada'])
    df_mov['qtd-produzida'] = clean_numeric(df_mov['qtd-produzida'])
    df_mov['qtd-estoq'] = clean_numeric(df_mov['qtd-estoq'])

if not df_notas.empty:
    df_notas['dt-emis-nota'] = pd.to_datetime(df_notas['dt-emis-nota'], format='%d/%m/%y', errors='coerce')
    df_notas['vl-total'] = clean_numeric(df_notas['vl-total'])

# Filtros Globais por Data
df_mov_f = df_mov[(df_mov['dt-movto'].dt.date >= d_inicio) & (df_mov['dt-movto'].dt.date <= d_fim)] if not df_mov.empty else pd.DataFrame()
df_notas_f = df_notas[(df_notas['dt-emis-nota'].dt.date >= d_inicio) & (df_notas['dt-emis-nota'].dt.date <= d_fim)] if not df_notas.empty else pd.DataFrame()

# --- INTERFACE PRINCIPAL ---
st.title("📊 BI Operacional | Bomlixo")
st.markdown(f"Análise de **{d_inicio.strftime('%d/%m/%Y')}** até **{d_fim.strftime('%d/%m/%Y')}**")

# --- CARDS DE MÉTRICAS (KPIs) ---
if not df_mov_f.empty or not df_notas_f.empty:
    m1, m2, m3 = st.columns(3)
    
    total_vendas_qtd = df_mov_f['qtd-faturada'].sum()
    total_producao_qtd = df_mov_f['qtd-produzida'].sum()
    total_faturamento_rs = df_notas_f['vl-total'].sum()

    m1.metric("Faturamento Total (R$)", f"R$ {total_faturamento_rs:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.'))
    m2.metric("Vendas (Sacos/Total)", f"{total_vendas_qtd:,.0f}".replace(',', '.'))
    m3.metric("Produção (Sacos/Total)", f"{total_producao_qtd:,.0f}".replace(',', '.'))

st.divider()

# --- SEÇÃO DE GRÁFICOS E TABELA ---
if not df_mov_f.empty:
    opcoes_bl = sorted(df_mov_f[df_mov_f['it-codigo'].str.startswith('BL', na=False)]['it-codigo'].unique())
    selecao_bl = st.multiselect("Filtrar Códigos BL para análise detalhada:", options=opcoes_bl, default=opcoes_bl[:1] if opcoes_bl else [])

    df_selecionado = df_mov_f[df_mov_f['it-codigo'].isin(selecao_bl)]

    if not df_selecionado.empty:
        # Gráfico
        ritmo = df_selecionado.groupby('dt-movto').agg({'qtd-faturada':'sum','qtd-produzida':'sum','qtd-estoq':'sum'}).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ritmo['dt-movto'], y=ritmo['qtd-faturada'], name='Vendas', line=dict(color=C_VENDA, width=3)))
        fig.add_trace(go.Scatter(x=ritmo['dt-movto'], y=ritmo['qtd-produzida'], name='Produção', line=dict(color=C_PROD, width=3)))
        fig.add_trace(go.Scatter(x=ritmo['dt-movto'], y=ritmo['qtd-estoq'], name='Estoque', line=dict(color=C_ESTQ, width=2, dash='dot')))
        fig.update_layout(title="Evolução Consolidada (Itens Selecionados)", hovermode="x unified", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

        # Tabela Detalhada (Cronológica)
        st.markdown("#### Detalhamento Diário")
        tabela = df_selecionado.groupby(['dt-movto', 'it-codigo']).agg({'qtd-faturada':'sum','qtd-produzida':'sum','qtd-estoq':'sum'}).reset_index()
        tabela = tabela.sort_values(['dt-movto', 'it-codigo'], ascending=[True, True])
        tabela['dt-movto'] = tabela['dt-movto'].dt.strftime('%d/%m/%Y')
        
        st.dataframe(
            tabela.rename(columns={'dt-movto':'Data','it-codigo':'Código','qtd-faturada':'Vendas','qtd-produzida':'Produção','qtd-estoq':'Estoque'}).style.format({'Vendas': '{:,.0f}', 'Produção': '{:,.0f}', 'Estoque': '{:,.0f}'}),
            use_container_width=True, hide_index=True
        )

# --- RANKINGS ---
st.divider()
r1, r2 = st.columns(2)

with r1:
    st.subheader("🏆 Itens Mais Vendidos")
    if not df_mov_f.empty:
        top_it = df_mov_f.groupby('it-codigo')['qtd-faturada'].sum().nlargest(15).reset_index()
        st.dataframe(top_it, use_container_width=True, hide_index=True)

with r2:
    st.subheader("💰 Maiores Clientes")
    if not df_notas_f.empty:
        top_cli = df_notas_f.groupby('nome-abrev')['vl-total'].sum().nlargest(15).reset_index()
        top_cli['vl-total'] = top_cli['vl-total'].apply(lambda x: f"R$ {x:,.2f}")
        st.table(top_cli)