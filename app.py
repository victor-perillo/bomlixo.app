import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
import os

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(page_title="Bomlixo | Dashboard Operacional", layout="wide")

# Cores Profissionais
C_VENDA, C_PROD, C_ESTQ = '#3498db', '#2ecc71', '#e74c3c'
CORES_FILHOS = ['#9b59b6', '#f1c40f', '#e67e22', '#1abc9c', '#34495e']

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

# --- CARREGAMENTO ---
df_item = load_data('item.txt')
df_mov = load_data('MovtoItem.txt')
df_notas = load_data('Notas.txt')
df_estrutura = load_data('MovtoItemFilho.txt')

# --- TRATAMENTO DATA E NÚMEROS ---
if not df_mov.empty:
    df_mov['dt-movto'] = pd.to_datetime(df_mov['dt-movto'], format='%d/%m/%y', errors='coerce')
    df_mov['it-codigo'] = df_mov['it-codigo'].astype(str).str.strip()
    df_mov['qtd-faturada'] = clean_numeric(df_mov['qtd-faturada'])
    df_mov['qtd-produzida'] = clean_numeric(df_mov['qtd-produzida'])
    df_mov['qtd-estoq'] = clean_numeric(df_mov['qtd-estoq'])

if not df_notas.empty:
    df_notas['dt-emis-nota'] = pd.to_datetime(df_notas['dt-emis-nota'], format='%d/%m/%y', errors='coerce')
    df_notas['vl-total'] = clean_numeric(df_notas['vl-total'])

if not df_estrutura.empty:
    for col in df_estrutura.columns:
        df_estrutura[col] = df_estrutura[col].astype(str).str.strip()

# Filtros Globais por Data
df_mov_f = df_mov[(df_mov['dt-movto'].dt.date >= d_inicio) & (df_mov['dt-movto'].dt.date <= d_fim)] if not df_mov.empty else pd.DataFrame()
df_notas_f = df_notas[(df_notas['dt-emis-nota'].dt.date >= d_inicio) & (df_notas['dt-emis-nota'].dt.date <= d_fim)] if not df_notas.empty else pd.DataFrame()

# --- INTERFACE PRINCIPAL ---
st.title("📊 BI Operacional | Bomlixo")

# CARDS DE MÉTRICAS
if not df_mov_f.empty or not df_notas_f.empty:
    m1, m2, m3 = st.columns(3)
    m1.metric("Faturamento Total", f"R$ {df_notas_f['vl-total'].sum():,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
    m2.metric("Vendas (Total Qtd)", f"{df_mov_f['qtd-faturada'].sum():,.0f}".replace(',', '.'))
    m3.metric("Produção (Total Qtd)", f"{df_mov_f['qtd-produzida'].sum():,.0f}".replace(',', '.'))

st.divider()

# --- SEÇÃO 1: EVOLUÇÃO OPERACIONAL ---
if not df_mov_f.empty:
    opcoes_bl = sorted(df_mov_f[df_mov_f['it-codigo'].str.startswith('BL', na=False)]['it-codigo'].unique())
    selecao_bl = st.multiselect("Filtrar Códigos BL:", options=opcoes_bl, default=opcoes_bl[:1] if opcoes_bl else [])

    df_g1 = df_mov_f[df_mov_f['it-codigo'].isin(selecao_bl)]

    if not df_g1.empty:
        ritmo = df_g1.groupby('dt-movto').agg({'qtd-faturada':'sum','qtd-produzida':'sum','qtd-estoq':'sum'}).reset_index()
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=ritmo['dt-movto'], y=ritmo['qtd-faturada'], name='Vendas', line=dict(color=C_VENDA, width=3)))
        fig1.add_trace(go.Scatter(x=ritmo['dt-movto'], y=ritmo['qtd-produzida'], name='Produção', line=dict(color=C_PROD, width=3)))
        fig1.add_trace(go.Scatter(x=ritmo['dt-movto'], y=ritmo['qtd-estoq'], name='Estoque', line=dict(color=C_ESTQ, width=2, dash='dot')))
        st.plotly_chart(fig1, use_container_width=True)

        st.markdown("#### Detalhamento Diário (Pai)")
        tabela = df_g1.groupby(['dt-movto', 'it-codigo']).agg({'qtd-faturada':'sum','qtd-produzida':'sum','qtd-estoq':'sum'}).reset_index()
        tabela = tabela.sort_values(['dt-movto', 'it-codigo'], ascending=[True, True])
        tabela['dt-movto'] = tabela['dt-movto'].dt.strftime('%d/%m/%Y')
        st.dataframe(tabela, use_container_width=True, hide_index=True)

# --- SEÇÃO 2: ANÁLISE DE INSUMOS (FILHOS) ---
if not df_estrutura.empty and not df_mov_f.empty:
    st.divider()
    st.header("🔗 Análise de Insumos (Itens Filhos)")
    
    pai_ref = st.selectbox("Selecione um Produto Pai para explodir insumos:", selecao_bl) if selecao_bl else None
    
    if pai_ref:
        # Busca colunas dinamicamente
        col_p = next((c for c in df_estrutura.columns if 'it-codigo' in c.lower() and 'filho' not in c.lower()), df_estrutura.columns[0])
        col_f = next((c for c in df_estrutura.columns if 'filho' in c.lower()), df_estrutura.columns[1])
        
        filhos = df_estrutura[df_estrutura[col_p] == pai_ref][col_f].unique()
        
        if len(filhos) > 0:
            df_filhos_mov = df_mov_f[df_mov_f['it-codigo'].isin(filhos)]
            fig2 = go.Figure()
            # Venda do pai como referência
            venda_p = df_g1[df_g1['it-codigo'] == pai_ref]
            fig2.add_trace(go.Scatter(x=venda_p['dt-movto'], y=venda_p['qtd-faturada'], name='Venda (Pai)', line=dict(color=C_VENDA, width=4)))
            
            for i, f_cod in enumerate(filhos):
                d_f = df_filhos_mov[df_filhos_mov['it-codigo'] == f_cod].sort_values('dt-movto')
                if not d_f.empty:
                    fig2.add_trace(go.Scatter(x=d_f['dt-movto'], y=d_f['qtd-estoq'], name=f"Estoque Filho: {f_cod}", line=dict(dash='dash')))
            
            st.plotly_chart(fig2, use_container_width=True)
            
            with st.expander("Ver Tabela de Insumos", expanded=True):
                tab_f = df_filhos_mov.sort_values(['dt-movto', 'it-codigo'], ascending=[True, True])
                tab_f['dt-movto'] = tab_f['dt-movto'].dt.strftime('%d/%m/%Y')
                st.dataframe(tab_f[['dt-movto', 'it-codigo', 'qtd-estoq', 'qtd-produzida']], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum item filho encontrado para este código.")

# --- RANKINGS ---
st.divider()
r1, r2 = st.columns(2)
with r1:
    st.subheader("🏆 Itens Mais Vendidos")
    if not df_mov_f.empty:
        st.dataframe(df_mov_f.groupby('it-codigo')['qtd-faturada'].sum().nlargest(15).reset_index(), use_container_width=True, hide_index=True)
with r2:
    st.subheader("💰 Maiores Clientes")
    if not df_notas_f.empty:
        st.table(df_notas_f.groupby('nome-abrev')['vl-total'].sum().nlargest(15).reset_index())
