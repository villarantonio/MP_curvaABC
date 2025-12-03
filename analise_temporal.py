# -*- coding: utf-8 -*-
"""
ANÁLISE TEMPORAL DE VENDAS: TOP/BOTTOM 10 MENSAL COM SAZONALIDADE
Gera rankings dinâmicos mês a mês com insights de IA para dashboards.

Estrutura de saída:
[
    {
        "id_loja": 1,
        "analises_mensais": {
            "2024-01": [{"produto": "...", "tipo": "TOP 10", ...}],
            ...
        }
    }
]
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Arquivos
NOME_ARQUIVO = "GMRMPMA (2)(Export).csv"
ARQUIVO_SAIDA = "analise_mensal_sazonal.json"

# Colunas do CSV
COL_LOJA = 'FtoResumoVendaGeralItem[loja_id]'
COL_PRODUTO = 'FtoResumoVendaGeralItem[material_descr]'
COL_VALOR = 'FtoResumoVendaGeralItem[vl_total]'
COL_DATA = 'FtoResumoVendaGeralItem[dt_contabil]'

# Parâmetros de análise
TOP_N = 10
BOTTOM_N = 10
PAUSA_ENTRE_REQUISICOES = 2.0  # segundos entre requisições
MAX_TENTATIVAS_API = 5   # tentativas para erros gerais
MAX_TENTATIVAS_RATE_LIMIT = 8  # tentativas extras para rate limit
DELAY_BASE_RATE_LIMIT = 30  # segundos base para rate limit
DELAY_ENTRE_CHAMADAS = 20.0  # segundos entre cada chamada (3 req/min seguro)

# API Key - carrega de variável de ambiente via .env
API_KEY = os.environ.get('GEMINI_API_KEY', '')

# Mapeamento de meses para contexto sazonal brasileiro
CONTEXTO_SAZONAL = {
    '01': {'estacao': 'Verão', 'eventos': 'Férias escolares, calor intenso', 'tendencia': 'bebidas geladas, saladas'},
    '02': {'estacao': 'Verão', 'eventos': 'Carnaval, calor', 'tendencia': 'bebidas, pratos leves'},
    '03': {'estacao': 'Outono', 'eventos': 'Volta às aulas, fim do verão', 'tendencia': 'transição cardápio'},
    '04': {'estacao': 'Outono', 'eventos': 'Páscoa, temperaturas amenas', 'tendencia': 'chocolates, pratos equilibrados'},
    '05': {'estacao': 'Outono', 'eventos': 'Dia das Mães, friagem', 'tendencia': 'aumento consumo, pratos reconfortantes'},
    '06': {'estacao': 'Inverno', 'eventos': 'Festa Junina, início frio', 'tendencia': 'comidas típicas, bebidas quentes'},
    '07': {'estacao': 'Inverno', 'eventos': 'Férias escolares, frio intenso', 'tendencia': 'sopas, caldos, churrasco'},
    '08': {'estacao': 'Inverno', 'eventos': 'Dia dos Pais, frio', 'tendencia': 'carnes, pratos quentes'},
    '09': {'estacao': 'Primavera', 'eventos': 'Início primavera, clima variável', 'tendencia': 'transição cardápio'},
    '10': {'estacao': 'Primavera', 'eventos': 'Dia das Crianças, esquenta', 'tendencia': 'combos família, porções'},
    '11': {'estacao': 'Primavera', 'eventos': 'Black Friday, calor chegando', 'tendencia': 'promoções, bebidas'},
    '12': {'estacao': 'Verão', 'eventos': 'Natal, Ano Novo, férias', 'tendencia': 'celebrações, alto movimento'}
}

# ==========================================
# 2. FUNÇÕES AUXILIARES
# ==========================================

def limpar_valor_monetario(valor: Any) -> float:
    """Converte valor monetário BR (1.234,56) para float."""
    if pd.isna(valor):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        try:
            return float(valor.strip().replace('.', '').replace(',', '.'))
        except ValueError:
            return 0.0
    return 0.0


def calcular_variacao(atual: float, anterior: float) -> tuple[float, str]:
    """
    Calcula variação percentual entre dois valores.

    Returns:
        Tupla (valor_percentual, texto_formatado)
    """
    if anterior > 0:
        delta = ((atual - anterior) / anterior) * 100
        return delta, f"{delta:+.1f}%"
    elif atual > 0:
        return 100.0, "Novo (sem vendas anteriores)"
    return 0.0, "Sem dados"


def extrair_nome_mes(mes_periodo: str) -> str:
    """Converte período (2025-01) para nome do mês em português."""
    meses = {
        '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março', '04': 'Abril',
        '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
        '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }
    try:
        ano, mes = mes_periodo.split('-')
        return f"{meses.get(mes, mes)}/{ano}"
    except ValueError:
        return mes_periodo


# ==========================================
# 3. INTEGRAÇÃO COM IA
# ==========================================

def configurar_ia() -> Optional[genai.GenerativeModel]:
    """Configura e retorna o modelo Gemini."""
    if not API_KEY:
        logger.warning("API Key não configurada. Análise IA será pulada.")
        return None

    try:
        genai.configure(api_key=API_KEY)
        modelo = genai.GenerativeModel(
            model_name="gemini-2.0-flash-lite",  # Modelo leve com rate limits mais altos
            generation_config={
                "temperature": 0.25,
                "response_mime_type": "application/json"
            }
        )
        logger.info("Modelo Gemini 2.0 Flash Lite configurado com sucesso")
        return modelo
    except Exception as e:
        logger.error(f"Erro ao configurar modelo: {e}")
        return None


def obter_contexto_sazonal(mes_ref: str) -> dict[str, str]:
    """
    Retorna contexto sazonal brasileiro para o mês especificado.

    Args:
        mes_ref: Período no formato '2024-01'

    Returns:
        Dicionário com estação, eventos e tendências do mês
    """
    try:
        _, mes = mes_ref.split('-')
        return CONTEXTO_SAZONAL.get(mes, {
            'estacao': 'N/A',
            'eventos': 'Período padrão',
            'tendencia': 'análise geral'
        })
    except ValueError:
        return {'estacao': 'N/A', 'eventos': 'N/A', 'tendencia': 'N/A'}


def construir_prompt_analise(
    id_loja: Any,
    mes_ref: str,
    nome_mes: str,
    lista_itens: list[dict],
    contexto_sazonal: dict[str, str],
    total_mensal: float
) -> str:
    """
    Constrói o prompt otimizado para análise de vendas mensais.

    O prompt é estruturado em seções claras para maximizar a qualidade
    das respostas da IA, focando em insights individuais sem comparações.

    Args:
        id_loja: Identificador da loja
        mes_ref: Período no formato '2024-01'
        nome_mes: Nome do mês em português
        lista_itens: Lista de produtos com dados de vendas
        contexto_sazonal: Dicionário com contexto sazonal do mês
        total_mensal: Valor total de vendas do mês (todos os produtos)

    Returns:
        Prompt formatado para a IA
    """
    # Separa itens TOP e BOTTOM para análise diferenciada
    tops = [i for i in lista_itens if 'TOP' in i.get('tipo', '')]
    bottoms = [i for i in lista_itens if 'BOTTOM' in i.get('tipo', '')]

    # Calcula métricas resumidas para contexto
    total_top = sum(i.get('venda_este_mes', 0) for i in tops)
    total_bottom = sum(i.get('venda_este_mes', 0) for i in bottoms)

    prompt = f"""# ANÁLISE DE PERFORMANCE MENSAL - RESTAURANTE

## 🎯 PAPEL
Você é um consultor sênior de gestão de restaurantes especializado em análise de cardápio e otimização de vendas no mercado brasileiro.

## 📊 CONTEXTO DO NEGÓCIO
- **Estabelecimento:** Restaurante/Churrascaria (Loja {id_loja})
- **Período:** {nome_mes}
- **Estação do ano:** {contexto_sazonal['estacao']}
- **Eventos/Contexto:** {contexto_sazonal['eventos']}

## 📈 VISÃO GERAL DOS DADOS
- **FATURAMENTO TOTAL DO MÊS:** R$ {total_mensal:,.2f}
- **TOP {TOP_N} produtos:** R$ {total_top:,.2f} em vendas (campeões do mês)
- **BOTTOM {BOTTOM_N} produtos:** R$ {total_bottom:,.2f} em vendas (menor performance)
- **Total de itens para análise:** {len(lista_itens)}

## 📋 DADOS DETALHADOS
Cada produto inclui: nome, categoria (TOP/BOTTOM), e valor vendido este mês.

```json
{json.dumps(lista_itens, ensure_ascii=False)}
```

## ✅ TAREFA
Analise CADA produto INDIVIDUALMENTE. Forneça um diagnóstico específico e uma ação prática.

### Para produtos TOP (Campeões):
- Identifique o potencial do produto
- Sugira oportunidades de maximização (combos, upselling, margem)

### Para produtos BOTTOM (Baixa performance):
- Diagnostique possível causa (sazonalidade, visibilidade, preço)
- Recomende ação específica (promoção, reformulação, reposicionamento)

### Fatores a considerar:
- **Sazonalidade:** {contexto_sazonal['estacao']} - influencia consumo
- **Eventos:** {contexto_sazonal['eventos']} - impactam comportamento
- **Categoria:** Carnes, bebidas e acompanhamentos têm dinâmicas diferentes

## 📝 FORMATO DE RESPOSTA (JSON)
Retorne EXATAMENTE um array JSON com um objeto para CADA produto:

```json
[
  {{
    "produto": "NOME_EXATO_COMO_NOS_DADOS",
    "diagnostico": "Diagnóstico direto sobre o produto (máx 80 chars)",
    "acao": "Ação prática e executável (máx 60 chars)"
  }}
]
```

## 💡 EXEMPLOS DE BOAS RESPOSTAS

```json
{{"produto": "PICANHA ANGUS", "diagnostico": "Produto estrela com alta margem e demanda constante", "acao": "Criar combo com acompanhamentos para aumentar ticket"}}
```

```json
{{"produto": "SOPA DE LEGUMES", "diagnostico": "Baixa procura típica no {contexto_sazonal['estacao'].lower()}", "acao": "Reduzir preparo ou pausar temporariamente"}}
```

```json
{{"produto": "CERVEJA ARTESANAL", "diagnostico": "Vendas abaixo do esperado para a categoria", "acao": "Promover degustação ou ajustar preço"}}
```

## ⚠️ REGRAS CRÍTICAS
1. Use EXATAMENTE o nome do produto como está nos dados
2. Diagnóstico deve ser DIRETO e ESPECÍFICO ao produto
3. Ação deve ser EXECUTÁVEL e PRÁTICA
4. NÃO faça comparações entre produtos ou períodos
5. NÃO mencione variações percentuais ou tendências
6. Foque no VALOR ABSOLUTO e no POTENCIAL do produto
7. Máximo 80 caracteres no diagnóstico e 60 na ação"""

    return prompt


def analisar_mes_com_ia(
    modelo: genai.GenerativeModel,
    id_loja: Any,
    mes_ref: str,
    lista_itens: list[dict],
    total_mensal: float,
    tentativas_max: int = MAX_TENTATIVAS_API
) -> list[dict]:
    """
    Analisa desempenho mensal de produtos usando IA com retry robusto.

    Implementa exponential backoff para lidar com rate limits e erros
    de conexão, garantindo resiliência nas chamadas à API.

    Para rate limit (429), usa delays maiores e mais tentativas.

    Args:
        modelo: Modelo Gemini configurado
        id_loja: Identificador da loja
        mes_ref: Período no formato '2024-01'
        lista_itens: Lista de produtos com dados de vendas
        total_mensal: Valor total de vendas do mês
        tentativas_max: Número máximo de tentativas em caso de erro

    Returns:
        Lista de dicionários com análises por produto
    """
    if not modelo or not lista_itens:
        return []

    nome_mes = extrair_nome_mes(mes_ref)
    contexto_sazonal = obter_contexto_sazonal(mes_ref)

    # Constrói prompt otimizado
    prompt = construir_prompt_analise(
        id_loja, mes_ref, nome_mes, lista_itens, contexto_sazonal, total_mensal
    )

    tentativas_rate_limit = 0  # Contador separado para rate limit
    tentativa = 0

    while tentativa < tentativas_max or tentativas_rate_limit < MAX_TENTATIVAS_RATE_LIMIT:
        tentativa += 1
        try:
            # Pausa entre chamadas para evitar rate limit
            time.sleep(DELAY_ENTRE_CHAMADAS)

            resposta = modelo.generate_content(prompt)

            if not resposta or not resposta.text:
                logger.warning(f"Resposta vazia da IA ({mes_ref})")
                continue

            resultado = json.loads(resposta.text)

            # Valida estrutura da resposta
            if not isinstance(resultado, list):
                logger.warning(f"Resposta não é lista: {type(resultado)}")
                return []

            # Valida que cada item tem os campos necessários
            for item in resultado:
                if not isinstance(item, dict):
                    continue
                # Garante campos mínimos
                item.setdefault('diagnostico', 'Análise indisponível')
                item.setdefault('acao', '-')

            logger.debug(f"IA retornou {len(resultado)} análises para {mes_ref}")
            return resultado

        except json.JSONDecodeError as e:
            logger.warning(f"Erro ao parsear JSON ({mes_ref}): {e}")
            return []

        except google_exceptions.ResourceExhausted:
            tentativas_rate_limit += 1
            # Delay progressivo: 30s, 60s, 90s, 120s... (mais agressivo para rate limit)
            tempo = DELAY_BASE_RATE_LIMIT * tentativas_rate_limit + random.uniform(0, 5)
            logger.warning(
                f"⚠️ Rate limit atingido! Tentativa {tentativas_rate_limit}/{MAX_TENTATIVAS_RATE_LIMIT}. "
                f"Aguardando {tempo:.0f}s..."
            )
            time.sleep(tempo)

            if tentativas_rate_limit >= MAX_TENTATIVAS_RATE_LIMIT:
                logger.error(f"❌ Rate limit persistente para {mes_ref}. Pulando.")
                return []

            # Não incrementa tentativa normal para rate limit
            tentativa -= 1
            continue

        except (google_exceptions.ServiceUnavailable,
                google_exceptions.DeadlineExceeded,
                ConnectionError) as e:
            tempo = (2 ** tentativa) + random.uniform(0, 1)
            logger.warning(f"Erro de conexão ({mes_ref}), tentativa {tentativa}/{tentativas_max}: {e}")
            if tentativa < tentativas_max:
                time.sleep(tempo)
            else:
                logger.error(f"Falha definitiva após {tentativas_max} tentativas para {mes_ref}")
                return []

        except Exception as e:
            logger.error(f"Erro inesperado ({mes_ref}): {type(e).__name__}: {e}")
            return []

    return []

# ==========================================
# 4. CARREGAMENTO E PREPARAÇÃO DOS DADOS
# ==========================================

def carregar_csv(caminho: str) -> Optional[pd.DataFrame]:
    """Carrega CSV com tratamento de encodings."""
    if not os.path.exists(caminho):
        logger.error(f"Arquivo não encontrado: {caminho}")
        return None

    encodings = ['latin1', 'utf-8', 'cp1252']

    for encoding in encodings:
        try:
            df = pd.read_csv(
                caminho,
                sep=';',
                encoding=encoding,
                on_bad_lines='skip',
                dtype={COL_LOJA: str}
            )
            logger.info(f"CSV carregado (encoding: {encoding}) - {len(df)} registros")
            return df
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Erro ao carregar CSV: {e}")
            return None

    logger.error("Não foi possível carregar o CSV")
    return None


def preparar_dados(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Limpa e prepara dados para análise temporal."""
    # Valida colunas necessárias
    colunas_necessarias = [COL_LOJA, COL_PRODUTO, COL_VALOR, COL_DATA]
    faltantes = [c for c in colunas_necessarias if c not in df.columns]
    if faltantes:
        logger.error(f"Colunas faltantes: {faltantes}")
        return None

    df = df.copy()

    # Limpa valores monetários
    df['valor_limpo'] = df[COL_VALOR].apply(limpar_valor_monetario)
    df = df[df['valor_limpo'] > 0]

    # Processa datas
    df['data_obj'] = pd.to_datetime(df[COL_DATA], dayfirst=True, errors='coerce')
    df['mes_ano'] = df['data_obj'].dt.to_period('M').astype(str)
    df = df.dropna(subset=['mes_ano'])

    # Padroniza produtos
    df['produto'] = (
        df[COL_PRODUTO]
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r'\s+', ' ', regex=True)
    )
    df['loja_id'] = df[COL_LOJA].astype(str)

    # Agrupamento mensal
    df_agrupado = (
        df.groupby(['loja_id', 'mes_ano', 'produto'])['valor_limpo']
        .sum()
        .reset_index()
    )

    logger.info(f"Dados preparados: {len(df_agrupado)} registros agregados")
    return df_agrupado


# ==========================================
# 5. PROCESSAMENTO DE RANKING MENSAL
# ==========================================

def selecionar_top_bottom(df_mes: pd.DataFrame) -> pd.DataFrame:
    """Seleciona TOP N e BOTTOM N do mês."""
    df_mes = df_mes.sort_values(by='valor_limpo', ascending=False)
    total = len(df_mes)

    if total == 0:
        return pd.DataFrame()

    if total <= (TOP_N + BOTTOM_N):
        df_mes = df_mes.copy()
        df_mes['tipo_ranking'] = 'GERAL'
        return df_mes

    top = df_mes.head(TOP_N).copy()
    top['tipo_ranking'] = f'TOP {TOP_N}'

    bottom = df_mes.tail(BOTTOM_N).copy()
    bottom['tipo_ranking'] = f'BOTTOM {BOTTOM_N}'

    return pd.concat([top, bottom], ignore_index=True)


def processar_mes(
    df_loja: pd.DataFrame,
    mes_atual: str
) -> tuple[list[dict], float]:
    """
    Processa dados de um mês específico, gerando ranking TOP/BOTTOM.

    Utiliza operações vetorizadas do pandas para melhor performance.
    Retorna também o total mensal de vendas (todos os produtos).

    Args:
        df_loja: DataFrame com dados da loja
        mes_atual: Período atual no formato '2024-01'

    Returns:
        Tupla com (lista de dicionários com dados de cada produto, total mensal)
    """
    df_mes = df_loja[df_loja['mes_ano'] == mes_atual].copy()

    # Calcula o TOTAL MENSAL de todas as vendas (não apenas TOP/BOTTOM)
    total_mensal = df_mes['valor_limpo'].sum()

    selecao = selecionar_top_bottom(df_mes)

    if selecao.empty:
        return [], total_mensal

    # Converte para lista de dicionários (sem comparações)
    itens = selecao.apply(
        lambda row: {
            "produto": row['produto'],
            "tipo": row['tipo_ranking'],
            "venda_este_mes": round(row['valor_limpo'], 2)
        },
        axis=1
    ).tolist()

    return itens, total_mensal


def aplicar_analise_ia(
    modelo: Optional[genai.GenerativeModel],
    id_loja: str,
    mes: str,
    itens: list[dict],
    total_mensal: float
) -> list[dict]:
    """Aplica análise IA aos itens do mês."""
    if not modelo:
        # Adiciona campo vazio se não houver IA
        for item in itens:
            item['analise_ia'] = {"diagnostico": "IA não disponível", "acao": "-"}
        return itens

    resultado_ia = analisar_mes_com_ia(modelo, id_loja, mes, itens, total_mensal)

    # Mapeia resultados por produto
    dict_analises = {}
    for item in resultado_ia:
        if isinstance(item, dict) and 'produto' in item:
            dict_analises[item['produto']] = item

    # Aplica análises aos itens
    for item in itens:
        analise = dict_analises.get(item['produto'], {})
        item['analise_ia'] = {
            "diagnostico": analise.get('diagnostico', 'Análise indisponível'),
            "acao": analise.get('acao', '-')
        }

    return itens


def processar_loja(
    df_loja: pd.DataFrame,
    id_loja: str,
    modelo: Optional[genai.GenerativeModel]
) -> dict:
    """Processa todos os meses de uma loja."""
    meses = sorted(df_loja['mes_ano'].unique())
    analises_mensais = {}

    for i, mes_atual in enumerate(meses):
        # Processa ranking do mês e calcula total mensal
        itens, total_mensal = processar_mes(df_loja, mes_atual)

        if not itens:
            continue

        logger.info(f"  📅 {extrair_nome_mes(mes_atual)}: {len(itens)} itens | Total: R$ {total_mensal:,.2f}")

        # Aplica análise IA
        itens = aplicar_analise_ia(modelo, id_loja, mes_atual, itens, total_mensal)

        # Adiciona total mensal ao resultado
        analises_mensais[mes_atual] = {
            "total_mensal": round(total_mensal, 2),
            "itens": itens
        }

        # Pausa entre requisições
        if modelo and i < len(meses) - 1:
            time.sleep(PAUSA_ENTRE_REQUISICOES)

    # Converte ID para int se possível
    try:
        id_loja_final = int(id_loja)
    except (ValueError, TypeError):
        id_loja_final = id_loja

    return {
        "id_loja": id_loja_final,
        "analises_mensais": analises_mensais
    }


def salvar_resultado(resultado: list[dict], caminho: str) -> bool:
    """
    Salva resultado em arquivo JSON com tratamento de erros.

    Args:
        resultado: Lista de resultados por loja
        caminho: Caminho do arquivo de saída

    Returns:
        True se salvou com sucesso, False caso contrário
    """
    try:
        # Garante que o diretório existe
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)

        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False, default=str)

        # Verifica tamanho do arquivo gerado
        tamanho_kb = Path(caminho).stat().st_size / 1024
        logger.info(f"Resultado salvo em: {caminho} ({tamanho_kb:.1f} KB)")
        return True

    except IOError as e:
        logger.error(f"Erro ao salvar arquivo: {e}")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar: {type(e).__name__}: {e}")
        return False


def gerar_estatisticas_execucao(resultado: list[dict]) -> dict[str, Any]:
    """
    Gera estatísticas da execução para logging.

    Args:
        resultado: Lista de resultados processados

    Returns:
        Dicionário com estatísticas
    """
    total_lojas = len(resultado)
    total_meses = sum(len(r.get('analises_mensais', {})) for r in resultado)
    total_itens = sum(
        len(mes_data.get('itens', []))
        for r in resultado
        for mes_data in r.get('analises_mensais', {}).values()
    )
    faturamento_total = sum(
        mes_data.get('total_mensal', 0)
        for r in resultado
        for mes_data in r.get('analises_mensais', {}).values()
    )

    return {
        'lojas': total_lojas,
        'meses_analisados': total_meses,
        'itens_processados': total_itens,
        'faturamento_total': faturamento_total,
        'media_itens_por_mes': total_itens / total_meses if total_meses > 0 else 0
    }


# ==========================================
# 6. FUNÇÃO PRINCIPAL
# ==========================================

def main() -> None:
    """
    Executa análise temporal completa de vendas por loja.

    Fluxo:
    1. Carrega e valida dados do CSV
    2. Prepara dados (limpeza, agregação mensal)
    3. Configura modelo de IA
    4. Para cada loja: processa rankings mensais com análise IA
    5. Salva resultado em JSON
    """
    logger.info("=" * 60)
    logger.info("ANÁLISE TEMPORAL MENSAL - TOP/BOTTOM 10 COM IA")
    logger.info("=" * 60)

    inicio = time.time()

    # 1. Carrega dados
    df_raw = carregar_csv(NOME_ARQUIVO)
    if df_raw is None:
        return

    # 2. Prepara dados
    df = preparar_dados(df_raw)
    if df is None:
        return

    # Libera memória do DataFrame original
    del df_raw

    # 3. Configura IA
    modelo = configurar_ia()

    if modelo:
        logger.info("Análise com IA habilitada - insights serão gerados")
    else:
        logger.warning("Análise sem IA - apenas rankings serão gerados")

    # 4. Processa cada loja
    lojas = sorted(df['loja_id'].unique())
    total_lojas = len(lojas)

    # Estatísticas de meses disponíveis
    meses_disponiveis = sorted(df['mes_ano'].unique())
    logger.info(f"Período de análise: {meses_disponiveis[0]} a {meses_disponiveis[-1]}")
    logger.info(f"Processando {total_lojas} lojas...")

    resultado = []
    for idx, id_loja in enumerate(lojas, 1):
        logger.info(f"🏢 Loja {id_loja} ({idx}/{total_lojas})")

        df_loja = df[df['loja_id'] == id_loja]
        resultado_loja = processar_loja(df_loja, id_loja, modelo)
        resultado.append(resultado_loja)

    # 5. Salva resultado
    if salvar_resultado(resultado, ARQUIVO_SAIDA):
        # Estatísticas finais
        stats = gerar_estatisticas_execucao(resultado)
        tempo_total = time.time() - inicio

        logger.info("=" * 60)
        logger.info("✅ PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        logger.info("-" * 60)
        logger.info(f"📊 Lojas processadas: {stats['lojas']}")
        logger.info(f"📅 Meses analisados: {stats['meses_analisados']}")
        logger.info(f"📦 Itens processados: {stats['itens_processados']}")
        logger.info(f"💰 Faturamento total: R$ {stats['faturamento_total']:,.2f}")
        logger.info(f"⏱️  Tempo total: {tempo_total:.1f} segundos")
        logger.info(f"📁 Arquivo gerado: {ARQUIVO_SAIDA}")
        logger.info("-" * 60)
        logger.info("Estrutura: {id_loja, analises_mensais: {mes: {total_mensal, itens}}}")
        logger.info("=" * 60)
    else:
        logger.error("❌ Falha ao salvar resultado final")


if __name__ == "__main__":
    main()