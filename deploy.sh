#!/bin/bash
# deploy.sh — Lightsail Ubuntu 22/24
# Execute: bash deploy.sh

set -e

APP_DIR="/var/www/estoque-roupas"
SERVICE="estoque-roupas"
PORT=5000

echo "==> Atualizando pacotes..."
sudo apt update -y
sudo apt install -y python3-pip python3-venv nginx git

echo "==> Copiando arquivos..."
sudo mkdir -p $APP_DIR
sudo cp -r . $APP_DIR/
sudo chown -R ubuntu:ubuntu $APP_DIR

echo "==> Criando ambiente virtual..."
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

echo "==> Gerando secret key..."
SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

echo "==> Criando serviço systemd..."
sudo tee /etc/systemd/system/${SERVICE}.service > /dev/null <<EOF
[Unit]
Description=EstoqueVestir Flask App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=${APP_DIR}
Environment="SECRET_KEY=${SECRET}"
ExecStart=${APP_DIR}/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:${PORT} app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE
sudo systemctl restart $SERVICE

echo "==> Configurando Nginx..."
sudo tee /etc/nginx/sites-available/$SERVICE > /dev/null <<EOF
server {
    listen 80;
    server_name _;  # Troque pelo seu domínio

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    location /static/ {
        alias ${APP_DIR}/static/;
        expires 7d;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/$SERVICE /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo ""
echo "✅ Deploy concluído!"
echo "   Acesse: http://$(curl -s ifconfig.me)"
echo "   Login: admin@loja.com / admin123"
echo "   ⚠  Troque a senha do admin após o primeiro acesso!"
