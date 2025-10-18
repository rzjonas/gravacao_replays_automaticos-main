import os

# Base directory for the project
BASE_DIR = "/home/jonas-zanelato/codigos-gerais/inifiniteplay/gravacao_replays_automaticos-main"

# Arena configuration
ARENA_NAME = "arena_cema_esportes"

# Directory paths for video storage and processing
VIDEO_DIRS = {
    "1": "/mnt/HD 500GB/infiniteplay/videos_arena_cema_esportes_camera_1",
    "2": "/mnt/HD 500GB/infiniteplay/videos_arena_cema_esportes_camera_2"
}
REPLAY_DIR = os.path.join(BASE_DIR, "replays")
REPLAY_BACKUP_DIR = "/mnt/HD 500GB/infiniteplay/replays_backup_infiniteplay"
TEMP_DIR = os.path.join(BASE_DIR, "arquivos_temporarios")

# Directory for editing assets
EDICAO_DIR = os.path.join(BASE_DIR, "edicao")
LOGO_PATH = os.path.join(EDICAO_DIR, "Patrocinadores1.mp4")
LOGO_PATH_LEFT = os.path.join(EDICAO_DIR, "Logo_ArenaCemaEsportes.png")
LOGO_PATH_RIGHT = os.path.join(EDICAO_DIR, "Logo_InfinitePlay.png")
IMAGEM_RODAPE_1 = os.path.join(EDICAO_DIR, "Imagem_Rodape_1.png")
IMAGEM_RODAPE_2 = os.path.join(EDICAO_DIR, "Imagem_Rodape_2.png")

# Directory for music files
MUSICAS_DIR = os.path.join(BASE_DIR, "musicas")
MUSICAS = [
    os.path.join(MUSICAS_DIR, f"musica{i}.mp3") for i in range(1, 11)
]

# Database configuration
DB_HOST = "br898.hostgator.com.br"
DB_USER = "infi0096_banco_de_dados"
DB_PASSWORD = "Ab151012@@"
DB_NAME = "infi0096_wp199"

# Camera RTSP URLs
CAMERA_1_RTSP_URL = "rtsp://admin:Ab151012!@hdf08bgvb0g.sn.mynetname.net:1010/stream"
CAMERA_2_RTSP_URL = "rtsp://admin:Ab151012!@hdf08bgvb0g.sn.mynetname.net:1011/stream"

# Timing constants
CLIP_INTERVAL = 600  # 10 minutes in seconds
REPLAY_OFFSET = 3
REPLAY_DURATION = 23
TIMEZONE_OFFSET = -3 * 3600  # UTC-3 offset in seconds

# ==================================
# CONFIGURAÇÃO DO CLOUDINARY
# =================================

CLOUDINARY_FOLDER = "arena_cema_esportes"

######## google contato.infiniteplay@hotmail.com
CLOUDINARY_CLOUD_NAME = "dctwqteag"
CLOUDINARY_API_KEY = "113533831818486"
CLOUDINARY_API_SECRET = "InV2XMHyT-XLSqeIZtcetirf5ec"

######## google rzjonass@gmail.com
# CLOUDINARY_CLOUD_NAME = "dhvvqoo97"
# CLOUDINARY_API_KEY = "636321146868464"
# CLOUDINARY_API_SECRET = "_L8qDkDYEHjcUO5Gl4_jkb1D9nc"

# ==================================
