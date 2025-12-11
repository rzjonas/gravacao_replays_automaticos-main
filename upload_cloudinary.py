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

# Configuração de logs para monitorar as operações de upload separadamente
cloudinary_logger = logging.getLogger('cloudinary_logger')
cloudinary_logger.setLevel(logging.INFO)
cloudinary_logger.propagate = False

if not cloudinary_logger.handlers:
    handler = logging.FileHandler('upload_cloudinary.log', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    cloudinary_logger.addHandler(handler)

def backup_video(file_path):
    """
    Cria uma cópia de segurança do vídeo antes de excluí-lo da pasta principal.
    Organiza os backups em subpastas por dia.
    """
    try:
        if not os.path.exists(file_path):
            cloudinary_logger.warning(f"Arquivo de origem para backup não encontrado: {file_path}")
            return
            
        filename = os.path.basename(file_path)
        # Ajusta para o fuso horário local definido na configuração
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(seconds=config.TIMEZONE_OFFSET)))
        date_dir_str = now.strftime("%d-%m-%Y")
        
        backup_base_dir = config.REPLAY_BACKUP_DIR
        dest_dir = os.path.join(backup_base_dir, f"replays_backup_{date_dir_str}")
        
        # Garante que a pasta de destino exista
        if not os.path.exists(backup_base_dir): os.makedirs(backup_base_dir)
        if not os.path.exists(dest_dir): os.makedirs(dest_dir)
        
        dest_path = os.path.join(dest_dir, filename)
        shutil.copy(file_path, dest_path)
        cloudinary_logger.info(f"BACKUP: Video '{filename}' copiado para '{dest_dir}'")
    except Exception as e:
        cloudinary_logger.error(f"ERRO no backup do vídeo '{os.path.basename(file_path)}': {e}", exc_info=True)

def delete_video(file_path):
    """
    Remove o vídeo original para liberar espaço em disco após o upload e backup.
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            cloudinary_logger.info(f"EXCLUIDO: Video '{os.path.basename(file_path)}' removido da pasta de replays.")
        else:
            cloudinary_logger.warning(f"Arquivo para exclusao nao encontrado: {file_path}")
    except Exception as e:
        cloudinary_logger.error(f"ERRO ao excluir o video '{os.path.basename(file_path)}': {e}", exc_info=True)

def connect_db():
    """Estabelece a conexão com o banco de dados MySQL."""
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

def extract_datetime(filename):
    """
    Extrai a data e hora do nome do arquivo usando Expressão Regular (Regex).
    Formato esperado: replay_ARENA_camera_ID_DD-MM-YYYY_HH-MM-SS.mp4
    """
    pattern = rf"replay_{config.ARENA_NAME}_camera_\d+_(\d{{2}}-\d{{2}}-\d{{4}})_(\d{{2}}-\d{{2}}-\d{{2}})\.mp4"
    result = re.search(pattern, filename)
    if result:
        date_part, time_part = result.group(1), result.group(2)
        # Converte para o formato DATETIME padrão do MySQL: YYYY-MM-DD HH:MM:SS
        return f"{date_part[6:10]}-{date_part[3:5]}-{date_part[0:2]} {time_part.replace('-', ':')}"
    return None

def configure_cloudinary():
    """Inicializa a SDK do Cloudinary com as credenciais."""
    cloudinary.config(
        cloud_name=config.CLOUDINARY_CLOUD_NAME,
        api_key=config.CLOUDINARY_API_KEY,
        api_secret=config.CLOUDINARY_API_SECRET,
        secure=True
    )
    cloudinary_logger.info("Cloudinary configurado com sucesso.")

def upload_to_cloudinary(file_path):
    """Realiza o upload do vídeo e retorna o ID e a URL segura."""
    try:
        filename_no_ext = os.path.splitext(os.path.basename(file_path))[0]
        cloudinary_logger.info(f"Iniciando upload para Cloudinary: {filename_no_ext}")
        
        result = cloudinary.uploader.upload(
            file_path,
            resource_type="video",
            public_id=filename_no_ext,
            folder=config.CLOUDINARY_FOLDER
        )
        
        public_id = result.get('public_id')
        secure_url = result.get('secure_url')
        
        if public_id and secure_url:
            cloudinary_logger.info(f"Upload concluido! URL: {secure_url}")
            return public_id, secure_url
        else:
            cloudinary_logger.error(f"Erro no upload: ID publico ou URL não retornados. Resposta: {result}")
            return None, None
    except Exception as e:
        cloudinary_logger.error(f"Erro detalhado ao fazer upload para Cloudinary: {e}", exc_info=True)
        return None, None

def save_url_to_db(public_id, video_url, created_at):
    """Salva o link do replay na tabela do WordPress (wp_replays)."""
    conn = connect_db()
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

def process_replays(target_timestamp=None):
    """
    Função principal que orquestra o fluxo:
    1. Busca arquivos locais (todos ou um específico).
    2. Faz upload para nuvem.
    3. Salva link no Banco de Dados.
    4. Faz backup e deleta o original.
    """
    cloudinary_logger.info("==========================================================")
    cloudinary_logger.info(f"Iniciando processo de upload para o Cloudinary... Timestamp: {target_timestamp or 'Todos'}")
    configure_cloudinary()
    
    # Define se busca um arquivo específico pelo timestamp ou processa todos da pasta
    if target_timestamp:
        search_pattern = os.path.join(config.REPLAY_DIR, f"replay_*_{target_timestamp}.mp4")
    else:
        search_pattern = os.path.join(config.REPLAY_DIR, "*.mp4")
        
    replay_files = glob.glob(search_pattern)

    if not replay_files:
        cloudinary_logger.warning("Nenhum replay encontrado para processar.")
        return

    for file_path in replay_files:
        public_id, video_url = upload_to_cloudinary(file_path)
        
        if public_id and video_url:
            created_at = extract_datetime(os.path.basename(file_path))
            if created_at:
                # Se upload e extração de data funcionarem, segue o fluxo de persistência e limpeza
                save_url_to_db(public_id, video_url, created_at)
                backup_video(file_path)
                delete_video(file_path)
            else:
                cloudinary_logger.error(f"Nao foi possivel extrair data e hora do arquivo: {file_path}")
        
        # Pausa leve para não sobrecarregar a rede em processamentos em lote
        time.sleep(1)

    cloudinary_logger.info(f"Processo de upload para Cloudinary concluido. Timestamp: {target_timestamp or 'Todos'}")
    cloudinary_logger.info("==========================================================\n")

if __name__ == "__main__":
    # Permite executar o script passando um timestamp como argumento na linha de comando
    timestamp_arg = sys.argv[1] if len(sys.argv) > 1 else None
    process_replays(timestamp_arg)
