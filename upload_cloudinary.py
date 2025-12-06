import os
import re
import glob
import time
import shutil
import mysql.connector
import config
import sys
import logging
from datetime import datetime, timezone, timedelta

import cloudinary
import cloudinary.uploader

# --- INÍCIO DA CONFIGURAÇÃO DE LOGGING ---
# Configura um logger específico para este script
cloudinary_logger = logging.getLogger('cloudinary_logger')
cloudinary_logger.setLevel(logging.INFO)
cloudinary_logger.propagate = False # Impede que os logs se espalhem para o logger raiz

# Cria um handler para escrever os logs em 'upload_cloudinary.log'
# Garante que o handler não seja adicionado múltiplas vezes
if not cloudinary_logger.handlers:
    handler = logging.FileHandler('upload_cloudinary.log', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    cloudinary_logger.addHandler(handler)
# --- FIM DA CONFIGURAÇÃO DE LOGGING ---

def backup_video(arquivo_path):
    """
    Copia o vídeo de replay para um diretório de backup diário.
    """
    try:
        if not os.path.exists(arquivo_path):
            cloudinary_logger.warning(f"Arquivo de origem para backup não encontrado: {arquivo_path}")
            return
            
        arquivo_nome = os.path.basename(arquivo_path)
        # Usa o horário local para criar a pasta de backup
        agora = datetime.now(timezone.utc).astimezone(timezone(timedelta(seconds=config.TIMEZONE_OFFSET)))
        data_diretorio = agora.strftime("%d-%m-%Y")
        
        backup_base_dir = config.REPLAY_BACKUP_DIR
        destino_dir = os.path.join(backup_base_dir, f"replays_backup_{data_diretorio}")
        
        if not os.path.exists(backup_base_dir): os.makedirs(backup_base_dir)
        if not os.path.exists(destino_dir): os.makedirs(destino_dir)
        
        destino_path = os.path.join(destino_dir, arquivo_nome)
        shutil.copy(arquivo_path, destino_path)
        cloudinary_logger.info(f"BACKUP: Video '{arquivo_nome}' copiado para '{destino_dir}'")
    except Exception as e:
        cloudinary_logger.error(f"ERRO no backup do vídeo '{os.path.basename(arquivo_path)}': {e}", exc_info=True)

def excluir_video(arquivo_path):
    """
    Exclui um arquivo de vídeo da pasta de replays.
    """
    try:
        if os.path.exists(arquivo_path):
            os.remove(arquivo_path)
            cloudinary_logger.info(f"EXCLUIDO: Video '{os.path.basename(arquivo_path)}' removido da pasta de replays.")
        else:
            cloudinary_logger.warning(f"Arquivo para exclusao nao encontrado: {arquivo_path}")
    except Exception as e:
        cloudinary_logger.error(f"ERRO ao excluir o video '{os.path.basename(arquivo_path)}': {e}", exc_info=True)

def conectar_banco():
    try:
        return mysql.connector.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
    except mysql.connector.Error as err:
        cloudinary_logger.error(f"Erro ao conectar ao banco: {err}")
        return None

def extrair_data_hora(nome_arquivo):
    padrao = rf"replay_{config.ARENA_NAME}_camera_\d+_(\d{{2}}-\d{{2}}-\d{{4}})_(\d{{2}}-\d{{2}}-\d{{2}})\.mp4"
    resultado = re.search(padrao, nome_arquivo)
    if resultado:
        data, hora = resultado.group(1), resultado.group(2)
        return f"{data[6:10]}-{data[3:5]}-{data[0:2]} {hora.replace('-', ':')}"
    return None

def configurar_cloudinary():
    cloudinary.config(
        cloud_name=config.CLOUDINARY_CLOUD_NAME,
        api_key=config.CLOUDINARY_API_KEY,
        api_secret=config.CLOUDINARY_API_SECRET,
        secure=True
    )
    cloudinary_logger.info("Cloudinary configurado com sucesso.")

def upload_para_cloudinary(arquivo_path):
    try:
        nome_arquivo_sem_ext = os.path.splitext(os.path.basename(arquivo_path))[0]
        cloudinary_logger.info(f"Iniciando upload para Cloudinary: {nome_arquivo_sem_ext}")
        resultado = cloudinary.uploader.upload(
            arquivo_path,
            resource_type="video",
            public_id=nome_arquivo_sem_ext,
            folder=config.CLOUDINARY_FOLDER
        )
        public_id = resultado.get('public_id')
        secure_url = resultado.get('secure_url')
        if public_id and secure_url:
            cloudinary_logger.info(f"Upload concluido! URL: {secure_url}")
            return public_id, secure_url
        else:
            cloudinary_logger.error(f"Erro no upload: ID publico ou URL não retornados. Resposta: {resultado}")
            return None, None
    except Exception as e:
        cloudinary_logger.error(f"Erro detalhado ao fazer upload para Cloudinary: {e}", exc_info=True)
        return None, None

def salvar_url_no_banco(public_id, video_url, created_at):
    conn = conectar_banco()
    if not conn: return
    try:
        with conn.cursor() as cursor:
            sql = """
            INSERT INTO wp_replays (file_id, download_link, created_at, arena)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE download_link = VALUES(download_link);
            """
            cursor.execute(sql, (public_id, video_url, created_at, config.ARENA_NAME))
            conn.commit()
        cloudinary_logger.info(f"URL do replay (ID: {public_id}) salva no banco de dados!")
    except mysql.connector.Error as err:
        cloudinary_logger.error(f"Erro ao inserir URL no banco de dados: {err}")
    finally:
        if conn and conn.is_connected(): conn.close()

def processar_replays(timestamp_alvo=None):
    cloudinary_logger.info("==========================================================")
    cloudinary_logger.info(f"Iniciando processo de upload para o Cloudinary... Timestamp: {timestamp_alvo or 'Todos'}")
    configurar_cloudinary()
    
    if timestamp_alvo:
        search_pattern = os.path.join(config.REPLAY_DIR, f"replay_*_{timestamp_alvo}.mp4")
    else:
        search_pattern = os.path.join(config.REPLAY_DIR, "*.mp4")
        
    arquivos_replay = glob.glob(search_pattern)

    if not arquivos_replay:
        cloudinary_logger.warning("Nenhum replay encontrado para processar.")
        return

    for arquivo in arquivos_replay:
        public_id, video_url = upload_para_cloudinary(arquivo)
        
        if public_id and video_url:
            created_at = extrair_data_hora(os.path.basename(arquivo))
            if created_at:
                salvar_url_no_banco(public_id, video_url, created_at)
                backup_video(arquivo)
                excluir_video(arquivo)
            else:
                cloudinary_logger.error(f"Nao foi possivel extrair data e hora do arquivo: {arquivo}")
        
        time.sleep(1)

    cloudinary_logger.info(f"Processo de upload para Cloudinary concluido. Timestamp: {timestamp_alvo or 'Todos'}")
    cloudinary_logger.info("==========================================================\n")

if __name__ == "__main__":
    timestamp_argumento = sys.argv[1] if len(sys.argv) > 1 else None
    processar_replays(timestamp_argumento)
    