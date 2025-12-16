# -*- coding: utf-8 -*-
"""
DOWNLOAD DE ARQUIVOS DO SHAREPOINT/ONEDRIVE
Baixa arquivos Excel grandes do SharePoint usando Microsoft Graph API.

Suporta dois métodos:
1. Link de compartilhamento público (sharing link)
2. Microsoft Graph API com autenticação (para arquivos privados)
"""

import os
import sys
import logging
import requests
import base64
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configurações
ARQUIVO_SAIDA = "dados_vendas.xlsx"
CHUNK_SIZE = 8192  # 8KB chunks para download


def extrair_share_id_de_url(url: str) -> str:
    """
    Extrai o share ID de uma URL de compartilhamento do SharePoint/OneDrive.
    
    Converte a URL de compartilhamento para base64url encoding que pode
    ser usado na Graph API.
    """
    # Codifica a URL em base64url (sem padding)
    encoded = base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')
    share_id = f"u!{encoded}"
    return share_id


def download_via_graph_api(url_compartilhamento: str, arquivo_saida: str) -> bool:
    """
    Baixa arquivo do SharePoint usando a Graph API (método para links públicos).
    
    Este método funciona para links de compartilhamento "Anyone with the link".
    Não requer autenticação para links públicos.
    """
    try:
        logger.info(f"🔗 Processando URL de compartilhamento...")
        
        # Converte URL para share ID
        share_id = extrair_share_id_de_url(url_compartilhamento)
        
        # Endpoint da Graph API para obter item compartilhado
        graph_url = f"https://graph.microsoft.com/v1.0/shares/{share_id}/driveItem"
        
        # Para links públicos, tenta sem autenticação primeiro
        headers = {"Accept": "application/json"}
        
        response = requests.get(graph_url, headers=headers, timeout=30)
        
        if response.status_code == 401:
            logger.warning("⚠️ Link requer autenticação. Tentando método alternativo...")
            return False
            
        if response.status_code != 200:
            logger.error(f"❌ Erro ao acessar Graph API: {response.status_code}")
            logger.error(f"Resposta: {response.text[:500]}")
            return False
        
        item_info = response.json()
        
        # Obtém URL de download
        download_url = item_info.get('@microsoft.graph.downloadUrl')
        if not download_url:
            logger.error("❌ URL de download não encontrada na resposta")
            return False
        
        # Baixa o arquivo
        logger.info(f"📥 Baixando arquivo...")
        return download_arquivo(download_url, arquivo_saida)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Erro de conexão: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Erro inesperado: {type(e).__name__}: {e}")
        return False


def download_via_link_direto(url: str, arquivo_saida: str) -> bool:
    """
    Tenta download direto convertendo URL do SharePoint para formato de download.
    
    Funciona para alguns links de compartilhamento do SharePoint/OneDrive.
    """
    try:
        # Converte URL de visualização para URL de download
        download_url = url.replace("action=default", "action=download")
        download_url = download_url.replace("action=view", "action=download")
        
        # Adiciona parâmetro de download se não existir
        if "download=1" not in download_url:
            separator = "&" if "?" in download_url else "?"
            download_url = f"{download_url}{separator}download=1"
        
        logger.info(f"📥 Tentando download direto...")
        return download_arquivo(download_url, arquivo_saida)
        
    except Exception as e:
        logger.error(f"❌ Erro no download direto: {e}")
        return False


def download_arquivo(url: str, arquivo_saida: str) -> bool:
    """
    Baixa arquivo de uma URL com suporte a arquivos grandes (streaming).
    """
    try:
        # Headers para simular navegador
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*"
        }
        
        response = requests.get(url, headers=headers, stream=True, timeout=300, allow_redirects=True)
        response.raise_for_status()
        
        # Obtém tamanho do arquivo
        total_size = int(response.headers.get('content-length', 0))
        
        if total_size > 0:
            logger.info(f"📊 Tamanho do arquivo: {total_size / (1024*1024):.2f} MB")
        
        # Baixa em chunks para não sobrecarregar memória
        downloaded = 0
        with open(arquivo_saida, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        if downloaded % (CHUNK_SIZE * 100) == 0:  # Log a cada ~800KB
                            logger.info(f"⏳ Progresso: {progress:.1f}%")
        
        # Verifica se arquivo foi criado
        if Path(arquivo_saida).exists():
            file_size = Path(arquivo_saida).stat().st_size
            logger.info(f"✅ Download concluído: {arquivo_saida} ({file_size / (1024*1024):.2f} MB)")
            return True
        else:
            logger.error("❌ Arquivo não foi criado")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Erro no download: {e}")
        return False


def download_com_graph_auth(url: str, arquivo_saida: str, client_id: str, client_secret: str, tenant_id: str) -> bool:
    """
    Baixa arquivo usando Microsoft Graph API com autenticação de aplicativo.

    Requer registro de aplicativo no Azure AD com permissões:
    - Files.Read.All (Application)
    - Sites.Read.All (Application)
    """
    try:
        # Obtém token de acesso
        logger.info("🔐 Obtendo token de autenticação...")

        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        token_data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default"
        }

        token_response = requests.post(token_url, data=token_data, timeout=30)
        token_response.raise_for_status()

        access_token = token_response.json().get("access_token")
        if not access_token:
            logger.error("❌ Falha ao obter token de acesso")
            return False

        logger.info("✅ Token obtido com sucesso")

        # Usa o token para acessar o arquivo
        share_id = extrair_share_id_de_url(url)
        graph_url = f"https://graph.microsoft.com/v1.0/shares/{share_id}/driveItem"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

        response = requests.get(graph_url, headers=headers, timeout=30)
        response.raise_for_status()

        item_info = response.json()
        download_url = item_info.get('@microsoft.graph.downloadUrl')

        if not download_url:
            logger.error("❌ URL de download não encontrada")
            return False

        return download_arquivo(download_url, arquivo_saida)

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Erro na autenticação Graph: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Erro inesperado: {type(e).__name__}: {e}")
        return False


def main():
    """
    Função principal: tenta múltiplos métodos de download.
    """
    logger.info("=" * 60)
    logger.info("DOWNLOAD DE ARQUIVO DO SHAREPOINT/ONEDRIVE")
    logger.info("=" * 60)

    # URL do arquivo (pode vir de variável de ambiente ou argumento)
    url = os.environ.get('SHAREPOINT_URL', '')

    if len(sys.argv) > 1:
        url = sys.argv[1]

    if not url:
        logger.error("❌ URL não fornecida!")
        logger.error("Uso: python download_sharepoint.py <URL_COMPARTILHAMENTO>")
        logger.error("Ou defina a variável de ambiente SHAREPOINT_URL")
        sys.exit(1)

    # Nome do arquivo de saída
    arquivo_saida = sys.argv[2] if len(sys.argv) > 2 else ARQUIVO_SAIDA

    logger.info(f"📁 Arquivo de saída: {arquivo_saida}")

    # Verifica se há credenciais para autenticação
    client_id = os.environ.get('AZURE_CLIENT_ID', '')
    client_secret = os.environ.get('AZURE_CLIENT_SECRET', '')
    tenant_id = os.environ.get('AZURE_TENANT_ID', '')

    sucesso = False

    # Método 1: Tenta download direto (links públicos)
    logger.info("\n📋 Método 1: Download via link direto...")
    sucesso = download_via_link_direto(url, arquivo_saida)

    if not sucesso:
        # Método 2: Tenta via Graph API sem auth (links "anyone")
        logger.info("\n📋 Método 2: Download via Graph API (sem auth)...")
        sucesso = download_via_graph_api(url, arquivo_saida)

    if not sucesso and client_id and client_secret and tenant_id:
        # Método 3: Graph API com autenticação
        logger.info("\n📋 Método 3: Download via Graph API (com auth)...")
        sucesso = download_com_graph_auth(url, arquivo_saida, client_id, client_secret, tenant_id)

    if sucesso:
        logger.info("\n" + "=" * 60)
        logger.info("✅ DOWNLOAD CONCLUÍDO COM SUCESSO!")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("\n" + "=" * 60)
        logger.error("❌ TODOS OS MÉTODOS DE DOWNLOAD FALHARAM")
        logger.error("=" * 60)
        logger.error("\nPossíveis soluções:")
        logger.error("1. Verifique se o link de compartilhamento está correto")
        logger.error("2. Configure as credenciais Azure (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)")
        logger.error("3. Verifique se o arquivo ainda existe no SharePoint")
        sys.exit(1)


if __name__ == "__main__":
    main()

