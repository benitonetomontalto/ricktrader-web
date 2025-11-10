# RICK TRADER - GUIA DE DEPLOY ONLINE

## Como Colocar Online GRATUITAMENTE

Este guia vai te ensinar a colocar o Rick Trader online usando **Render.com** (100% grátis).

---

## PASSO 1: Criar Conta no GitHub

1. Acesse: https://github.com
2. Clique em "Sign up" (Cadastrar)
3. Crie sua conta gratuitamente

---

## PASSO 2: Criar Repositório no GitHub

1. No GitHub, clique no botão verde "New" (Novo)
2. Nome do repositório: **ricktrader-web**
3. Deixe como **Public** (Público)
4. Marque "Add a README file"
5. Clique em "Create repository"

---

## PASSO 3: Subir o Código para o GitHub

### Opção A: Usando GitHub Desktop (MAIS FÁCIL)

1. Baixe o GitHub Desktop: https://desktop.github.com
2. Instale e faça login com sua conta GitHub
3. Clique em "Add" > "Add Existing Repository"
4. Escolha esta pasta: `C:\Users\benit\Desktop\RickTrader_DEPLOY`
5. Clique em "Publish repository"
6. Pronto! Código enviado.

### Opção B: Usando Git Command Line

```bash
cd C:\Users\benit\Desktop\RickTrader_DEPLOY

# Inicializar repositório
git init

# Adicionar todos os arquivos
git add .

# Fazer primeiro commit
git commit -m "Deploy Rick Trader"

# Conectar com GitHub
git remote add origin https://github.com/SEU_USUARIO/ricktrader-web.git

# Enviar para GitHub
git push -u origin main
```

> **IMPORTANTE:** Substitua `SEU_USUARIO` pelo seu nome de usuário do GitHub!

---

## PASSO 4: Criar Conta no Render.com

1. Acesse: https://render.com
2. Clique em "Get Started for Free"
3. Faça login com sua conta do GitHub (mais fácil)
4. Autorize o Render a acessar seus repositórios

---

## PASSO 5: Criar Web Service no Render

1. No dashboard do Render, clique em "New +"
2. Escolha "Web Service"
3. Conecte seu repositório: **ricktrader-web**
4. Clique em "Connect"

### Configurações do Deploy:

```
Name: ricktrader-web
Region: Oregon (US West)
Branch: main
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: python run_ricktrader.py
```

### Instance Type:

- Escolha: **Free** (Gratuito)

5. Clique em "Create Web Service"

---

## PASSO 6: Aguardar Deploy

O Render vai:
1. Baixar seu código
2. Instalar as dependências (requirements.txt)
3. Iniciar o servidor

**Tempo estimado:** 2-5 minutos

Você verá os logs em tempo real. Quando aparecer:

```
✅ Rick Trader iniciado com sucesso!
📊 Acesse: http://0.0.0.0:8000
```

Significa que funcionou!

---

## PASSO 7: Acessar sua Aplicação Online

Após o deploy, o Render vai te dar uma URL tipo:

```
https://ricktrader-web-xxxx.onrender.com
```

**PRONTO!** Sua aplicação está online! 🎉

---

## CONFIGURAÇÕES IMPORTANTES

### Variáveis de Ambiente (Opcional)

Se precisar configurar variáveis de ambiente:

1. No dashboard do Render, vá em seu serviço
2. Clique em "Environment"
3. Adicione as variáveis:

```
PORT=8000
PYTHON_VERSION=3.11.9
```

---

## LIMITAÇÕES DO PLANO GRÁTIS

O Render.com Free tem:
- ✅ 750 horas/mês (mais que suficiente)
- ✅ Deploy automático quando você atualiza o código
- ✅ HTTPS grátis
- ⚠️ O servidor "dorme" após 15 min sem uso
- ⚠️ Primeiro acesso após dormir demora ~30 segundos

---

## COMO ATUALIZAR O CÓDIGO

Sempre que você fizer alterações:

```bash
# Adicionar mudanças
git add .

# Fazer commit
git commit -m "Atualização XYZ"

# Enviar para GitHub
git push
```

O Render vai detectar automaticamente e fazer novo deploy!

---

## DOMÍNIO PRÓPRIO (Opcional)

Se quiser usar seu próprio domínio (ex: ricktrader.com.br):

1. No Render, vá em seu serviço
2. Clique em "Settings" > "Custom Domain"
3. Adicione seu domínio
4. Configure o DNS do seu domínio apontando para o Render

---

## MONITORAMENTO

### Ver Logs em Tempo Real:

1. No dashboard do Render
2. Clique em seu serviço
3. Vá em "Logs"

### Reiniciar o Servidor:

1. No dashboard do Render
2. Clique em "Manual Deploy"
3. Clique em "Clear build cache & deploy"

---

## ALTERNATIVAS GRATUITAS

Se quiser testar outras plataformas:

### 1. Railway.app
- 500 horas grátis/mês
- Deploy mais rápido
- Interface mais simples

### 2. Fly.io
- 160 GB grátis/mês
- Servidores em vários países
- Bom para performance

### 3. Vercel (apenas frontend)
- Ilimitado grátis
- Ideal se você separar frontend/backend
- Super rápido

---

## TROUBLESHOOTING

### Erro: "Build Failed"

**Solução:**
1. Verifique se `requirements.txt` está correto
2. Veja os logs do build
3. Pode ser falta de memória (use versões mais leves das bibliotecas)

### Erro: "Application timeout"

**Solução:**
1. Verifique se o servidor está iniciando na porta correta
2. O Render usa a variável `PORT` automática
3. Ajuste `run_ricktrader.py` se necessário

### Aplicação demora muito para carregar

**Solução:**
- Isso é normal no plano grátis após 15 min sem uso
- Para evitar, use um "ping service" como:
  - https://uptimerobot.com (grátis)
  - Faz uma requisição a cada 5 minutos mantendo servidor ativo

---

## SUPORTE

Se tiver problemas:

1. Veja os logs no Render
2. Verifique se todos os arquivos estão no GitHub
3. Teste localmente antes: `python run_ricktrader.py`

---

## CHECKLIST FINAL

Antes de fazer deploy, certifique-se:

- [ ] Código funciona localmente
- [ ] `requirements.txt` tem todas as dependências
- [ ] `.gitignore` não está bloqueando arquivos importantes
- [ ] `render.yaml` está configurado corretamente
- [ ] Repositório GitHub está atualizado
- [ ] Conta no Render.com criada
- [ ] Web Service criado no Render

---

## ESTRUTURA DOS ARQUIVOS

```
RickTrader_DEPLOY/
├── run_ricktrader.py       # Arquivo principal
├── requirements.txt        # Dependências Python
├── render.yaml            # Configuração Render
├── .gitignore            # Arquivos a ignorar
├── README_DEPLOY.md      # Este arquivo
├── static/               # Frontend compilado
│   ├── index.html
│   ├── assets/
│   └── ...
└── database.db           # Será criado automaticamente
```

---

## PRÓXIMOS PASSOS

Depois que estiver online:

1. **Teste tudo:** Login, dashboard, conexão IQ Option
2. **Compartilhe a URL** com seus usuários
3. **Configure domínio próprio** (opcional)
4. **Setup monitoramento** com UptimeRobot
5. **Backup do banco de dados** regularmente

---

## CUSTOS

### 100% Grátis:
- Render.com Free Plan
- GitHub (repositório público)
- HTTPS incluído

### Opcional (se quiser upgrades):
- Render Starter Plan: $7/mês (sem dormir, mais recursos)
- Domínio próprio: ~R$ 40/ano
- Nada disso é necessário para funcionar!

---

## CONCLUSÃO

Seguindo este guia, você terá o Rick Trader rodando online **gratuitamente** em menos de 15 minutos!

A URL gerada pode ser compartilhada com qualquer pessoa no mundo.

**Boa sorte!** 🚀

---

## CONTATO/SUPORTE

- **Render Docs:** https://render.com/docs
- **GitHub Docs:** https://docs.github.com
- **Render Community:** https://community.render.com

---

**Rick Trader © 2025**
Sistema de Trading Profissional com IA
