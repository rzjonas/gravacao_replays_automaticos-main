# InfinitePlay -- Documentação Técnica de Implantação

## 1. Visão Geral

Este documento descreve de forma técnica a estrutura, requisitos,
dependências e procedimentos necessários para implantação do sistema
**InfinitePlay** em um novo ambiente Linux (Ubuntu recomendado).

O sistema executa:

-   Gravação contínua de câmeras RTSP
-   Recorte automático dos trechos usando FFmpeg
-   Edição (logos, overlays, música, rodapé)
-   Geração do replay final
-   Upload para Cloudinary
-   Registro no banco MySQL
-   Automação com systemd e cron

------------------------------------------------------------------------

## 2. Estrutura do Projeto

A estrutura mínima necessária para funcionamento:

    infiniteplay/
    │
    ├── infiniteplay_server.py
    ├── replay.py
    ├── replay_manual.py
    ├── upload_cloudinary.py
    ├── config.py
    │
    ├── start_if_in_window.sh
    │
    ├── edicao/                       # Contém os arquivos para sobreposição na edição
    ├── videos/                       # Gravados automaticamente por dia
    ├── replays/                      # Replays gerados
    ├── replays_backup/               # Backup dos replays gerados
    ├── temp/                         # Arquivos temporários de música/timestamp
    │
    └── .venv/

------------------------------------------------------------------------

## 3. Dependências do Sistema

Instalar:

```
sudo apt update
sudo apt install -y python3-venv ffmpeg mysql-client cron
```

------------------------------------------------------------------------

## 4. Ambiente Virtual Python

```
cd /home/seu_usuario/infiniteplay
python3 -m venv .venv
source .venv/bin/activate
```

Instalar dependências:

```
pip install mysql-connector-python cloudinary
```

------------------------------------------------------------------------

## 5. Configuração `config.py`

O arquivo deve conter:

```
import os

BASE_DIR = 

ARENA_NAME = 

VIDEO_DIRS = {
    "1": ,
    "2": 
}
REPLAY_DIR = os.path.join(BASE_DIR, "replays")
REPLAY_BACKUP_DIR = 
TEMP_DIR = os.path.join(BASE_DIR, "arquivos_temporarios")

EDICAO_DIR = os.path.join(BASE_DIR, "edicao")
LOGO_PATH = os.path.join(EDICAO_DIR, "Patrocinadores1.mp4")
LOGO_PATH_LEFT = os.path.join(EDICAO_DIR, "Logo_ArenaCemaEsportes.png")
LOGO_PATH_RIGHT = os.path.join(EDICAO_DIR, "Logo_InfinitePlay.png")
IMAGEM_RODAPE_1 = os.path.join(EDICAO_DIR, "Imagem_Rodape_1.png")
IMAGEM_RODAPE_2 = os.path.join(EDICAO_DIR, "Imagem_Rodape_2.png")

MUSICAS_DIR = os.path.join(BASE_DIR, "musicas")
MUSICAS = [
    os.path.join(MUSICAS_DIR, f"musica{i}.mp3") for i in range(1, 11)
]

DB_HOST = 
DB_USER = 
DB_PASSWORD = 
DB_NAME = 

CAMERA_1_RTSP_URL = 
CAMERA_2_RTSP_URL = 

CLIP_INTERVAL = 600
REPLAY_OFFSET = 3
REPLAY_DURATION = 23
TIMEZONE_OFFSET = -3 * 3600

CLOUDINARY_FOLDER = 
CLOUDINARY_CLOUD_NAME = 
CLOUDINARY_API_KEY = 
CLOUDINARY_API_SECRET = 
```

------------------------------------------------------------------------

## 6. Execução Manual

### Servidor principal:

```
source .venv/bin/activate
python infiniteplay_server.py
```

### Replays manuais:

```
python replay_manual.py 01-01-2025_20-30-00
```

### Upload manual:

```
python upload_cloudinary.py 01-01-2025_20-30-00
```

------------------------------------------------------------------------

## 7. API Interna

### Geração automática via HTTP:

    GET /replay

Processo interno:

1.  Gera timestamp atual
2.  Cria replays das câmeras
3.  Valida arquivos
4.  Efetua upload
5.  Move arquivos para backup
6.  Remove originais

------------------------------------------------------------------------

## 8. Automação (systemd + cron)

### 8.1 Script Porteiro

Arquivo obrigatório: `start_if_in_window.sh`

```
#!/bin/bash

DIA_SEMANA=$(date +%u)
HORA_ATUAL=$(date +%H%M)

HORA_INICIO=1850  # 18:50
HORA_FIM=2230    # 22:30
DIA_INICIO=1     # Segunda
DIA_FIM=5        # Sexta

if [ "$DIA_SEMANA" -ge $DIA_INICIO ] && [ "$DIA_SEMANA" -le $DIA_FIM ] && \
   [ "$HORA_ATUAL" -ge "$HORA_INICIO" ] && [ "$HORA_ATUAL" -lt "$HORA_FIM" ];
then
  echo "Dentro do horário de operação. Iniciando o servidor..."
  /home/jonas-zanelato/codigos-gerais/inifiniteplay/gravacao_replays_automaticos-main/.venv/bin/python infiniteplay_server.py
else
  echo "Fora do horário de operação. O servidor não será iniciado."
  exit 0
fi
```

Executa o servidor **somente dentro do horário permitido**.

```
chmod +x start_if_in_window.sh
```

------------------------------------------------------------------------

### 8.2 Serviço systemd

Criar:

    sudo nano /etc/systemd/system/infiniteplay.service

Conteúdo:

    [Unit]
    Description=InfinitePlay — Automatic Recording and Replay System
    After=network.target

    [Service]
    User=seu_usuario
    Group=seu_usuario
    WorkingDirectory=/home/seu_usuario/infiniteplay
    ExecStart=/home/seu_usuario/infiniteplay/start_if_in_window.sh

    Restart=on-failure
    RestartSec=5s

    [Install]
    WantedBy=multi-user.target

Ativar:

```
sudo systemctl daemon-reload
sudo systemctl enable infiniteplay.service
```

------------------------------------------------------------------------

### 8.3 Agendamento via cron

```
sudo nano /etc/cron.d/infiniteplay-schedule
```

    50 18 * * 1-5 root /usr/bin/systemctl start infiniteplay.service
    30 22 * * 1-5 root /usr/bin/systemctl stop infiniteplay.service

------------------------------------------------------------------------

## 9. Logs e Debug

### Logs do systemd:

```
journalctl -u infiniteplay.service -n 50
```

### Logs específicos do sistema:

-   infiniteplay_server.log
-   camera_recorder.log
-   replay.log
-   upload_cloudinary.log

------------------------------------------------------------------------

## 10. Dependências Críticas

Se ausentes, o sistema falhará:

-   FFmpeg
-   Pasta edicao com logos e imagens
-   URLs RTSP válidas
-   Diretórios definidos em config.py
-   Credenciais MySQL
-   Credenciais Cloudinary

------------------------------------------------------------------------

## 11. Conclusão

Este documento fornece toda a base técnica necessária para implantação
completa do sistema InfinitePlay em qualquer computador ou VPS Linux.
Serve como documentação técnica e deve acompanhar o projeto para
futuras instalações.
 