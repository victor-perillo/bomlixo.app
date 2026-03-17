import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
import os

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(page_title="Bomlixo | Inteligência de Insumos", layout="wide")

# Paleta de Cores Profissionais
C_VENDA, C_PROD, C_ESTQ = '#3498db', '#2ecc71', '#e74c3c'
CORES_FILHOS = ['#9b59b6', '#f1c40f', '#e67e22', '#1abc9c', '#34495e']

@st.cache_data
def load_data(file_name):
    if not os.path.exists(file_name):
        return pd.DataFrame()
    try:
        return pd.read_csv(file_name, sep='\t', encoding='utf-8')
    except:
        return pd.read_csv(file_name, sep='\t', encoding='latin1')

# --- SIDEBAR (FILTROS TEMPORAIS) ---
st.sidebar.markdown("### 📅 Período de Análise")
data_range = st.sidebar.date_input("Intervalo", value=(date(2025, 1, 1), date(2025, 1, 31)), format="DD/MM/YYYY")

if not (isinstance(data_range, tuple) and len(data_range) == 2):
    st.stop()
d_inicio, d_fim = data_range

# --- CARREGAMENTO E TRATAMENTO ---
df_item = load_data('item.txt')
df_mov = load_data('MovtoItem.txt')
df_notas = load_data('Notas.txt')
df_estrutura = load_data('MovtoItemFilho.txt') # Nome atualizado conforme solicitado

# Padronização de Tipos (String para Códigos)
for df in [df_mov, df_item, df_estrutura]:
    if not df.empty:
        for col in df.columns:
            if 'codigo' in col: df[col] = df[col].astype(str)

if not df_mov.empty:
    for col in ['qtd-estoq', 'qtd-produzida', 'qtd-faturada']:
        df_mov[col] = df_mov[col].astype(str).str.replace(',', '.').astype(float)
    df_mov['dt-movto'] = pd.to_datetime(df_mov['dt-movto'], format='%d/%m/%y')

# Filtro de Data Global
df_mov_f = df_mov[(df_mov['dt-movto'].dt.date >= d_inicio) & (df_mov['dt-movto'].dt.date <= d_fim)]

# Categorização
df_acabados = df_item[df_item['desc-grp-estoq'].astype(str).str.upper() == 'PRODUTO ACABADO'].copy()
df_semi = df_item[df_item['desc-grp-estoq'].astype(str).str.upper() == 'PRODUTO SEMI ACABADO'].copy()

# --- SEÇÃO 1: EVOLUÇÃO OPERACIONAL (PRODUTO PAI) ---
st.title("📊 BI Operacional | Bomlixo")
st.divider()

opcoes_bl = sorted(df_mov_f[df_mov_f['it-codigo'].str.startswith('BL', na=False)]['it-codigo'].unique())
selecao_bl = st.multiselect("Selecione os Produtos Acabados (BL):", options=opcoes_bl, default=opcoes_bl[:1])

df_g1 = df_mov_f[df_mov_f['it-codigo'].isin(selecao_bl)]

if not df_g1.empty:
    ritmo_g1 = df_g1.groupby('dt-movto').agg({'qtd-faturada':'sum','qtd-produzida':'sum','qtd-estoq':'sum'}).reset_index()
    
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=ritmo_g1['dt-movto'], y=ritmo_g1['qtd-faturada'], name='Vendas', line=dict(color=C_VENDA, width=3)))
    fig1.add_trace(go.Scatter(x=ritmo_g1['dt-movto'], y=ritmo_g1['qtd-produzida'], name='Produção', line=dict(color=C_PROD, width=3)))
    fig1.add_trace(go.Scatter(x=ritmo_g1['dt-movto'], y=ritmo_g1['qtd-estoq'], name='Estoque', line=dict(color=C_ESTQ, width=2, dash='dot')))
    fig1.update_layout(title="Evolução Consolidada (Pai)", hovermode="x unified", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig1, use_container_width=True)

    with st.expander("📄 Tabela Detalhada (Pai)", expanded=True):
        tabela_pai = ritmo_g1.sort_values('dt-movto', ascending=True).copy()
        tabela_pai['dt-movto'] = tabela_pai['dt-movto'].dt.strftime('%d/%m/%Y')
        st.dataframe(tabela_pai.rename(columns={'dt-movto':'Data','qtd-faturada':'Vendas','qtd-produzida':'Produção','qtd-estoq':'Estoque'}), use_container_width=True, hide_index=True)

# --- SEÇÃO 2: ANÁLISE DE RUPTURA (ITENS FILHOS) ---
st.divider()
st.header("🔗 Análise de Ruptura de Insumos")

if df_estrutura.empty:
    st.warning("⚠️ Arquivo 'MovtoItemFilho.txt' não encontrado no GitHub.")
else:
    pai_analise = st.selectbox("Escolha um Produto para analisar seus Filhos:", selecao_bl)
    
    # Filtra os filhos na estrutura
    filhos_do_pai = df_estrutura[df_estrutura['it-codigo'] == pai_analise]['it-codigo-filho'].unique()
    
    if len(filhos_do_pai) == 0:
        st.info(f"O item {pai_analise} não possui filhos vinculados.")
    else:
        df_mov_filhos = df_mov_f[df_mov_f['it-codigo'].isin(filhos_do_pai)]
        df_venda_pai = df_g1[df_g1['it-codigo'] == pai_analise].sort_values('dt-movto')
        
        fig_ruptura = go.Figure()
        fig_ruptura.add_trace(go.Scatter(x=df_venda_pai['dt-movto'], y=df_venda_pai['qtd-faturada'], name='Venda do Pai', line=dict(color=C_VENDA, width=4)))
        
        for i, filho in enumerate(filhos_do_pai):
            df_f = df_mov_filhos[df_mov_filhos['it-codigo'] == filho].sort_values('dt-movto')
            if not df_f.empty:
                cor = CORES_FILHOS[i % len(CORES_FILHOS)]
                fig_ruptura.add_trace(go.Scatter(x=df_f['dt-movto'], y=df_f['qtd-estoq'], name=f"Estoque Filho: {filho}", line=dict(color=cor, width=2, dash='dash')))
        
        fig_ruptura.update_layout(title=f"Disponibilidade de Insumos para {pai_analise}", hovermode="x unified", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_ruptura, use_container_width=True)

        with st.expander("📄 Tabela Cronológica de Insumos", expanded=True):
            tabela_filhos = df_mov_filhos.sort_values(['dt-movto', 'it-codigo'], ascending=[True, True])[['dt-movto', 'it-codigo', 'qtd-estoq', 'qtd-produzida']]
            tabela_filhos['dt-movto'] = tabela_filhos['dt-movto'].dt.strftime('%d/%m/%Y')
            st.dataframe(tabela_filhos.rename(columns={'dt-movto':'Data','it-codigo':'Código Filho','qtd-estoq':'Estoque Filho','qtd-produzida':'Produção Filho'}), use_container_width=True, hide_index=True)

# --- SEÇÃO 3: RANKINGS ---
st.divider()
t1, t2 = st.columns(2)
with t1:
    st.subheader("🏆 Top 15 Itens (Volume)")
    df_rank = df_mov_f.merge(df_acabados[['it-codigo', 'desc-item']], on='it-codigo')
    res = df_rank.groupby(['it-codigo', 'desc-item']).agg({'qtd-faturada':'sum','qtd-produzida':'sum'}).reset_index()
    estq_f = df_rank.sort_values('dt-movto').groupby('it-codigo').tail(1)[['it-codigo', 'qtd-estoq']]
    top = res.merge(estq_f, on='it-codigo', how='left').nlargest(15, 'qtd-faturada')
    st.dataframe(top[['it-codigo','desc-item','qtd-faturada','qtd-produzida','qtd-estoq']], use_container_width=True, hide_index=True)

with t2:
    st.subheader("💰 Top Clientes (Faturamento Financeiro)")
    df_notas_f = df_notas[(df_notas['dt-emis-nota'].dt.date >= d_inicio) & (df_notas['dt-emis-nota'].dt.date <= d_fim)]
    cli = df_notas_f.groupby('nome-abrev')['vl-total'].sum().nlargest(15).reset_index()
    cli['vl-total'] = cli['vl-total'].apply(lambda x: f"R$ {x:,.2f}")
    st.table(cli.rename(columns={'nome-abrev':'Cliente', 'vl-total':'Faturamento'}))
