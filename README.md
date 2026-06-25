# EstoqueVestir — Controle de Estoque para Loja de Roupas

Sistema web desenvolvido em Flask + SQLite com interface dark elegante.

## Funcionalidades

- Login com controle de acesso (Admin / Vendedor)
- Dashboard com KPIs e alertas de estoque baixo
- CRUD completo de produtos (SKU, tamanho, cor, preços, quantidade)
- Movimentações de estoque (entrada, saída, ajuste)
- Histórico por produto
- Categorias personalizáveis
- Gestão de usuários (somente admin)
- Relatório geral com valores e margens
- Impressão do relatório

## Deploy no AWS Lightsail

### 1. Transfira os arquivos
```bash
# Na sua máquina local:
scp -i chave.pem -r estoque-roupas/ ubuntu@IP_LIGHTSAIL:~/
```

### 2. Execute o deploy
```bash
# No servidor:
cd ~/estoque-roupas
chmod +x deploy.sh
bash deploy.sh
```

### 3. Acesso
- URL: `http://IP_DO_SERVIDOR`
- Login padrão: `admin@loja.com` / `admin123`
- **Troque a senha imediatamente após o primeiro acesso!**

### 4. Domínio próprio (opcional)
Edite `/etc/nginx/sites-available/estoque-roupas` e troque `server_name _;` por `server_name oee.toitisistemas.com.br;`, depois:
```bash
sudo certbot --nginx -d seudominio.com.br  # SSL grátis
sudo systemctl reload nginx
```

## Desenvolvimento local

```bash
pip install -r requirements.txt
python app.py
# Acesse: http://localhost:5000
```

## Perfis de Acesso

| Funcionalidade     | Vendedor | Admin |
|--------------------|----------|-------|
| Ver dashboard      | ✅        | ✅     |
| Produtos           | ✅ (editar)| ✅ (excluir) |
| Movimentações      | ✅        | ✅     |
| Relatório          | ✅        | ✅     |
| Categorias         | —        | ✅     |
| Usuários           | —        | ✅     |

---
Toiti Sistemas · toitisistemas.com.br
