# 📊 Análise de Curva ABC com IA para Restaurantes

Sistema de análise de vendas para restaurantes que gera relatórios de **Curva ABC** e **Análise Temporal** com insights inteligentes usando **Google Gemini AI**.

---

## ✨ Funcionalidades

### 🔷 Análise Curva ABC (`relatorio_teste.py`)
- Classificação ABC (regra 80/95%) dos produtos por faturamento
- Histórico de vendas mensal por produto
- Insights de tendência (Alta/Queda/Sazonal) gerados por IA
- Processamento loja por loja
- Exportação em JSON estruturado

### 🔷 Análise Temporal Mensal (`analise_temporal.py`)
- Rankings **TOP 10** e **BOTTOM 10** por mês
- Comparativo mês a mês com variação percentual
- Contexto sazonal brasileiro (eventos, estações, feriados)
- Diagnósticos e ações recomendadas por IA
- Processamento loja por loja com histórico completo

### 🔷 Recursos Técnicos
- ✅ Retry com exponential backoff para chamadas à API
- ✅ Logging estruturado para debug e monitoramento
- ✅ Validação de dados e tratamento de erros robusto
- ✅ Type hints para melhor manutenibilidade
- ✅ Operações vetorizadas para performance otimizada

---

## 📋 Requisitos

- **Python 3.10+**
- pandas
- google-generativeai

### Instalação das Dependências

```bash
pip install pandas google-generativeai
```

---

## ⚙️ Configuração

### 1. API Key do Google Gemini

Configure a variável de ambiente `GEMINI_API_KEY`:

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY = "sua-api-key-aqui"
```

**Windows (CMD):**
```cmd
set GEMINI_API_KEY=sua-api-key-aqui
```

**Linux/macOS:**
```bash
export GEMINI_API_KEY="sua-api-key-aqui"
```

### 2. Arquivo de Dados (CSV)

O sistema espera um arquivo CSV com separador `;` e as seguintes colunas:

| Coluna | Descrição |
|--------|-----------|
| `FtoResumoVendaGeralItem[loja_id]` | ID da loja |
| `FtoResumoVendaGeralItem[material_descr]` | Nome do produto |
| `FtoResumoVendaGeralItem[vl_total]` | Valor total da venda |
| `FtoResumoVendaGeralItem[dt_contabil]` | Data da venda (DD/MM/YYYY) |

---

## 🚀 Uso

### Análise Curva ABC

```bash
python relatorio_teste.py
```

**Saída:** `analise_abc_final.json`

```json
[
  {
    "id_loja": 1,
    "itens": [
      {
        "produto": "PICANHA ANGUS",
        "valor_total": 45230.50,
        "classe": "A",
        "historico": {"2024-01": 3500.00, "2024-02": 4200.00},
        "analise_ia": "Produto líder com tendência de alta sazonal"
      }
    ]
  }
]
```

### Análise Temporal Mensal

```bash
python analise_temporal.py
```

**Saída:** `analise_mensal_sazonal.json`

```json
[
  {
    "id_loja": 1,
    "analises_mensais": {
      "2024-01": [
        {
          "produto": "COCA-COLA 350ML",
          "tipo": "TOP 10",
          "venda_este_mes": 1250.00,
          "venda_mes_passado": 980.00,
          "variacao": "+27.6%",
          "analise_ia": {
            "diagnostico": "Crescimento forte - verão impulsiona bebidas geladas",
            "acao": "Garantir estoque extra para fim de semana"
          }
        }
      ]
    }
  }
]
```

---

## 📁 Estrutura do Projeto

```
├── relatorio_teste.py      # Script principal - Análise Curva ABC
├── analise_temporal.py     # Script - Análise Temporal TOP/BOTTOM 10
├── .gitignore              # Arquivos ignorados pelo Git
├── README.md               # Documentação do projeto
└── [dados].csv             # Arquivo de dados (não versionado)
```

---

## 🔧 Principais Funções

### `relatorio_teste.py`

| Função | Descrição |
|--------|-----------|
| `carregar_csv()` | Carrega CSV com múltiplos encodings |
| `preparar_dados()` | Limpa e valida dados de entrada |
| `gerar_historico_vendas()` | Cria histórico mensal por produto |
| `processar_loja()` | Calcula curva ABC e chama IA |
| `analisar_lote_ia_robusto()` | Chamada à API com retry |

### `analise_temporal.py`

| Função | Descrição |
|--------|-----------|
| `selecionar_top_bottom()` | Seleciona TOP N e BOTTOM N do mês |
| `processar_mes()` | Processa ranking mensal com variação |
| `construir_prompt_analise()` | Gera prompt otimizado para IA |
| `obter_contexto_sazonal()` | Retorna contexto brasileiro do mês |
| `analisar_mes_com_ia()` | Análise IA com exponential backoff |

---

## 📈 Melhorias Implementadas

- **Logging estruturado** substituindo print statements
- **Type hints** em todas as funções para manutenibilidade
- **Prompt de IA otimizado** com contexto sazonal brasileiro
- **Exponential backoff** para resiliência em chamadas API
- **Operações vetorizadas** do pandas para performance
- **Validação de dados** robusta com mensagens claras
- **Tratamento de erros** específicos por tipo de exceção
- **Modelo atualizado** para Gemini 2.5 Flash

---

## 🇧🇷 Contexto Sazonal Brasileiro

O sistema considera automaticamente:

| Mês | Estação | Eventos | Tendência |
|-----|---------|---------|-----------|
| Jan-Fev | Verão | Férias, Carnaval | Bebidas geladas, saladas |
| Mar-Mai | Outono | Páscoa, Dia das Mães | Transição cardápio |
| Jun-Ago | Inverno | Festa Junina, Dia dos Pais | Sopas, caldos, churrasco |
| Set-Nov | Primavera | Dia das Crianças, Black Friday | Combos, promoções |
| Dez | Verão | Natal, Ano Novo | Alto movimento, celebrações |

---

## 📄 Licença

Este projeto é de uso interno para análise de dados de restaurantes.

---

## 👥 Contribuidores

- Desenvolvido para otimização de cardápio e gestão de vendas em restaurantes

