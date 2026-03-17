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
        st.error(f"Arquivo {file_name} não encontrado.")
        st.stop()
    try:
        return pd.read_csv(file_name, sep='\t', encoding='utf-8', low_memory=False)
    except:
        return pd.read_csv(file_name, sep='\t', encoding='latin1', low_memory=False)

# --- SIDEBAR (FILTROS DE DATA) ---
st.sidebar.markdown("### 📅 Período de Análise")
data_range = st.sidebar.date_input("Intervalo", value=(date(2025, 1, 1), date(2025, 1, 31)), format="DD/MM/YYYY")

if not (isinstance(data_range, tuple) and len(data_range) == 2):
    st.stop()
d_inicio, d_fim = data_range

# --- CARREGAMENTO E TRATAMENTO ---
df_item = load_data('item.txt')
df_mov = load_data('MovtoItem.txt')
df_notas = load_data('Notas.txt')

# Garantir tipos de dados corretos e evitar erros de filtro
df_mov['it-codigo'] = df_mov['it-codigo'].astype(str).str.strip()
df_item['it-codigo'] = df_item['it-codigo'].astype(str).str.strip()

# Tratamento numérico robusto
for col in ['qtd-estoq', 'qtd-produzida', 'qtd-faturada']:
    df_mov[col] = pd.to_numeric(df_mov[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

df_notas['vl-total'] = pd.to_numeric(df_notas['vl-total'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

df_mov['dt-movto'] = pd.to_datetime(df_mov['dt-movto'], format='%d/%m/%y', errors='coerce')
df_notas['dt-emis-nota'] = pd.to_datetime(df_notas['dt-emis-nota'], format='%d/%m/%y', errors='coerce')

# Filtro de Data Global
df_mov_f = df_mov[(df_mov['dt-movto'].dt.date >= d_inicio) & (df_mov['dt-movto'].dt.date <= d_fim)]
df_notas_f = df_notas[(df_notas['dt-emis-nota'].dt.date >= d_inicio) & (df_notas['dt-emis-nota'].dt.date <= d_fim)]

# --- TÍTULO E CARDS DE MÉTRICAS (KPIs) ---
st.title("📊 Relatório de Performance Operacional")

# Cálculos para os Cards
total_vendas_qtd = df_mov_f['qtd-faturada'].sum()
total_producao_qtd = df_mov_f['qtd-produzida'].sum()

# Layout dos Cards
col_m1, col_m2 = st.columns(2)
with col_m1:
    st.metric("Vendas (Qtd Total)", f"{total_vendas_qtd:,.0f}".replace(',', '.'))
with col_m2:
    st.metric("Produção (Qtd Total)", f"{total_producao_qtd:,.0f}".replace(',', '.'))

st.divider()

# Categorias de Produtos
df_acabados = df_item[df_item['desc-grp-estoq'].astype(str).str.upper() == 'PRODUTO ACABADO'].copy()
df_semi = df_item[df_item['desc-grp-estoq'].astype(str).str.upper() == 'PRODUTO SEMI ACABADO'].copy()

# --- GRÁFICO 1: EVOLUÇÃO OPERACIONAL ---
# Filtro de Busca/Seleção Multipla
opcoes_bl = sorted(df_mov_f[df_mov_f['it-codigo'].str.startswith('BL', na=False)]['it-codigo'].unique())
selecao_bl = st.multiselect(
    "Pesquisar e Selecionar Códigos BL (Múltipla Seleção):", 
    options=opcoes_bl,
    default=opcoes_bl[:1] if opcoes_bl else None
)

df_g1 = df_mov_f[df_mov_f['it-codigo'].isin(selecao_bl)]

if not df_g1.empty:
    # Agrupamento para o Gráfico
    ritmo_grafico = df_g1.groupby('dt-movto').agg({
        'qtd-faturada':'sum',
        'qtd-produzida':'sum',
        'qtd-estoq':'sum'
    }).reset_index()
    
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=ritmo_grafico['dt-movto'], y=ritmo_grafico['qtd-faturada'], name='Vendas', line=dict(color=C_VENDA, width=3)))
    fig1.add_trace(go.Scatter(x=ritmo_grafico['dt-movto'], y=ritmo_grafico['qtd-produzida'], name='Produção', line=dict(color=C_PROD, width=3)))
    fig1.add_trace(go.Scatter(x=ritmo_grafico['dt-movto'], y=ritmo_grafico['qtd-estoq'], name='Estoque', line=dict(color=C_ESTQ, width=2, dash='dot')))
    fig1.update_layout(title="Evolução Consolidada dos Itens Selecionados", hovermode="x unified", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig1, use_container_width=True)

    # --- TABELA DETALHADA ---
    st.markdown("#### Detalhamento de Movimentação")
    ritmo_tabela = df_g1.groupby(['dt-movto', 'it-codigo']).agg({
        'qtd-faturada':'sum',
        'qtd-produzida':'sum',
        'qtd-estoq':'sum'
    }).reset_index()
    
    tabela_display = ritmo_tabela.sort_values(['dt-movto', 'it-codigo'], ascending=[True, True]).copy()
    tabela_display['dt-movto'] = tabela_display['dt-movto'].dt.strftime('%d/%m/%Y')
    
    st.dataframe(
        tabela_display.rename(columns={
            'dt-movto': 'Data',
            'it-codigo': 'Código',
            'qtd-faturada': 'Vendas (Qtd)',
            'qtd-produzida': 'Produção (Qtd)',
            'qtd-estoq': 'Saldo Estoque'
        }).style.format({
            'Vendas (Qtd)': '{:,.0f}',
            'Produção (Qtd)': '{:,.0f}',
            'Saldo Estoque': '{:,.0f}'
        }),
        use_container_width=True,
        hide_index=True
    )

# --- GRÁFICO 2: ANÁLISE COMPARATIVA (BL + SC) ---
st.divider()
df_todos = pd.concat([df_acabados, df_semi])
df_mov_todos = df_mov_f.merge(df_todos[['it-codigo', 'desc-item']], on='it-codigo', how='inner')
df_mov_todos['display'] = df_mov_todos['it-codigo'] + " - " + df_mov_todos['desc-item']
opcoes_todos = sorted(df_mov_todos['display'].unique())

selecao_unitaria = st.multiselect(
    "Comparativo Detalhado (Selecione códigos BL ou SC):",
    options=opcoes_todos,
    default=opcoes_todos[:1] if opcoes_todos else None
)

codigos_unidade = [s.split(" - ")[0] for s in selecao_unitaria]
df_g2 = df_mov_todos[df_mov_todos['it-codigo'].isin(codigos_unidade)]

if not df_g2.empty:
    ritmo_un = df_g2.groupby('dt-movto').agg({'qtd-faturada':'sum','qtd-produzida':'sum','qtd-estoq':'sum'}).reset_index()
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=ritmo_un['dt-movto'], y=ritmo_un['qtd-faturada'], name='Vendas', marker_color=C_VENDA, opacity=0.6))
    fig2.add_trace(go.Scatter(x=ritmo_un['dt-movto'], y=ritmo_un['qtd-produzida'], name='Produção', line=dict(color=C_PROD, width=3)))
    fig2.add_trace(go.Scatter(x=ritmo_un['dt-movto'], y=ritmo_un['qtd-estoq'], name='Estoque', line=dict(color=C_ESTQ, width=3)))
    fig2.update_layout(title="Fluxo de Inventário (Barras vs Linhas)", hovermode="x unified", barmode='group', legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig2, use_container_width=True)

# --- SEÇÃO FINAL: RANKINGS ---
st.divider()
t1, t2 = st.columns(2)

with t1:
    st.subheader("🏆 Top 15 Itens (Volume)")
    if not df_mov_f.empty and not df_acabados.empty:
        df_rank = df_mov_f.merge(df_acabados[['it-codigo', 'desc-item']], on='it-codigo')
        res = df_rank.groupby(['it-codigo', 'desc-item']).agg({'qtd-faturada':'sum','qtd-produzida':'sum'}).reset_index()
        estq = df_rank.sort_values('dt-movto').groupby('it-codigo').tail(1)[['it-codigo', 'qtd-estoq']]
        top = res.merge(estq, on='it-codigo', how='left').nlargest(15, 'qtd-faturada')
        st.dataframe(top.rename(columns={'it-codigo':'Código','desc-item':'Descrição','qtd-faturada':'Vendas','qtd-produzida':'Produção','qtd-estoq':'Estoque'}), use_container_width=True, hide_index=True)

with t2:
    st.subheader("💰 Top Clientes (Faturamento R$)")
    if not df_notas_f.empty:
        cli = df_notas_f.groupby('nome-abrev')['vl-total'].sum().nlargest(15).reset_index()
        cli['vl-total'] = cli['vl-total'].apply(lambda x: f"R$ {x:,.2f}")
        st.table(cli.rename(columns={'nome-abrev':'Cliente', 'vl-total':'Faturamento'}))
