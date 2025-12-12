# -*- coding: utf-8 -*-
"""
ANÃLISE TEMPORAL DE VENDAS - loja 122
Processa APENAS a loja 122 para evitar rate limit da API.
"""

from __future__ import annotations

import logging
import os
import sys
import json
import time
import random
from typing import Any, Optional
from pathlib import Path

import pandas as pd
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from dotenv import load_dotenv

# Carrega variÃ¡veis do arquivo .env
load_dotenv()

# ==========================================
# CONFIGURAÃ‡Ã•ES
# ==========================================

# ID DA LOJA QUE ESTE SCRIPT PROCESSA
LOJA_ID = "12"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Arquivos - aceita argumento de linha de comando ou usa valor padrÃ£o
NOME_ARQUIVO = sys.argv[1] if len(sys.argv) > 1 else "GMRMPMA (2)(Export).csv"
ARQUIVO_SAIDA = f"analise_temporal_loja_{LOJA_ID}.json"

# Colunas do CSV
COL_LOJA = 'FtoResumoVendaGeralItem[loja_id]'
COL_PRODUTO = 'FtoResumoVendaGeralItem[material_descr]'
COL_VALOR = 'FtoResumoVendaGeralItem[vl_total]'
COL_DATA = 'FtoResumoVendaGeralItem[dt_contabil]'

# ParÃ¢metros de anÃ¡lise
TOP_N = 10
BOTTOM_N = 10
PAUSA_ENTRE_REQUISICOES = 2.0
MAX_TENTATIVAS_API = 5
MAX_TENTATIVAS_RATE_LIMIT = 8
DELAY_BASE_RATE_LIMIT = 30
DELAY_ENTRE_CHAMADAS = 35.0  # 35 segundos entre cada chamada

# API Key
API_KEY = os.environ.get('GEMINI_API_KEY', '')

# Contexto sazonal brasileiro
CONTEXTO_SAZONAL = {
    '01': {'estacao': 'VerÃ£o', 'eventos': 'FÃ©rias escolares, calor intenso', 'tendencia': 'bebidas geladas, saladas'},
    '02': {'estacao': 'VerÃ£o', 'eventos': 'Carnaval, calor', 'tendencia': 'bebidas, pratos leves'},
    '03': {'estacao': 'Outono', 'eventos': 'Volta Ã s aulas, fim do verÃ£o', 'tendencia': 'transiÃ§Ã£o cardÃ¡pio'},
    '04': {'estacao': 'Outono', 'eventos': 'PÃ¡scoa, temperaturas amenas', 'tendencia': 'chocolates, pratos equilibrados'},
    '05': {'estacao': 'Outono', 'eventos': 'Dia das MÃ£es, friagem', 'tendencia': 'aumento consumo, pratos reconfortantes'},
    '06': {'estacao': 'Inverno', 'eventos': 'Festa Junina, inÃ­cio frio', 'tendencia': 'comidas tÃ­picas, bebidas quentes'},
    '07': {'estacao': 'Inverno', 'eventos': 'FÃ©rias escolares, frio intenso', 'tendencia': 'sopas, caldos, churrasco'},
    '08': {'estacao': 'Inverno', 'eventos': 'Dia dos Pais, frio', 'tendencia': 'carnes, pratos quentes'},
    '09': {'estacao': 'Primavera', 'eventos': 'InÃ­cio primavera, clima variÃ¡vel', 'tendencia': 'transiÃ§Ã£o cardÃ¡pio'},
    '10': {'estacao': 'Primavera', 'eventos': 'Dia das CrianÃ§as, esquenta', 'tendencia': 'combos famÃ­lia, porÃ§Ãµes'},
    '11': {'estacao': 'Primavera', 'eventos': 'Black Friday, calor chegando', 'tendencia': 'promoÃ§Ãµes, bebidas'},
    '12': {'estacao': 'VerÃ£o', 'eventos': 'Natal, Ano Novo, fÃ©rias', 'tendencia': 'celebraÃ§Ãµes, alto movimento'}
}

# ==========================================
# FUNÃ‡Ã•ES AUXILIARES
# ==========================================

def limpar_valor_monetario(valor: Any) -> float:
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


def extrair_nome_mes(mes_periodo: str) -> str:
    meses = {
        '01': 'Janeiro', '02': 'Fevereiro', '03': 'MarÃ§o', '04': 'Abril',
        '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
        '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }
    try:
        ano, mes = mes_periodo.split('-')
        return f"{meses.get(mes, mes)}/{ano}"
    except ValueError:
        return mes_periodo


def obter_contexto_sazonal(mes_ref: str) -> dict[str, str]:
    try:
        _, mes = mes_ref.split('-')
        return CONTEXTO_SAZONAL.get(mes, {
            'estacao': 'N/A', 'eventos': 'PerÃ­odo padrÃ£o', 'tendencia': 'anÃ¡lise geral'
        })
    except ValueError:
        return {'estacao': 'N/A', 'eventos': 'N/A', 'tendencia': 'N/A'}


# ==========================================
# INTEGRAÃ‡ÃƒO COM IA
# ==========================================

def configurar_ia() -> Optional[genai.GenerativeModel]:
    if not API_KEY:
        logger.warning("API Key nÃ£o configurada. AnÃ¡lise IA serÃ¡ pulada.")
        return None

    try:
        genai.configure(api_key=API_KEY)
        modelo = genai.GenerativeModel(
            model_name="gemini-2.0-flash-lite",
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


def construir_prompt_analise(
    id_loja: Any, mes_ref: str, nome_mes: str, lista_itens: list[dict],
    contexto_sazonal: dict[str, str], total_mensal: float
) -> str:
    tops = [i for i in lista_itens if 'TOP' in i.get('tipo', '')]
    bottoms = [i for i in lista_itens if 'BOTTOM' in i.get('tipo', '')]
    total_top = sum(i.get('venda_este_mes', 0) for i in tops)
    total_bottom = sum(i.get('venda_este_mes', 0) for i in bottoms)

    prompt = f"""# ANÃLISE DE PERFORMANCE MENSAL - RESTAURANTE

## ðŸŽ¯ PAPEL
VocÃª Ã© um consultor sÃªnior de gestÃ£o de restaurantes especializado em anÃ¡lise de cardÃ¡pio e otimizaÃ§Ã£o de vendas no mercado brasileiro.

## ðŸ“Š CONTEXTO DO NEGÃ“CIO
- **Estabelecimento:** Restaurante/Churrascaria (Loja {id_loja})
- **PerÃ­odo:** {nome_mes}
- **EstaÃ§Ã£o do ano:** {contexto_sazonal['estacao']}
- **Eventos/Contexto:** {contexto_sazonal['eventos']}

## ðŸ“ˆ VISÃƒO GERAL DOS DADOS
- **FATURAMENTO TOTAL DO MÃŠS:** R$ {total_mensal:,.2f}
- **TOP {TOP_N} produtos:** R$ {total_top:,.2f} em vendas (campeÃµes do mÃªs)
- **BOTTOM {BOTTOM_N} produtos:** R$ {total_bottom:,.2f} em vendas (menor performance)
- **Total de itens para anÃ¡lise:** {len(lista_itens)}

## ðŸ“‹ DADOS DETALHADOS
```json
{json.dumps(lista_itens, ensure_ascii=False)}
```

## âœ… TAREFA
Analise CADA produto INDIVIDUALMENTE. ForneÃ§a um diagnÃ³stico especÃ­fico e uma aÃ§Ã£o prÃ¡tica.

### Para produtos TOP (CampeÃµes):
- Identifique o potencial do produto
- Sugira oportunidades de maximizaÃ§Ã£o (combos, upselling, margem)

### Para produtos BOTTOM (Baixa performance):
- Diagnostique possÃ­vel causa (sazonalidade, visibilidade, preÃ§o)
- Recomende aÃ§Ã£o especÃ­fica (promoÃ§Ã£o, reformulaÃ§Ã£o, reposicionamento)

## ðŸ“ FORMATO DE RESPOSTA (JSON)
Retorne EXATAMENTE um array JSON com um objeto para CADA produto:
[
  {{"produto": "NOME_EXATO", "diagnostico": "DiagnÃ³stico direto (mÃ¡x 80 chars)", "acao": "AÃ§Ã£o prÃ¡tica (mÃ¡x 60 chars)"}}
]

## âš ï¸ REGRAS CRÃTICAS
1. Use EXATAMENTE o nome do produto como estÃ¡ nos dados
2. NÃƒO faÃ§a comparaÃ§Ãµes entre produtos ou perÃ­odos
3. NÃƒO mencione variaÃ§Ãµes percentuais ou tendÃªncias
4. Foque no VALOR ABSOLUTO e no POTENCIAL do produto"""

    return prompt


def limpar_json_resposta(texto: str) -> str:
    """Limpa e corrige JSON mal formatado da resposta da IA."""
    import re

    # Remove markdown code blocks se existirem
    texto = re.sub(r'^```json\s*', '', texto.strip())
    texto = re.sub(r'^```\s*', '', texto)
    texto = re.sub(r'\s*```$', '', texto)

    # Remove trailing commas antes de ] ou }
    texto = re.sub(r',\s*]', ']', texto)
    texto = re.sub(r',\s*}', '}', texto)

    # Tenta encontrar o array JSON se houver texto extra
    match = re.search(r'\[[\s\S]*\]', texto)
    if match:
        texto = match.group(0)

    return texto.strip()


def analisar_mes_com_ia(
    modelo: genai.GenerativeModel, id_loja: Any, mes_ref: str,
    lista_itens: list[dict], total_mensal: float, tentativas_max: int = MAX_TENTATIVAS_API
) -> list[dict]:
    if not modelo or not lista_itens:
        return []

    nome_mes = extrair_nome_mes(mes_ref)
    contexto_sazonal = obter_contexto_sazonal(mes_ref)
    prompt = construir_prompt_analise(id_loja, mes_ref, nome_mes, lista_itens, contexto_sazonal, total_mensal)

    tentativas_rate_limit = 0
    tentativas_json_error = 0
    max_tentativas_json = 3
    tentativa = 0

    while tentativa < tentativas_max or tentativas_rate_limit < MAX_TENTATIVAS_RATE_LIMIT:
        tentativa += 1
        try:
            time.sleep(DELAY_ENTRE_CHAMADAS)
            resposta = modelo.generate_content(prompt)

            if not resposta or not resposta.text:
                logger.warning(f"Resposta vazia da IA ({mes_ref})")
                continue

            # Limpa o JSON antes de parsear
            texto_limpo = limpar_json_resposta(resposta.text)
            resultado = json.loads(texto_limpo)

            if not isinstance(resultado, list):
                logger.warning(f"Resposta nÃ£o Ã© lista: {type(resultado)}")
                return []

            for item in resultado:
                if isinstance(item, dict):
                    item.setdefault('diagnostico', 'AnÃ¡lise indisponÃ­vel')
                    item.setdefault('acao', '-')

            logger.debug(f"IA retornou {len(resultado)} anÃ¡lises para {mes_ref}")
            return resultado

        except json.JSONDecodeError as e:
            tentativas_json_error += 1
            logger.warning(f"Erro ao parsear JSON ({mes_ref}), tentativa {tentativas_json_error}/{max_tentativas_json}: {e}")
            if tentativas_json_error >= max_tentativas_json:
                logger.error(f"âŒ JSON invÃ¡lido persistente para {mes_ref}. Pulando.")
                return []
            tentativa -= 1  # NÃ£o conta como tentativa normal
            continue

        except google_exceptions.ResourceExhausted:
            tentativas_rate_limit += 1
            tempo = DELAY_BASE_RATE_LIMIT * tentativas_rate_limit + random.uniform(0, 5)
            logger.warning(f"âš ï¸ Rate limit! Tentativa {tentativas_rate_limit}/{MAX_TENTATIVAS_RATE_LIMIT}. Aguardando {tempo:.0f}s...")
            time.sleep(tempo)

            if tentativas_rate_limit >= MAX_TENTATIVAS_RATE_LIMIT:
                logger.error(f"âŒ Rate limit persistente para {mes_ref}. Pulando.")
                return []
            tentativa -= 1
            continue

        except (google_exceptions.ServiceUnavailable, google_exceptions.DeadlineExceeded, ConnectionError) as e:
            tempo = (2 ** tentativa) + random.uniform(0, 1)
            logger.warning(f"Erro de conexÃ£o ({mes_ref}), tentativa {tentativa}/{tentativas_max}: {e}")
            if tentativa < tentativas_max:
                time.sleep(tempo)
            else:
                return []

        except Exception as e:
            logger.error(f"Erro inesperado ({mes_ref}): {type(e).__name__}: {e}")
            return []

    return []


# ==========================================
# CARREGAMENTO E PREPARAÃ‡ÃƒO DOS DADOS
# ==========================================

def carregar_csv(caminho: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(caminho):
        logger.error(f"Arquivo nÃ£o encontrado: {caminho}")
        return None

    encodings = ['latin1', 'utf-8', 'cp1252']
    for encoding in encodings:
        try:
            df = pd.read_csv(caminho, sep=';', encoding=encoding, on_bad_lines='skip', dtype={COL_LOJA: str})
            logger.info(f"CSV carregado (encoding: {encoding}) - {len(df)} registros")
            return df
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Erro ao carregar CSV: {e}")
            return None
    logger.error("NÃ£o foi possÃ­vel carregar o CSV")
    return None


def preparar_dados(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    colunas_necessarias = [COL_LOJA, COL_PRODUTO, COL_VALOR, COL_DATA]
    faltantes = [c for c in colunas_necessarias if c not in df.columns]
    if faltantes:
        logger.error(f"Colunas faltantes: {faltantes}")
        return None

    df = df.copy()
    df['valor_limpo'] = df[COL_VALOR].apply(limpar_valor_monetario)
    df = df[df['valor_limpo'] > 0]
    df['data_obj'] = pd.to_datetime(df[COL_DATA], dayfirst=True, errors='coerce')
    df['mes_ano'] = df['data_obj'].dt.to_period('M').astype(str)
    df = df.dropna(subset=['mes_ano'])
    df['produto'] = df[COL_PRODUTO].astype(str).str.strip().str.upper().str.replace(r'\s+', ' ', regex=True)
    df['loja_id'] = df[COL_LOJA].astype(str)

    df_agrupado = df.groupby(['loja_id', 'mes_ano', 'produto'])['valor_limpo'].sum().reset_index()
    logger.info(f"Dados preparados: {len(df_agrupado)} registros agregados")
    return df_agrupado


# ==========================================
# PROCESSAMENTO DE RANKING MENSAL
# ==========================================

def selecionar_top_bottom(df_mes: pd.DataFrame) -> pd.DataFrame:
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


def processar_mes(df_loja: pd.DataFrame, mes_atual: str) -> tuple[list[dict], float]:
    df_mes = df_loja[df_loja['mes_ano'] == mes_atual].copy()
    total_mensal = df_mes['valor_limpo'].sum()
    selecao = selecionar_top_bottom(df_mes)

    if selecao.empty:
        return [], total_mensal

    itens = selecao.apply(
        lambda row: {
            "produto": row['produto'],
            "tipo": row['tipo_ranking'],
            "venda_este_mes": round(row['valor_limpo'], 2)
        }, axis=1
    ).tolist()
    return itens, total_mensal


def aplicar_analise_ia(modelo: Optional[genai.GenerativeModel], id_loja: str, mes: str, itens: list[dict], total_mensal: float) -> list[dict]:
    if not modelo:
        for item in itens:
            item['analise_ia'] = {"diagnostico": "IA nÃ£o disponÃ­vel", "acao": "-"}
        return itens

    resultado_ia = analisar_mes_com_ia(modelo, id_loja, mes, itens, total_mensal)
    dict_analises = {item['produto']: item for item in resultado_ia if isinstance(item, dict) and 'produto' in item}

    for item in itens:
        analise = dict_analises.get(item['produto'], {})
        item['analise_ia'] = {
            "diagnostico": analise.get('diagnostico', 'AnÃ¡lise indisponÃ­vel'),
            "acao": analise.get('acao', '-')
        }
    return itens


def processar_loja(df_loja: pd.DataFrame, id_loja: str, modelo: Optional[genai.GenerativeModel]) -> dict:
    meses = sorted(df_loja['mes_ano'].unique())
    analises_mensais = {}

    for i, mes_atual in enumerate(meses):
        itens, total_mensal = processar_mes(df_loja, mes_atual)
        if not itens:
            continue

        logger.info(f"  ðŸ“… {extrair_nome_mes(mes_atual)}: {len(itens)} itens | Total: R$ {total_mensal:,.2f}")
        itens = aplicar_analise_ia(modelo, id_loja, mes_atual, itens, total_mensal)

        analises_mensais[mes_atual] = {
            "total_mensal": round(total_mensal, 2),
            "itens": itens
        }

        if modelo and i < len(meses) - 1:
            time.sleep(PAUSA_ENTRE_REQUISICOES)

    try:
        id_loja_final = int(id_loja)
    except (ValueError, TypeError):
        id_loja_final = id_loja

    return {"id_loja": id_loja_final, "analises_mensais": analises_mensais}


def salvar_resultado(resultado: list[dict], caminho: str) -> bool:
    try:
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False, default=str)
        tamanho_kb = Path(caminho).stat().st_size / 1024
        logger.info(f"Resultado salvo em: {caminho} ({tamanho_kb:.1f} KB)")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo: {e}")
        return False


# ==========================================
# FUNÃ‡ÃƒO PRINCIPAL
# ==========================================

def main() -> None:
    logger.info("=" * 60)
    logger.info(f"ANÃLISE TEMPORAL - LOJA {LOJA_ID}")
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
    del df_raw

    # 3. Filtra APENAS a loja especÃ­fica
    df_loja = df[df['loja_id'] == LOJA_ID]
    if df_loja.empty:
        logger.error(f"Loja {LOJA_ID} nÃ£o encontrada nos dados")
        return

    logger.info(f"Processando loja {LOJA_ID} com {len(df_loja)} registros")

    # 4. Configura IA
    modelo = configurar_ia()
    if modelo:
        logger.info("AnÃ¡lise com IA habilitada")
    else:
        logger.warning("AnÃ¡lise sem IA")

    # 5. Processa a loja
    meses_disponiveis = sorted(df_loja['mes_ano'].unique())
    logger.info(f"PerÃ­odo: {meses_disponiveis[0]} a {meses_disponiveis[-1]}")

    resultado_loja = processar_loja(df_loja, LOJA_ID, modelo)

    # 6. Salva resultado
    if salvar_resultado([resultado_loja], ARQUIVO_SAIDA):
        tempo_total = time.time() - inicio
        logger.info("=" * 60)
        logger.info("âœ… PROCESSAMENTO CONCLUÃDO!")
        logger.info(f"â±ï¸  Tempo total: {tempo_total:.1f} segundos")
        logger.info(f"ðŸ“ Arquivo: {ARQUIVO_SAIDA}")
        logger.info("=" * 60)
    else:
        logger.error("âŒ Falha ao salvar resultado")


if __name__ == "__main__":
    main()

