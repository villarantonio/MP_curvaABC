# -*- coding: utf-8 -*-
"""
ANÁLISE TEMPORAL MULTI-GRANULARIDADE: DIÁRIO, SEMANAL E MENSAL
Gera rankings e análises com IA para diferentes períodos temporais.

Uso:
    python analise_temporal_multi.py [arquivo_dados] [--diario] [--semanal] [--mensal]

Saída: JSONs separados em mp-main/data/
    - vendas_diario.json
    - vendas_semanal.json
    - vendas_mensal.json
    - consolidado.json (índice de todos os arquivos)
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Any
import pandas as pd

# Tenta importar o Gemini
try:
    import google.generativeai as genai
    GEMINI_DISPONIVEL = True
except ImportError:
    GEMINI_DISPONIVEL = False

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURAÇÕES
# ==========================================
NOME_ARQUIVO = sys.argv[1] if len(sys.argv) > 1 else "dados_vendas.csv"
PASTA_SAIDA = "docs/data"

# Colunas do CSV/XLSX
COL_LOJA = 'FtoResumoVendaGeralItem[loja_id]'
COL_PRODUTO = 'FtoResumoVendaGeralItem[material_descr]'
COL_VALOR = 'FtoResumoVendaGeralItem[vl_total]'
COL_DATA = 'FtoResumoVendaGeralItem[dt_contabil]'

# Parâmetros
TOP_N = 10
BOTTOM_N = 10
PAUSA_ENTRE_REQUISICOES = 2.0
MAX_TENTATIVAS_API = 5
DELAY_ENTRE_CHAMADAS = 12.0  # segundos entre chamadas (reduzido para plano pago)

API_KEY = os.environ.get('GEMINI_API_KEY', '')

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================

def limpar_valor_monetario(valor: Any) -> float:
    """Converte valor monetário para float."""
    if pd.isna(valor):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    texto = texto.replace('R$', '').replace(' ', '')
    texto = texto.replace('.', '').replace(',', '.')
    try:
        return float(texto)
    except ValueError:
        return 0.0


def carregar_dados(caminho: str) -> Optional[pd.DataFrame]:
    """Carrega arquivo de dados (CSV ou XLSX)."""
    if not os.path.exists(caminho):
        logger.error(f"Arquivo não encontrado: {caminho}")
        return None

    extensao = caminho.lower().split('.')[-1]

    if extensao in ['xlsx', 'xls']:
        try:
            df = pd.read_excel(caminho, engine='openpyxl', dtype={COL_LOJA: str})
            logger.info(f"Excel carregado - {len(df)} registros")
            return df
        except Exception as e:
            logger.error(f"Erro ao carregar Excel: {e}")
            return None
    else:
        try:
            for encoding in ['utf-8', 'latin1', 'cp1252']:
                try:
                    df = pd.read_csv(caminho, sep=';', encoding=encoding, dtype={COL_LOJA: str})
                    logger.info(f"CSV carregado ({encoding}) - {len(df)} registros")
                    return df
                except UnicodeDecodeError:
                    continue
            return None
        except Exception as e:
            logger.error(f"Erro ao carregar CSV: {e}")
            return None


def preparar_dados(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara dados com colunas temporais."""
    df = df.copy()

    # Limpa valores
    df['valor_limpo'] = df[COL_VALOR].apply(limpar_valor_monetario)
    df = df[df['valor_limpo'] > 0]

    # Processa datas
    df['data_obj'] = pd.to_datetime(df[COL_DATA], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['data_obj'])

    # Cria colunas temporais
    df['dia'] = df['data_obj'].dt.strftime('%Y-%m-%d')
    df['semana'] = df['data_obj'].dt.strftime('%Y-W%W')
    df['mes'] = df['data_obj'].dt.to_period('M').astype(str)

    # Padroniza
    df['produto'] = df[COL_PRODUTO].astype(str).str.strip().str.upper()
    df['loja_id'] = df[COL_LOJA].astype(str)

    logger.info(f"Dados preparados: {len(df)} registros válidos")
    return df


def configurar_ia() -> Optional[Any]:
    """Configura modelo Gemini."""
    if not GEMINI_DISPONIVEL or not API_KEY:
        logger.warning("API Gemini não disponível")
        return None
    try:
        genai.configure(api_key=API_KEY)
        modelo = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={"temperature": 0.25, "response_mime_type": "application/json"}
        )
        logger.info("Gemini configurado")
        return modelo
    except Exception as e:
        logger.error(f"Erro ao configurar Gemini: {e}")
        return None


# ==========================================
# ANÁLISE POR GRANULARIDADE
# ==========================================

def agregar_por_periodo(df: pd.DataFrame, coluna_periodo: str) -> pd.DataFrame:
    """Agrega dados por período (dia, semana ou mês)."""
    return (
        df.groupby(['loja_id', coluna_periodo, 'produto'])['valor_limpo']
        .sum()
        .reset_index()
        .rename(columns={coluna_periodo: 'periodo'})
    )


def selecionar_top_bottom(df_periodo: pd.DataFrame, top_n: int = TOP_N, bottom_n: int = BOTTOM_N) -> pd.DataFrame:
    """Seleciona TOP e BOTTOM produtos de um período."""
    df_sorted = df_periodo.sort_values('valor_limpo', ascending=False)

    # TOP N
    top = df_sorted.head(top_n).copy()
    top['tipo'] = 'TOP'

    # BOTTOM N (com vendas > 0)
    bottom = df_sorted[df_sorted['valor_limpo'] > 0].tail(bottom_n).copy()
    bottom['tipo'] = 'BOTTOM'

    return pd.concat([top, bottom], ignore_index=True)


def analisar_com_ia(modelo: Any, id_loja: str, periodo: str, itens: list, total: float, granularidade: str) -> list:
    """Analisa produtos com IA."""
    if not modelo or not itens:
        for item in itens:
            item['analise_ia'] = {"diagnostico": "IA não disponível", "acao": "-"}
        return itens

    # Prepara dados para o prompt
    dados_texto = "\n".join([
        f"- {i['produto']}: R$ {i['valor']:.2f} ({i['tipo']})"
        for i in itens
    ])

    prompt = f"""Analise o desempenho de vendas da Loja {id_loja} no período {periodo} ({granularidade}).

DADOS DE VENDAS:
{dados_texto}

Total do período: R$ {total:.2f}

Para CADA produto, forneça:
1. Diagnóstico curto (máx 80 chars)
2. Ação prática (máx 60 chars)

Retorne JSON array:
[{{"produto": "NOME", "diagnostico": "...", "acao": "..."}}]"""

    try:
        time.sleep(DELAY_ENTRE_CHAMADAS)
        resposta = modelo.generate_content(prompt)
        resultado = json.loads(resposta.text)

        # Mapeia resultados
        dict_analises = {r['produto']: r for r in resultado if isinstance(r, dict)}

        for item in itens:
            analise = dict_analises.get(item['produto'], {})
            item['analise_ia'] = {
                "diagnostico": analise.get('diagnostico', 'Análise indisponível'),
                "acao": analise.get('acao', '-')
            }

        return itens
    except Exception as e:
        logger.warning(f"Erro IA para {periodo}: {e}")
        for item in itens:
            item['analise_ia'] = {"diagnostico": "Erro na análise", "acao": "-"}
        return itens


def processar_granularidade(df: pd.DataFrame, coluna_periodo: str, granularidade: str, modelo: Any) -> dict:
    """Processa análise para uma granularidade específica."""
    logger.info(f"\n{'='*50}")
    logger.info(f"📊 Processando análise {granularidade.upper()}")
    logger.info(f"{'='*50}")

    df_agregado = agregar_por_periodo(df, coluna_periodo)
    lojas = sorted(df_agregado['loja_id'].unique())

    resultado = {"granularidade": granularidade, "gerado_em": datetime.now().isoformat(), "dados_lojas": []}

    for id_loja in lojas:
        df_loja = df_agregado[df_agregado['loja_id'] == id_loja]
        periodos = sorted(df_loja['periodo'].unique())

        logger.info(f"🏢 Loja {id_loja}: {len(periodos)} períodos")

        analises = {}
        for periodo in periodos:
            df_periodo = df_loja[df_loja['periodo'] == periodo]
            total = df_periodo['valor_limpo'].sum()

            selecao = selecionar_top_bottom(df_periodo)
            if selecao.empty:
                continue

            itens = [
                {"produto": row['produto'], "valor": round(row['valor_limpo'], 2), "tipo": row['tipo']}
                for _, row in selecao.iterrows()
            ]

            # Análise IA (apenas para os últimos 7 períodos para economizar rate limit)
            if periodo in periodos[-7:]:
                itens = analisar_com_ia(modelo, id_loja, periodo, itens, total, granularidade)
            else:
                for item in itens:
                    item['analise_ia'] = {"diagnostico": "Período histórico", "acao": "-"}

            analises[periodo] = {"total": round(total, 2), "itens": itens}

        try:
            id_loja_final = int(id_loja)
        except:
            id_loja_final = id_loja

        resultado["dados_lojas"].append({"id_loja": id_loja_final, "analises": analises})

    return resultado



# ==========================================
# FUNÇÃO PRINCIPAL
# ==========================================

def salvar_json(dados: dict, nome_arquivo: str) -> bool:
    """Salva dados em JSON na pasta de saída."""
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    caminho = os.path.join(PASTA_SAIDA, nome_arquivo)
    try:
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Salvo: {caminho}")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar {caminho}: {e}")
        return False


def main():
    """Executa análise temporal multi-granularidade."""
    inicio = time.time()

    logger.info("="*60)
    logger.info("🚀 ANÁLISE TEMPORAL MULTI-GRANULARIDADE")
    logger.info("="*60)

    # Detecta quais granularidades executar
    args = sys.argv[1:]
    fazer_diario = '--diario' in args or '--all' in args or len([a for a in args if a.startswith('--')]) == 0
    fazer_semanal = '--semanal' in args or '--all' in args or len([a for a in args if a.startswith('--')]) == 0
    fazer_mensal = '--mensal' in args or '--all' in args or len([a for a in args if a.startswith('--')]) == 0

    logger.info(f"Granularidades: Diário={fazer_diario}, Semanal={fazer_semanal}, Mensal={fazer_mensal}")

    # Carrega dados
    df = carregar_dados(NOME_ARQUIVO)
    if df is None:
        logger.error("Falha ao carregar dados")
        return 1

    df = preparar_dados(df)
    if df.empty:
        logger.error("Nenhum dado válido após preparação")
        return 1

    # Configura IA
    modelo = configurar_ia()

    # Processa cada granularidade
    arquivos_gerados = []

    if fazer_mensal:
        resultado_mensal = processar_granularidade(df, 'mes', 'mensal', modelo)
        if salvar_json(resultado_mensal, 'vendas_mensal.json'):
            arquivos_gerados.append('vendas_mensal.json')

    if fazer_semanal:
        resultado_semanal = processar_granularidade(df, 'semana', 'semanal', modelo)
        if salvar_json(resultado_semanal, 'vendas_semanal.json'):
            arquivos_gerados.append('vendas_semanal.json')

    if fazer_diario:
        resultado_diario = processar_granularidade(df, 'dia', 'diario', modelo)
        if salvar_json(resultado_diario, 'vendas_diario.json'):
            arquivos_gerados.append('vendas_diario.json')

    # Gera arquivo consolidado (índice)
    consolidado = {
        "gerado_em": datetime.now().isoformat(),
        "arquivos": arquivos_gerados,
        "lojas": sorted(df['loja_id'].unique().tolist()),
        "periodo_dados": {
            "inicio": df['data_obj'].min().strftime('%Y-%m-%d'),
            "fim": df['data_obj'].max().strftime('%Y-%m-%d')
        }
    }
    salvar_json(consolidado, 'consolidado.json')

    # Estatísticas finais
    tempo_total = time.time() - inicio
    logger.info("\n" + "="*60)
    logger.info("📊 RESUMO DA EXECUÇÃO")
    logger.info("="*60)
    logger.info(f"⏱️  Tempo total: {tempo_total:.1f}s")
    logger.info(f"📁 Arquivos gerados: {len(arquivos_gerados)}")
    for arq in arquivos_gerados:
        logger.info(f"   - {PASTA_SAIDA}/{arq}")
    logger.info("="*60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

