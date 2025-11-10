"""
Rick Trader - Standalone Executable Entry Point
Inicia o servidor backend e abre o navegador automaticamente
"""
import os
import sys
import webbrowser
import time
import threading
import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def open_browser():
    """Abre o navegador após 2 segundos - APENAS se não estiver no Electron"""
    # Verificar se está sendo executado pelo Electron
    if os.environ.get('ELECTRON_RUN_AS_NODE') or os.environ.get('ELECTRON_NO_BROWSER'):
        logger.info("🔧 Detectado Electron - NÃO abrindo navegador")
        return

    time.sleep(2)
    logger.info("Abrindo Rick Trader no navegador...")
    webbrowser.open('http://127.0.0.1:8000')

def main():
    """Função principal"""
    logger.info("=" * 60)
    logger.info("🚀 RICK TRADER - AI TRADING SYSTEM")
    logger.info("=" * 60)
    logger.info("Iniciando servidor...")

    # Configurar paths
    if getattr(sys, 'frozen', False):
        # Executável PyInstaller
        application_path = os.path.dirname(sys.executable)
        static_path = get_resource_path('static')
        frontend_path = get_resource_path('frontend_dist')
        data_path = os.path.join(application_path, 'data')
    else:
        # Desenvolvimento
        application_path = os.path.dirname(os.path.abspath(__file__))
        static_path = os.path.join(application_path, 'static')
        frontend_path = os.path.join(application_path, 'frontend_dist')
        data_path = os.path.join(application_path, 'data')

    # Criar diretório data se não existir
    os.makedirs(data_path, exist_ok=True)

    # Verificar se arquivos necessários existem
    access_tokens_file = os.path.join(data_path, 'access_tokens.json')
    if not os.path.exists(access_tokens_file):
        import json
        with open(access_tokens_file, 'w') as f:
            json.dump([], f)
        logger.info(f"Criado arquivo de tokens: {access_tokens_file}")

    logger.info(f"Diretório da aplicação: {application_path}")
    logger.info(f"Diretório de dados: {data_path}")
    logger.info(f"Diretório static: {static_path}")
    logger.info(f"Diretório frontend: {frontend_path}")

    # Iniciar navegador em thread separada
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # Iniciar servidor FastAPI
    import uvicorn
    from app.main import app

    logger.info("")
    logger.info("✅ Rick Trader iniciado com sucesso!")
    logger.info("📊 Acesse: http://127.0.0.1:8000")
    logger.info("🔧 Painel Admin: http://127.0.0.1:8000/static/admin.html")
    logger.info("")
    logger.info("Pressione CTRL+C para encerrar")
    logger.info("=" * 60)

    # Configurar host e porta para produção
    # Render.com fornece a porta via variável de ambiente PORT
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"  # Permitir conexões externas em produção

    # Em ambiente local, usar 127.0.0.1
    if os.environ.get("RENDER") is None:
        host = "127.0.0.1"

    logger.info(f"🌐 Host: {host}")
    logger.info(f"🔌 Port: {port}")

    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=False
        )
    except KeyboardInterrupt:
        logger.info("\n👋 Rick Trader encerrado. Até logo!")
        sys.exit(0)

if __name__ == "__main__":
    main()
