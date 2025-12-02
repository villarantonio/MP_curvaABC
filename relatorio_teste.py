# -*- coding: utf-8 -*-
"""
SCRIPT ROBUSTO: CURVA ABC COM ANÁLISE IA E SISTEMA DE RETENTATIVA
Gera relatório ABC com insights de tendência usando Google Gemini.
"""

from __future__ import annotations

import logging
import os
import json
import time
import random
from typing import Any, Optional
from pathlib import Path

import pandas as pd
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

# ==========================================
# 1. CONFIGURAÇÕES E CONSTANTES
# ==========================================

# Configuração de logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configurações do arquivo
NOME_ARQUIVO = "GMRMPMA (2)(Export).csv"
ARQUIVO_SAIDA = "analise_abc_final.json"

# Colunas esperadas do CSV
COL_LOJA = 'FtoResumoVendaGeralItem[loja_id]'
COL_PRODUTO = 'FtoResumoVendaGeralItem[material_descr]'
COL_VALOR = 'FtoResumoVendaGeralItem[vl_total]'
COL_DATA = 'FtoResumoVendaGeralItem[dt_contabil]'

# Parâmetros da Curva ABC
LIMITE_CLASSE_A = 80  # Percentual acumulado para classe A
LIMITE_CLASSE_B = 95  # Percentual acumulado para classe B

# Parâmetros de processamento IA
TAMANHO_LOTE_IA = 15
PAUSA_ENTRE_LOTES = 1.5  # segundos
MAX_TENTATIVAS_API = 3

# API Key - carrega de variável de ambiente (NUNCA commitar chaves no código!)
API_KEY = os.environ.get('GEMINI_API_KEY', '')

# ==========================================
# 2. FUNÇÕES AUXILIARES
# ==========================================

def limpar_valor_monetario(valor: Any) -> float:
    """
    Converte valor monetário brasileiro (1.234,56) para float.

    Args:
        valor: Valor a ser convertido (string ou numérico)

    Returns:
        Valor como float, ou 0.0 em caso de erro
    """
    if pd.isna(valor):
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    if isinstance(valor, str):
        try:
            # Remove pontos de milhar e troca vírgula por ponto
            valor_limpo = valor.strip().replace('.', '').replace(',', '.')
            return float(valor_limpo)
        except ValueError:
            logger.warning(f"Não foi possível converter valor: '{valor}'")
            return 0.0

    return 0.0


def classificar_abc(valor_acumulado: float) -> str:
    """
    Classifica item na curva ABC baseado no percentual acumulado.

    Args:
        valor_acumulado: Percentual acumulado de vendas

    Returns:
        Classe 'A', 'B' ou 'C'
    """
    if valor_acumulado <= LIMITE_CLASSE_A:
        return 'A'
    elif valor_acumulado <= LIMITE_CLASSE_B:
        return 'B'
    return 'C'


def validar_colunas_csv(df: pd.DataFrame) -> bool:
    """
    Valida se o DataFrame contém todas as colunas necessárias.

    Args:
        df: DataFrame a ser validado

    Returns:
        True se válido, False caso contrário
    """
    colunas_requeridas = [COL_LOJA, COL_PRODUTO, COL_VALOR, COL_DATA]
    colunas_faltantes = [col for col in colunas_requeridas if col not in df.columns]

    if colunas_faltantes:
        logger.error(f"Colunas faltantes no CSV: {colunas_faltantes}")
        logger.info(f"Colunas disponíveis: {list(df.columns)}")
        return False

    return True


# ==========================================
# 3. FUNÇÕES DE INTEGRAÇÃO COM IA
# ==========================================

def configurar_ia() -> Optional[genai.GenerativeModel]:
    """
    Configura e retorna o modelo Gemini para análise.

    Returns:
        Modelo configurado ou None se não disponível
    """
    if not API_KEY:
        logger.warning("API Key não configurada. Análise IA será pulada.")
        return None

    try:
        genai.configure(api_key=API_KEY)
        modelo = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "application/json"
            }
        )
        logger.info("Modelo Gemini configurado com sucesso")
        return modelo
    except Exception as e:
        logger.error(f"Erro ao configurar modelo Gemini: {e}")
        return None


def analisar_lote_ia_robusto(
    modelo: genai.GenerativeModel,
    id_loja: Any,
    lote_itens: list[dict],
    tentativas_max: int = MAX_TENTATIVAS_API
) -> list[dict]:
    """
    Envia lote de itens para análise IA com sistema de retentativa.

    Implementa exponential backoff para lidar com erros temporários
    como RemoteDisconnected, Timeout, rate limiting, etc.

    Args:
        modelo: Modelo Gemini configurado
        id_loja: Identificador da loja
        lote_itens: Lista de itens para análise
        tentativas_max: Número máximo de tentativas

    Returns:
        Lista de análises ou lista vazia em caso de falha
    """
    if not modelo:
        return []

    if not lote_itens:
        return []

    prompt = f"""
    Analise estes itens da Loja {id_loja} (Cardápio Restaurante).
    Retorne JSON LISTA estrito: [ {{"produto": "Nome", "analise": "Frase curta sobre tendência (Alta/Queda/Sazonal)"}} ]

    DADOS:
    {json.dumps(lote_itens, ensure_ascii=False)}
    """

    for tentativa in range(1, tentativas_max + 1):
        try:
            resposta = modelo.generate_content(prompt)

            # Valida se há resposta
            if not resposta or not resposta.text:
                logger.warning(f"Resposta vazia da IA na tentativa {tentativa}")
                continue

            # Parse e validação do JSON
            resultado = json.loads(resposta.text)

            # Valida estrutura da resposta
            if not isinstance(resultado, list):
                logger.warning(f"Resposta IA não é lista: {type(resultado)}")
                return []

            return resultado

        except json.JSONDecodeError as e:
            logger.warning(f"Erro ao parsear JSON da IA: {e}")
            return []

        except google_exceptions.ResourceExhausted as e:
            tempo_espera = (2 ** tentativa) + random.uniform(0, 1)
            logger.warning(f"Rate limit atingido. Aguardando {tempo_espera:.1f}s...")
            time.sleep(tempo_espera)

        except (google_exceptions.ServiceUnavailable,
                google_exceptions.DeadlineExceeded,
                ConnectionError) as e:
            tempo_espera = (2 ** tentativa) + random.uniform(0, 1)
            logger.warning(f"Erro de conexão na tentativa {tentativa}/{tentativas_max}: {e}")

            if tentativa < tentativas_max:
                logger.info(f"Tentando novamente em {tempo_espera:.1f}s...")
                time.sleep(tempo_espera)
            else:
                logger.error("Falha definitiva neste lote após todas as tentativas.")
                return []

        except Exception as e:
            logger.error(f"Erro inesperado na análise IA: {type(e).__name__}: {e}")
            return []

    return []

# ==========================================
# 4. FUNÇÕES DE PROCESSAMENTO DE DADOS
# ==========================================

def carregar_csv(caminho: str) -> Optional[pd.DataFrame]:
    """
    Carrega arquivo CSV com tratamento de diferentes encodings.

    Args:
        caminho: Caminho para o arquivo CSV

    Returns:
        DataFrame carregado ou None em caso de erro
    """
    if not os.path.exists(caminho):
        logger.error(f"Arquivo CSV não encontrado: {caminho}")
        return None

    encodings = ['latin1', 'utf-8', 'cp1252', 'iso-8859-1']

    for encoding in encodings:
        try:
            df = pd.read_csv(
                caminho,
                sep=';',
                encoding=encoding,
                on_bad_lines='skip',
                dtype={COL_LOJA: str}  # Preserva ID como string
            )
            logger.info(f"CSV carregado com sucesso (encoding: {encoding})")
            logger.info(f"Total de registros: {len(df)}")
            return df
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Erro ao carregar CSV com {encoding}: {e}")
            continue

    logger.error("Não foi possível carregar o CSV com nenhum encoding suportado")
    return None


def preparar_dados(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Limpa e prepara os dados para análise ABC.

    Args:
        df: DataFrame bruto do CSV

    Returns:
        DataFrame preparado ou None em caso de erro
    """
    # Validação de colunas
    if not validar_colunas_csv(df):
        return None

    # Cria cópia para não modificar original
    df = df.copy()

    # Converte valores monetários
    df['valor_limpo'] = df[COL_VALOR].apply(limpar_valor_monetario)

    # Remove registros com valor zero ou negativo
    registros_antes = len(df)
    df = df[df['valor_limpo'] > 0]
    registros_removidos = registros_antes - len(df)

    if registros_removidos > 0:
        logger.info(f"Removidos {registros_removidos} registros com valor <= 0")

    # Tratamento de data
    df['data_obj'] = pd.to_datetime(
        df[COL_DATA],
        dayfirst=True,
        errors='coerce'
    )

    # Verifica datas inválidas
    datas_invalidas = df['data_obj'].isna().sum()
    if datas_invalidas > 0:
        logger.warning(f"Encontradas {datas_invalidas} datas inválidas")

    # Cria período mês/ano
    df['mes_ano'] = df['data_obj'].dt.to_period('M').astype(str)
    df = df.dropna(subset=['mes_ano'])

    # Padroniza nomes de produtos
    df[COL_PRODUTO] = (
        df[COL_PRODUTO]
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r'\s+', ' ', regex=True)  # Remove espaços múltiplos
    )

    # Remove produtos vazios ou inválidos
    df = df[df[COL_PRODUTO].notna() & (df[COL_PRODUTO] != '') & (df[COL_PRODUTO] != 'NAN')]

    logger.info(f"Dados preparados: {len(df)} registros válidos")
    return df


def gerar_historico_vendas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gera histórico de vendas mensais agrupado por loja e produto.

    Args:
        df: DataFrame preparado

    Returns:
        DataFrame com totais e histórico por produto/loja
    """
    logger.info("Gerando histórico de vendas...")

    # Agrupa vendas por mês
    historico_mensal = (
        df.groupby([COL_LOJA, COL_PRODUTO, 'mes_ano'])['valor_limpo']
        .sum()
        .reset_index()
    )

    # Cria dicionário de histórico para cada produto
    def criar_dict_historico(grupo: pd.DataFrame) -> dict:
        return dict(zip(grupo['mes_ano'], grupo['valor_limpo'].round(2)))

    df_historico = (
        historico_mensal
        .groupby([COL_LOJA, COL_PRODUTO], group_keys=False)
        .apply(criar_dict_historico, include_groups=False)
        .reset_index(name='historico_vendas')
    )

    # Calcula total de vendas por produto
    df_total = (
        df.groupby([COL_LOJA, COL_PRODUTO])['valor_limpo']
        .sum()
        .reset_index(name='total_vendas')
    )

    # Merge histórico com totais
    df_final = pd.merge(df_total, df_historico, on=[COL_LOJA, COL_PRODUTO])

    logger.info(f"Histórico gerado: {len(df_final)} produtos únicos")
    return df_final


def processar_loja(
    df_loja: pd.DataFrame,
    id_loja: str,
    modelo: Optional[genai.GenerativeModel]
) -> dict:
    """
    Processa dados de uma loja individual: curva ABC e análise IA.

    Args:
        df_loja: DataFrame com dados da loja
        id_loja: Identificador da loja
        modelo: Modelo Gemini ou None

    Returns:
        Dicionário com dados processados da loja
    """
    # Ordena por vendas (maior para menor)
    df_loja = df_loja.sort_values(by='total_vendas', ascending=False).copy()

    # Calcula curva ABC
    total_vendas = df_loja['total_vendas'].sum()

    if total_vendas == 0:
        logger.warning(f"Loja {id_loja} sem vendas válidas")
        return {"id_loja": id_loja, "itens": []}

    df_loja['percentual'] = (df_loja['total_vendas'] / total_vendas * 100)
    df_loja['acumulado'] = df_loja['percentual'].cumsum()
    df_loja['classe'] = df_loja['acumulado'].apply(classificar_abc)

    # Monta lista de itens (usando to_dict para melhor performance)
    itens_loja = df_loja.apply(
        lambda row: {
            "produto": row[COL_PRODUTO],
            "valor_total": round(row['total_vendas'], 2),
            "classe": row['classe'],
            "historico": row['historico_vendas']
        },
        axis=1
    ).tolist()

    # Análise IA com lotes
    if modelo:
        itens_loja = processar_analise_ia(modelo, id_loja, itens_loja)

    # Converte ID para int se possível, senão mantém string
    try:
        id_loja_final = int(id_loja)
    except (ValueError, TypeError):
        id_loja_final = str(id_loja)

    return {"id_loja": id_loja_final, "itens": itens_loja}


def processar_analise_ia(
    modelo: genai.GenerativeModel,
    id_loja: str,
    itens: list[dict]
) -> list[dict]:
    """
    Processa análise IA em lotes para todos os itens de uma loja.

    Args:
        modelo: Modelo Gemini configurado
        id_loja: Identificador da loja
        itens: Lista de itens para análise

    Returns:
        Lista de itens com análise IA adicionada
    """
    analises_finais = []
    total_lotes = (len(itens) + TAMANHO_LOTE_IA - 1) // TAMANHO_LOTE_IA

    for i, k in enumerate(range(0, len(itens), TAMANHO_LOTE_IA)):
        lote = itens[k:k + TAMANHO_LOTE_IA]

        logger.info(f"  Processando lote {i + 1}/{total_lotes} ({len(lote)} itens)")

        # Prepara dados mínimos para IA
        lote_ia = [
            {
                'produto': item['produto'],
                'classe': item['classe'],
                'historico': item['historico']
            }
            for item in lote
        ]

        # Chamada à IA com retentativa
        resultado_ia = analisar_lote_ia_robusto(modelo, id_loja, lote_ia)

        # Mapeia resultados
        dict_analises = {
            item.get('produto', ''): item.get('analise', '')
            for item in resultado_ia
            if isinstance(item, dict)
        }

        # Adiciona análise a cada item
        for item in lote:
            item['analise_ia'] = dict_analises.get(
                item['produto'],
                "Análise indisponível"
            )
            analises_finais.append(item)

        # Pausa entre lotes para evitar rate limiting
        if k + TAMANHO_LOTE_IA < len(itens):
            time.sleep(PAUSA_ENTRE_LOTES)

    return analises_finais


def salvar_resultado(resultado: list[dict], caminho: str) -> bool:
    """
    Salva resultado em arquivo JSON.

    Args:
        resultado: Lista de resultados por loja
        caminho: Caminho do arquivo de saída

    Returns:
        True se salvou com sucesso
    """
    try:
        # Cria diretório se não existir
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)

        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(
                resultado,
                f,
                indent=2,
                ensure_ascii=False,
                default=str
            )

        logger.info(f"Resultado salvo em: {caminho}")
        return True

    except IOError as e:
        logger.error(f"Erro ao salvar arquivo: {e}")
        return False


# ==========================================
# 5. FUNÇÃO PRINCIPAL
# ==========================================

def main() -> None:
    """
    Função principal: orquestra o processamento completo.
    """
    logger.info("=" * 50)
    logger.info("INICIANDO ANÁLISE CURVA ABC COM IA")
    logger.info("=" * 50)

    # 1. Carregar dados
    df = carregar_csv(NOME_ARQUIVO)
    if df is None:
        return

    # 2. Preparar dados
    df = preparar_dados(df)
    if df is None:
        return

    # 3. Gerar histórico
    df_processado = gerar_historico_vendas(df)

    # 4. Configurar IA
    modelo = configurar_ia()

    # 5. Processar lojas
    lista_lojas = df_processado[COL_LOJA].unique()
    total_lojas = len(lista_lojas)

    logger.info(f"Iniciando processamento de {total_lojas} lojas...")

    resultado_final = []

    for idx, id_loja in enumerate(lista_lojas, 1):
        logger.info(f"Processando Loja {id_loja} ({idx}/{total_lojas})")

        df_loja = df_processado[df_processado[COL_LOJA] == id_loja]
        resultado_loja = processar_loja(df_loja, id_loja, modelo)
        resultado_final.append(resultado_loja)

    # 6. Salvar resultado
    if salvar_resultado(resultado_final, ARQUIVO_SAIDA):
        logger.info("=" * 50)
        logger.info("PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        logger.info(f"Total de lojas processadas: {total_lojas}")
        logger.info(f"Arquivo gerado: {ARQUIVO_SAIDA}")
        logger.info("=" * 50)
    else:
        logger.error("Falha ao salvar resultado final")


if __name__ == "__main__":
    main()