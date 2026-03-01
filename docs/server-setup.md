# Ilm Atlas — Server Setup

One-time setup for a fresh Hetzner CX22 VPS (Ubuntu 24.04).

## 1. Initial server hardening

```bash
# SSH in as root
ssh root@<VPS_IP>

# Create deploy user
adduser deploy
usermod -aG sudo deploy

# Set up SSH key auth for deploy user
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh

# Disable password auth
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# Firewall
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

## 2. Install Docker

```bash
# As deploy user
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy
# Log out and back in for group change
```

## 3. Deploy the application

```bash
cd /opt
sudo mkdir ilmatlas && sudo chown deploy:deploy ilmatlas
cd ilmatlas

# Clone repo
git clone https://github.com/<your-username>/ilm-atlas.git .

# Create .env from template
cp .env.production.template .env
nano .env  # Fill in all secrets

# Start services
docker compose up -d
```

## 4. DNS

Point these records to the VPS IP:

| Record | Type | Value |
|--------|------|-------|
| ilmatlas.com | A | <VPS_IP> |
| api.ilmatlas.com | A | <VPS_IP> |

Wait for DNS propagation (~5-30 minutes), then Caddy auto-provisions SSL.

## 5. Email DNS (Resend)

Add the DNS records from Resend dashboard for `ilmatlas.com`:
- SPF (TXT record)
- DKIM (CNAME records)
- Return-Path (CNAME record)

## 6. Create admin user

```bash
cd /opt/ilmatlas
docker compose exec backend python -c "
import asyncio
from app.database import async_session
from app.models.db import User
from passlib.hash import bcrypt

async def create():
    async with async_session() as s:
        user = User(
            email='admin@ilmatlas.com',
            password_hash=bcrypt.hash('CHANGE_THIS_PASSWORD'),
            role='admin',
            email_verified=True,
        )
        s.add(user)
        await s.commit()
        print(f'Admin created: {user.id}')

asyncio.run(create())
"
```

## 7. Migrate Qdrant data

Option A — Re-run ingestion scripts on the server:
```bash
docker compose exec backend python ../scripts/ingest_quran.py
# etc.
```

Option B — Snapshot from local Qdrant and restore:
```bash
# On local machine: create snapshot
curl -X POST http://localhost:6333/collections/ilm-atlas-v1/snapshots

# Download snapshot, upload to VPS, restore
# See: https://qdrant.tech/documentation/concepts/snapshots/
```
