# Rick Trader - AI Trading System

Sistema profissional de trading com inteligência artificial para IQ Option.

## Recursos

- Interface web moderna e responsiva
- Conexão direta com IQ Option
- Sistema de autenticação por token
- Dashboard em tempo real
- Análise de mercado com IA
- Gerenciamento de operações

## Deploy

Este projeto está pronto para deploy no **Render.com** (gratuito).

### Guia Rápido de Deploy

1. Faça fork deste repositório
2. Crie uma conta no [Render.com](https://render.com)
3. Crie um novo Web Service
4. Conecte este repositório
5. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python run_ricktrader.py`
   - **Instance Type:** Free

Aguarde 2-5 minutos e sua aplicação estará online!

### Documentação Completa

- [DEPLOY_RAPIDO.txt](DEPLOY_RAPIDO.txt) - Guia rápido de 5 minutos
- [README_DEPLOY.md](README_DEPLOY.md) - Documentação completa de deploy

## Tecnologias

- **Backend:** Python, FastAPI, Uvicorn
- **Frontend:** React, TypeScript, Tailwind CSS
- **Trading:** IQ Option API
- **Deploy:** Render.com (gratuito)

## Desenvolvimento Local

```bash
# Instalar dependências
pip install -r requirements.txt

# Iniciar servidor
python run_ricktrader.py

# Acessar
http://127.0.0.1:8000
```

## Requisitos

- Python 3.11+
- Conta IQ Option
- Token de acesso válido

## Estrutura do Projeto

```
ricktrader-web/
├── app/                  # Backend API
├── static/              # Arquivos estáticos
├── frontend_dist/       # Frontend compilado
├── data/                # Banco de dados
├── run_ricktrader.py    # Servidor principal
├── requirements.txt     # Dependências
└── render.yaml         # Configuração Render
```

## Sistema de Tokens

O Rick Trader usa sistema de autenticação baseado em tokens de acesso.

Para gerar tokens:
- Acesse: `/static/admin.html`
- Use o gerador de licenças incluído

## Suporte

Para problemas ou dúvidas, consulte:
- [Documentação de Deploy](README_DEPLOY.md)
- [Render Docs](https://render.com/docs)

## Licença

Rick Trader © 2025 - Sistema de Trading Profissional com IA

---

**Deploy online em 5 minutos!** 🚀
