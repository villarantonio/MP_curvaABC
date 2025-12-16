# 🚀 Guia de Automação - MP_curvaABC

Este documento descreve a arquitetura e configuração da automação para análise de vendas com IA.

---

## 📋 Índice

1. [Visão Geral da Arquitetura](#-visão-geral-da-arquitetura)
2. [Configuração do GitHub](#-configuração-do-github)
3. [Configuração Alternativa (n8n)](#-configuração-alternativa-n8n)
4. [Testes e Validação](#-testes-e-validação)
5. [Troubleshooting](#-troubleshooting)

---

## 🏗️ Visão Geral da Arquitetura

### ⚡ Nova Arquitetura (GitHub Actions Completo)

> **IMPORTANTE:** Esta é a arquitetura recomendada. Substitui o n8n para evitar problemas de memória com arquivos grandes (500k+ linhas).

```
┌─────────────┐     ┌─────────────────────────────────────────┐     ┌─────────────┐
│ SharePoint  │────▶│           GitHub Actions                │────▶│  Dashboard  │
│  (Excel)    │     │  ┌─────────┐  ┌─────────┐  ┌─────────┐  │     │  (GitHub    │
│             │     │  │Download │─▶│ Análise │─▶│ Commit  │  │     │   Pages)    │
│             │     │  │SharePt  │  │  + IA   │  │  JSONs  │  │     │             │
└─────────────┘     │  └─────────┘  └─────────┘  └─────────┘  │     └─────────────┘
                    └─────────────────────────────────────────┘
```

### Fluxo Automático

1. **Agendamento**: GitHub Actions executa diariamente às 6h (Brasília)
2. **Download**: Script Python baixa o Excel do SharePoint (sem limite de memória)
3. **Análise**: Scripts processam dados e geram insights com Gemini AI
4. **Deploy**: JSONs são commitados automaticamente para o dashboard

### Componentes

| Componente | Função | Tecnologia |
|------------|--------|------------|
| **SharePoint** | Armazenamento do Excel de vendas | Microsoft 365 |
| **GitHub Actions** | Download + Análise + Deploy (tudo em um) | Ubuntu runner |
| **Gemini AI** | Geração de insights de vendas | Google AI |
| **GitHub Pages** | Hospedagem do Dashboard | GitHub.com |

### Scripts Executados

| Script | Função | Saída |
|--------|--------|-------|
| `download_sharepoint.py` | Baixa Excel do SharePoint | `dados_vendas.xlsx` |
| `relatorio_teste.py` | Curva ABC com insights IA | `analise_abc_final.json` |
| `analise_temporal_multi.py` | Análise diária/semanal/mensal | `docs/data/vendas_*.json` |

---

## ⚙️ Configuração do GitHub

### 1. Adicionar Secrets Necessários

Acesse: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret | Descrição | Obrigatório |
|--------|-----------|-------------|
| `GEMINI_API_KEY` | Chave da API Google Gemini | ✅ Sim |
| `AZURE_CLIENT_ID` | ID do aplicativo Azure (para SharePoint privado) | ❌ Opcional |
| `AZURE_CLIENT_SECRET` | Secret do aplicativo Azure | ❌ Opcional |
| `AZURE_TENANT_ID` | ID do tenant Azure | ❌ Opcional |

> **Nota:** As credenciais Azure só são necessárias se o link do SharePoint for privado.
> Para links "Qualquer pessoa com o link", não é necessário.

### 2. Verificar Permissões do Workflow

1. Vá em **Settings** → **Actions** → **General**
2. Em **Workflow permissions**, selecione:
   - ✅ **Read and write permissions**
   - ✅ **Allow GitHub Actions to create and approve pull requests**
3. Clique em **Save**

### 3. Executar a Automação

#### Execução Automática (Recomendado)
O workflow `Automação Completa` executa automaticamente todo dia às **6h (Brasília)**.

#### Execução Manual
1. Vá na aba **Actions**
2. Selecione **"Automação Completa - Download SharePoint + Análise + Dashboard"**
3. Clique em **Run workflow**
4. (Opcional) Insira uma URL diferente do SharePoint
5. Clique em **Run workflow**

### 4. Visualizar Logs de Execução

1. Vá na aba **Actions**
2. Clique no workflow em execução ou concluído
3. Clique no job `download-e-analise`
4. Expanda cada step para ver os logs detalhados

---

## 🔄 Configuração Alternativa (n8n)

> ⚠️ **ATENÇÃO:** O n8n tem limitações de memória e **NÃO é recomendado** para arquivos grandes (500k+ linhas).
> Use apenas para arquivos pequenos ou se preferir uma interface visual.

### Quando usar n8n vs GitHub Actions

| Cenário | Recomendação |
|---------|--------------|
| Arquivo Excel > 100MB | ✅ GitHub Actions |
| Mais de 100k linhas | ✅ GitHub Actions |
| Arquivo pequeno (< 50k linhas) | ✅ n8n ou GitHub Actions |
| Precisa de interface visual | ✅ n8n |
| Automação sem manutenção | ✅ GitHub Actions |

### Se ainda quiser usar n8n

O n8n pode ser usado para **disparar** o workflow do GitHub Actions em vez de fazer o download diretamente:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Trigger    │────▶│   HTTP       │────▶│   GitHub     │
│  (Schedule)  │     │  Request     │     │   Actions    │
│              │     │  (Webhook)   │     │  (Executa)   │
└──────────────┘     └──────────────┘     └──────────────┘
```

#### Configuração do Webhook no GitHub

1. Crie um **Personal Access Token** com permissão `repo`
2. No n8n, use o node **HTTP Request** com:
   - **Method:** POST
   - **URL:** `https://api.github.com/repos/Yago-Coqueiro/MP_curvaABC/actions/workflows/automacao_completa.yml/dispatches`
   - **Headers:**
     - `Authorization: Bearer <SEU_TOKEN>`
     - `Accept: application/vnd.github.v3+json`
   - **Body:**
     ```json
     {"ref": "main"}
     ```

Isso dispara o workflow completo no GitHub, que faz todo o trabalho pesado.

---

## 🧪 Testes e Validação

### Teste Local dos Scripts

#### 1. Testar download do SharePoint
```bash
# Defina a URL do SharePoint
$env:SHAREPOINT_URL = "https://mandapicanha-my.sharepoint.com/..."

# Execute o download
python scripts/download_sharepoint.py
```

#### 2. Testar análises com arquivo local
```bash
# Análise ABC
python scripts/relatorio_teste.py dados_vendas.xlsx

# Análise temporal (todas as granularidades)
python scripts/analise_temporal_multi.py dados_vendas.xlsx --all
```

#### 3. Verificar se os JSONs foram gerados
```bash
# Windows PowerShell
Get-ChildItem *.json
Get-ChildItem docs/data/*.json

# Linux/Mac
ls -la *.json docs/data/*.json
```

### Teste do Workflow GitHub Actions

#### Opção 1: Disparar workflow manualmente (RECOMENDADO)
1. Vá na aba **Actions** do repositório
2. Selecione **"Automação Completa - Download SharePoint + Análise + Dashboard"**
3. Clique em **Run workflow**
4. (Opcional) Insira uma URL diferente do SharePoint
5. Clique em **Run workflow**

#### Opção 2: Usar workflow legado (arquivo local)
Se já tiver o arquivo no repositório:
1. Selecione **"Processamento de Vendas"**
2. Clique em **Run workflow**

### Validação dos JSONs Gerados

```python
# Script de validação rápida
import json
from pathlib import Path

# Arquivos esperados
arquivos = [
    'analise_abc_final.json',
    'docs/data/vendas_diario.json',
    'docs/data/vendas_semanal.json',
    'docs/data/vendas_mensal.json'
]

for arquivo in arquivos:
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        size = Path(arquivo).stat().st_size / 1024
        print(f"✅ {arquivo}: válido ({size:.1f} KB)")
    except FileNotFoundError:
        print(f"❌ {arquivo}: não encontrado")
    except json.JSONDecodeError as e:
        print(f"❌ {arquivo}: JSON inválido - {e}")
```

---

## 🔧 Troubleshooting

### Erros Comuns e Soluções

#### 1. Rate Limit da API Gemini (429)
```
❌ Rate limit atingido!
```

**Causa:** Muitas requisições em pouco tempo (limite: ~2 req/min no plano gratuito)

**Soluções:**
- O script já tem retry automático com delays progressivos
- Se persistir, aumente `DELAY_ENTRE_CHAMADAS` nos scripts
- Considere usar os scripts individuais por loja (`analise_loja_*.py`)

#### 2. Falha no download do SharePoint
```
❌ TODOS OS MÉTODOS DE DOWNLOAD FALHARAM
```

**Possíveis causas e soluções:**
- **Link expirado:** Gere um novo link de compartilhamento no SharePoint
- **Link privado:** Configure as credenciais Azure (AZURE_CLIENT_ID, etc.)
- **Arquivo movido:** Verifique se o arquivo ainda existe no SharePoint
- **Timeout:** O arquivo é muito grande, tente novamente

#### 3. Secret GEMINI_API_KEY não configurada
```
API Key não configurada. Análise IA será pulada.
```

**Soluções:**
- Verifique se a secret foi adicionada corretamente
- O nome deve ser exatamente `GEMINI_API_KEY`
- Gere uma nova chave em: https://aistudio.google.com/app/apikey

#### 4. Workflow não dispara automaticamente
**Possíveis causas:**
- O workflow está desabilitado
- O schedule está configurado incorretamente

**Soluções:**
- Vá em Actions → Enable workflow
- Verifique se o cron está correto (0 9 * * * = 6h Brasília)
- Execute manualmente para testar

#### 5. Permissão negada para push
```
Permission denied to github-actions[bot]
```

**Soluções:**
- Vá em Settings → Actions → General
- Habilite "Read and write permissions"
- Marque "Allow GitHub Actions to create and approve pull requests"

### Como Verificar Logs do GitHub Actions

1. **Acesse a aba Actions** do repositório
2. **Clique na execução** que deseja investigar
3. **Expanda o job** `download-e-analise`
4. **Clique em cada step** para ver logs detalhados:
   - 📥 Download do SharePoint
   - 📈 Análise ABC
   - 📅 Análise Temporal
   - 📤 Commit dos JSONs
5. **Procure por ícones:**
   - ✅ Verde: Step concluído com sucesso
   - ❌ Vermelho: Step falhou
   - ⚠️ Amarelo: Step com warnings

### Comandos Úteis para Debug Local

```bash
# Verificar versão do Python
python --version

# Verificar dependências instaladas
pip list

# Testar import das bibliotecas
python -c "import pandas; import google.generativeai; import requests; print('OK')"

# Verificar variáveis de ambiente
python -c "import os; print('GEMINI_API_KEY:', 'SET' if os.environ.get('GEMINI_API_KEY') else 'NOT SET')"
```

---

## 📞 Suporte

- **Repositório:** https://github.com/Yago-Coqueiro/MP_curvaABC
- **Dashboard:** https://yago-coqueiro.github.io/MP_curvaABC/
- **Documentação Google Gemini:** https://ai.google.dev/docs
- **Microsoft Graph API:** https://learn.microsoft.com/graph/

---

*Última atualização: Dezembro 2025*

