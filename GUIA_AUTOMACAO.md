# 🚀 Guia de Automação - MP_curvaABC

Este documento descreve a arquitetura e configuração da automação para análise de vendas com IA.

---

## 📋 Índice

1. [Visão Geral da Arquitetura](#-visão-geral-da-arquitetura)
2. [Configuração do GitHub](#-configuração-do-github)
3. [Configuração do n8n](#-configuração-do-n8n)
4. [Testes e Validação](#-testes-e-validação)
5. [Troubleshooting](#-troubleshooting)

---

## 🏗️ Visão Geral da Arquitetura

### Fluxo Completo de Automação

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   OneDrive  │────▶│     n8n     │────▶│   GitHub    │────▶│   Actions   │
│  (CSV novo) │     │  (Download  │     │  (Commit    │     │  (Executa   │
│             │     │   + Commit) │     │   trigger)  │     │   scripts)  │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                    ┌─────────────┐     ┌─────────────┐            │
                    │  Dashboard  │◀────│   GitHub    │◀───────────┘
                    │  (Consome   │     │  (JSONs     │   (Commit JSONs)
                    │   JSONs)    │     │   gerados)  │
                    └─────────────┘     └─────────────┘
```

### Componentes

| Componente | Função | Tecnologia |
|------------|--------|------------|
| **OneDrive** | Armazenamento do CSV de vendas | Microsoft 365 |
| **n8n** | Orquestração: download + commit | Self-hosted / Cloud |
| **GitHub** | Repositório + Trigger de CI/CD | GitHub.com |
| **GitHub Actions** | Execução dos scripts Python | Ubuntu runner |
| **Gemini AI** | Geração de insights de vendas | Google AI |

### Scripts Executados

| Script | Função | Saída |
|--------|--------|-------|
| `relatorio_teste.py` | Curva ABC com insights IA | `analise_abc_final.json` |
| `analise_temporal.py` | Análise mensal todas as lojas | `analise_mensal_sazonal.json` |

---

## ⚙️ Configuração do GitHub

### 1. Adicionar Secret da API Gemini

1. Acesse o repositório: https://github.com/Yago-Coqueiro/MP_curvaABC
2. Vá em **Settings** → **Secrets and variables** → **Actions**
3. Clique em **New repository secret**
4. Configure:
   - **Name:** `GEMINI_API_KEY`
   - **Secret:** Sua chave da API Google Gemini
5. Clique em **Add secret**

### 2. Verificar Permissões do Workflow

1. Vá em **Settings** → **Actions** → **General**
2. Em **Workflow permissions**, selecione:
   - ✅ **Read and write permissions**
   - ✅ **Allow GitHub Actions to create and approve pull requests**
3. Clique em **Save**

### 3. Verificar se o Workflow está Habilitado

1. Vá na aba **Actions** do repositório
2. Se aparecer um banner pedindo para habilitar, clique em **Enable**
3. O workflow `Processamento de Vendas` deve aparecer na lista

### 4. Visualizar Logs de Execução

1. Vá na aba **Actions**
2. Clique no workflow em execução ou concluído
3. Clique no job `analise-vendas`
4. Expanda cada step para ver os logs detalhados

---

## 🔄 Configuração do n8n

### Visão Geral do Workflow n8n

O n8n será responsável por:
1. Monitorar/receber trigger quando novo CSV estiver disponível
2. Baixar o arquivo do OneDrive
3. Fazer commit no GitHub como `dados_entrada.csv`

### Nodes Necessários

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Trigger    │────▶│   OneDrive   │────▶│   GitHub     │────▶│   Resposta   │
│  (Schedule   │     │  (Download   │     │  (Commit     │     │  (Opcional)  │
│   ou Webhook)│     │   File)      │     │   File)      │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### Passo a Passo Conceitual

#### Node 1: Trigger (Schedule ou Webhook)
```json
{
  "type": "Schedule Trigger",
  "config": {
    "cronExpression": "0 6 * * *",
    "comment": "Executa todo dia às 6h"
  }
}
```

#### Node 2: OneDrive - Download File
```json
{
  "type": "Microsoft OneDrive",
  "operation": "Download File",
  "config": {
    "authentication": "OAuth2",
    "fileId": "ID_DO_ARQUIVO_OU_CAMINHO",
    "comment": "Baixa o CSV mais recente"
  }
}
```

#### Node 3: GitHub - Create/Update File
```json
{
  "type": "GitHub",
  "operation": "Create or Update File",
  "config": {
    "owner": "Yago-Coqueiro",
    "repository": "MP_curvaABC",
    "filePath": "dados_entrada.csv",
    "branch": "feature/analise-por-loja",
    "commitMessage": "chore: atualização automática do CSV de vendas",
    "fileContent": "{{ $binary.data }}",
    "authentication": "Personal Access Token"
  }
}
```

### Criando Personal Access Token (PAT) no GitHub

1. Acesse: https://github.com/settings/tokens
2. Clique em **Generate new token (classic)**
3. Configure:
   - **Note:** `n8n-automation`
   - **Expiration:** Escolha conforme necessidade
   - **Scopes:** Marque `repo` (acesso completo ao repositório)
4. Clique em **Generate token**
5. **IMPORTANTE:** Copie o token imediatamente (não será mostrado novamente)
6. Use este token nas credenciais do GitHub no n8n

---

## 🧪 Testes e Validação

### Teste Local dos Scripts

#### 1. Testar com arquivo padrão (sem argumentos)
```bash
# Deve usar o arquivo padrão "GMRMPMA (2)(Export).csv"
python relatorio_teste.py
python analise_temporal.py
```

#### 2. Testar com arquivo específico (com argumento)
```bash
# Passa o caminho do arquivo como argumento
python relatorio_teste.py dados_entrada.csv
python analise_temporal.py dados_entrada.csv
```

#### 3. Verificar se os JSONs foram gerados
```bash
# Windows PowerShell
Get-ChildItem *.json

# Linux/Mac
ls -la *.json
```

### Teste Manual do Workflow GitHub Actions

#### Opção 1: Commit manual do arquivo CSV
```bash
# Renomeie seu CSV para dados_entrada.csv
copy "GMRMPMA (2)(Export).csv" dados_entrada.csv

# Commit e push
git add dados_entrada.csv
git commit -m "test: trigger workflow com novo CSV"
git push
```

#### Opção 2: Disparar workflow manualmente
1. Vá na aba **Actions** do repositório
2. Selecione o workflow **Processamento de Vendas**
3. Clique em **Run workflow**
4. (Opcional) Especifique o nome do arquivo CSV
5. Clique em **Run workflow**

### Validação dos JSONs Gerados

```python
# Script de validação rápida
import json

arquivos = ['analise_abc_final.json', 'analise_mensal_sazonal.json']

for arquivo in arquivos:
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        print(f"✅ {arquivo}: válido ({len(str(dados))} caracteres)")
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

#### 2. Arquivo CSV não encontrado
```
❌ Arquivo dados_entrada.csv não encontrado!
```

**Soluções:**
- Verifique se o n8n fez o commit corretamente
- Confirme que o nome do arquivo é exatamente `dados_entrada.csv`
- Verifique a branch correta

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
- O arquivo commitado não é `dados_entrada.csv`
- O commit foi feito em outra branch
- O workflow está desabilitado

**Soluções:**
- Verifique o nome exato do arquivo no commit
- Confirme a branch no trigger do workflow
- Habilite o workflow em Actions → Enable

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
3. **Expanda o job** `analise-vendas`
4. **Clique em cada step** para ver logs detalhados
5. **Procure por ícones:**
   - ✅ Verde: Step concluído com sucesso
   - ❌ Vermelho: Step falhou
   - ⚠️ Amarelo: Step com warnings

### Comandos Úteis para Debug

```bash
# Verificar versão do Python
python --version

# Verificar dependências instaladas
pip list

# Testar import das bibliotecas
python -c "import pandas; import google.generativeai; print('OK')"

# Verificar variável de ambiente
python -c "import os; print('API Key:', 'SET' if os.environ.get('GEMINI_API_KEY') else 'NOT SET')"
```

---

## 📞 Suporte

- **Repositório:** https://github.com/Yago-Coqueiro/MP_curvaABC
- **Branch de automação:** `feature/analise-por-loja`
- **Documentação Google Gemini:** https://ai.google.dev/docs

---

*Última atualização: Dezembro 2025*

