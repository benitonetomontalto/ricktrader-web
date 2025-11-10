"""
GT4 Binary Options Trading System - Main Application
FastAPI backend com IQ Option Real API Integration
"""
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.api.routes import router
from app.websocket.manager import manager
from app.core.config import settings
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Criar aplicação FastAPI
app = FastAPI(
    title="GT4 Binary Options Trading API",
    description="Sistema de Trading com IA e IQ Option Real API",
    version="2.0.0",
    docs_url="/api/docs",  # Mover docs para não interferir
    redoc_url="/api/redoc",  # Mover redoc
    openapi_url="/api/openapi.json"  # Mover OpenAPI
)

# Handler para erros 404 - redirecionar para frontend
@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        # Se for uma requisição de API, retornar JSON
        if request.url.path.startswith("/api"):
            return JSONResponse(
                status_code=404,
                content={"detail": "API endpoint not found", "path": request.url.path}
            )
        # Caso contrário, servir o index.html do frontend (SPA routing)
        import os
        import sys
        if getattr(sys, 'frozen', False):
            html_path = os.path.join(sys._MEIPASS, "frontend_dist", "index.html")
        else:
            html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend_dist", "index.html")

        if os.path.exists(html_path):
            from fastapi.responses import FileResponse
            return FileResponse(html_path)
        else:
            return JSONResponse(
                status_code=500,
                content={"error": "Frontend not found", "path": html_path}
            )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique os domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar rotas
app.include_router(router, prefix="/api/v1")

# Registrar rotas de admin
from app.api.admin_routes import router as admin_router
app.include_router(admin_router, prefix="/api/v1")

# Registrar rotas de diagnóstico
from app.api.diagnostic_routes import router as diagnostic_router
app.include_router(diagnostic_router, prefix="/api/v1")

# Servir arquivos estáticos (HTML admin e frontend)
import os
import sys

# Health check endpoint (para Electron verificar se backend está pronto)
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "port": 8000}

# Detectar se está rodando como executável PyInstaller
if getattr(sys, 'frozen', False):
    # PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
    base_path = sys._MEIPASS
    logger.info(f"[FROZEN] Rodando como executável, base_path: {base_path}")
else:
    base_path = os.path.dirname(os.path.dirname(__file__))
    logger.info(f"[DEV] Rodando em desenvolvimento, base_path: {base_path}")

static_path = os.path.join(base_path, "static")
frontend_path = os.path.join(base_path, "frontend_dist")

logger.info(f"Static path: {static_path} (existe: {os.path.exists(static_path)})")
logger.info(f"Frontend path: {frontend_path} (existe: {os.path.exists(frontend_path)})")

# WebSocket endpoint - DEVE SER REGISTRADO ANTES DO STATICFILES!
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para sinais em tempo real"""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)

# Montar arquivos estáticos do admin
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")
    logger.info("[OK] Montou /static")
else:
    logger.warning(f"[AVISO] Static path não encontrado: {static_path}")

# Montar frontend React (DEVE SER MONTADO POR ÚLTIMO!)
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
    logger.info("[OK] Montou / (frontend React)")
else:
    logger.error(f"[ERRO] Frontend path não encontrado: {frontend_path}")

# Health check
@app.get("/api/v1/health")
async def health_check():
    """Verificar status da API"""
    return JSONResponse({
        "status": "healthy",
        "version": "2.0.0",
        "service": "GT4 Trading API",
        "data_source": "IQ Option Real API"
    })

# Root endpoint explícito para servir o frontend
from fastapi.responses import FileResponse

# Redirecionar páginas antigas para o frontend de desenvolvimento
@app.get("/login")
async def redirect_login():
    """Redireciona /login para o frontend React"""
    logger.info("[REDIRECT] /login → http://localhost:3000")
    return RedirectResponse(url="http://localhost:3000", status_code=302)

@app.get("/dashboard")
async def redirect_dashboard():
    """Redireciona /dashboard para o frontend React"""
    logger.info("[REDIRECT] /dashboard → http://localhost:3000/dashboard")
    return RedirectResponse(url="http://localhost:3000/dashboard", status_code=302)

@app.get("/")
async def root():
    """Serve the frontend React app"""
    if getattr(sys, 'frozen', False):
        # Executável PyInstaller
        html_path = os.path.join(sys._MEIPASS, "frontend_dist", "index.html")
    else:
        # Desenvolvimento - Redirecionar para Vite dev server
        logger.info("[REDIRECT] / → http://localhost:3000")
        return RedirectResponse(url="http://localhost:3000", status_code=302)

    logger.info(f"[ROOT] Servindo index.html de: {html_path} (existe: {os.path.exists(html_path)})")

    if not os.path.exists(html_path):
        return JSONResponse({
            "error": "Frontend not found",
            "path": html_path,
            "message": "Execute o build do frontend primeiro!"
        }, status_code=500)

    return FileResponse(html_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
