import os
import subprocess
import glob
import sys
import config
import logging
from datetime import datetime, timedelta

# Configuração do Logger para registrar erros e informações de execução em arquivo
replay_logger = logging.getLogger('replay_logger')
replay_logger.setLevel(logging.INFO)
replay_logger.propagate = False
if not replay_logger.handlers:
    handler = logging.FileHandler('replay.log', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - (%(funcName)s) - %(message)s')
    handler.setFormatter(formatter)
    replay_logger.addHandler(handler)

def validate_timestamp(timestamp):
    # Garante que o timestamp recebido segue estritamente o formato DD-MM-YYYY_HH-MM-SS
    # Isso evita erros de processamento mais à frente
    if not timestamp or len(timestamp) != 19: return False
    if timestamp[2] != '-' or timestamp[5] != '-' or timestamp[10] != '_' or timestamp[13] != '-' or timestamp[16] != '-': return False
    for i in [0, 1, 3, 4, 6, 7, 8, 9, 11, 12, 14, 15, 17, 18]:
        if not timestamp[i].isdigit(): return False
    return True

def get_next_index():
    # Lê o índice da música atual de um arquivo de texto para manter a sequência entre execuções
    MUSIC_INDEX_FILE = os.path.join(config.TEMP_DIR, "music_index.txt")
    if not os.path.exists(MUSIC_INDEX_FILE):
        with open(MUSIC_INDEX_FILE, "w") as f: f.write("0")
        return 0
    try:
        with open(MUSIC_INDEX_FILE, "r") as f:
            content = f.read().strip()
            if content.isdigit(): return int(content)
            else:
                with open(MUSIC_INDEX_FILE, "w") as f_corrected: f_corrected.write("0")
                return 0
    except Exception: return 0

def advance_index():
    # Incrementa o índice para que a próxima execução use a próxima música da lista
    MUSIC_INDEX_FILE = os.path.join(config.TEMP_DIR, "music_index.txt")
    index = get_next_index()
    new_index = (index + 1) % len(config.MUSIC_TRACKS)
    with open(MUSIC_INDEX_FILE, "w") as f: f.write(str(new_index))

def select_music_by_timestamp(timestamp):
    # Garante consistência: se duas câmeras gerarem replay ao mesmo tempo,
    # ambas usarão a mesma música baseada no timestamp do evento.
    filename = os.path.join(config.TEMP_DIR, f"music_by_timestamp_{timestamp}.txt")
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    
    if not os.path.exists(filename):
        # Se é um novo evento, pega o próximo índice e avança a lista
        index = get_next_index()
        with open(filename, "w") as f: f.write(str(index))
        advance_index()
    else:
        # Se já existe (ex: segunda câmera processando o mesmo lance), reutiliza o índice
        with open(filename, "r") as f: index = int(f.read())
    
    cleanup_old_timestamp_files()
    return config.MUSIC_TRACKS[index]

def cleanup_old_timestamp_files():
    # Remove arquivos de controle de música antigos (mantém só os 2 últimos)
    timestamp_files = sorted(glob.glob(os.path.join(config.TEMP_DIR, "music_by_timestamp_*.txt")), key=os.path.getmtime, reverse=True)
    for file_path in timestamp_files[2:]:
        try:
            os.remove(file_path)
            replay_logger.info(f"Arquivo de controle antigo removido: {os.path.basename(file_path)}")
        except Exception as e:
            replay_logger.error(f"Erro ao apagar {file_path}: {e}")
            
    # NOVO: Varredura para apagar vídeos temporários (replay_temp_*.mp4) que ficaram orfãos
    # Apaga se o arquivo tiver mais de 10 minutos de vida (600 segundos)
    temp_replays = glob.glob(os.path.join(config.REPLAY_DIR, "replay_temp_*.mp4"))
    for temp_file in temp_replays:
        try:
            idade_segundos = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(temp_file))).total_seconds()
            if idade_segundos > 600:
                os.remove(temp_file)
                replay_logger.info(f"Lixeiro: Video temporario orfao removido: {os.path.basename(temp_file)}")
        except Exception as e:
            pass

def find_video_and_offset(video_dir, timestamp_replay):
    try:
        target_dt = datetime.strptime(timestamp_replay, "%d-%m-%Y_%H-%M-%S")
    except ValueError:
        replay_logger.error(f"Timestamp do replay em formato invalido: {timestamp_replay}")
        return None, None

    # Define quais pastas procurar (dia atual e dia anterior, para cobrir viradas de noite)
    current_date_str = target_dt.strftime("%d-%m-%Y")
    prev_date_str = (target_dt - timedelta(days=1)).strftime("%d-%m-%Y")
    
    search_dirs = [
        os.path.join(video_dir, current_date_str),
        os.path.join(video_dir, prev_date_str)
    ]

    candidate_videos = []
    for folder in search_dirs:
        if os.path.exists(folder):
            files = glob.glob(os.path.join(folder, f"video_{config.ARENA_NAME}_camera_*.ts"))
            candidate_videos.extend(files)

    if not candidate_videos:
        replay_logger.warning(f"Nenhum video encontrado nas pastas {search_dirs}")
        return None, None

    relevant_video = None
    relevant_start_dt = None

    # Percorre os vídeos para encontrar aquele que contém o momento do replay
    for video_path in candidate_videos:
        try:
            filename = os.path.basename(video_path)
            parts = filename.split('_')
            # Extrai a data/hora do nome do arquivo (ex: video_ARENA_camera_ID_DD-MM-YYYY_HH-MM-SS.ts)
            datetime_str = f"{parts[-2]}_{parts[-1].replace('.ts', '')}"
            video_start_dt = datetime.strptime(datetime_str, "%d-%m-%Y_%H-%M-%S")

            # Lógica para encontrar o vídeo mais recente que começou ANTES do momento do replay
            if video_start_dt <= target_dt:
                if relevant_video is None or video_start_dt > relevant_start_dt:
                    relevant_video = video_path
                    relevant_start_dt = video_start_dt
        except (IndexError, ValueError):
            replay_logger.warning(f"Nao foi possivel extrair data do arquivo: {filename}")
            continue

    if not relevant_video:
        replay_logger.error(f"Nenhum video compativel encontrado para o timestamp {timestamp_replay}")
        return None, None

    # Calcula o deslocamento (offset) em segundos dentro do vídeo encontrado
    offset = (target_dt - relevant_start_dt).total_seconds()
    return relevant_video, offset


def create_replay(camera_id, timestamp_replay):
    replay_logger.info("----------------------------------------------------------")
    replay_logger.info(f"Iniciando processo CRIAR_REPLAY para Camera: {camera_id}, Timestamp: {timestamp_replay}")
    
    video_dir = config.VIDEO_DIRS.get(str(camera_id))
    if not video_dir:
        replay_logger.error(f"ID da camera {camera_id} invalido!")
        return

    if not validate_timestamp(timestamp_replay):
        replay_logger.error(f"Timestamp invalido: {timestamp_replay}. Deve estar no formato DD-MM-YYYY_HH-MM-SS.")
        return

    video_path, offset = find_video_and_offset(video_dir, timestamp_replay)
    
    if not video_path:
        replay_logger.error(f"Nenhum video relevante encontrado para a camera {camera_id} no timestamp {timestamp_replay}.")
        return

    if offset < 0:
        replay_logger.error(f"Offset negativo calculado. Horario alvo {timestamp_replay} é anterior ao inicio do video mais proximo {os.path.basename(video_path)}")
        return
    
    replay_logger.info(f"Video selecionado para replay: {os.path.basename(video_path)}")
    replay_logger.info(f"Offset calculado: {offset:.2f} segundos")

    os.makedirs(config.REPLAY_DIR, exist_ok=True)
    replay_filename = f"replay_{config.ARENA_NAME}_camera_{camera_id}_{timestamp_replay}.mp4"
    replay_path = os.path.join(config.REPLAY_DIR, replay_filename)
    replay_temp = os.path.join(config.REPLAY_DIR, f"replay_temp_{camera_id}_{timestamp_replay}.mp4")
    
    replay_logger.info(f"Iniciando recorte do video para a camera {camera_id} e timestamp {timestamp_replay}...")

    # Calcula o ponto de início subtraindo a duração do replay e um offset de segurança
    start_time_seconds = max(0, offset - config.REPLAY_DURATION - config.REPLAY_OFFSET)
    
    # Primeiro comando FFmpeg: Apenas recorta o trecho necessário (rápido)
    replay_command = [
        "ffmpeg", "-ss", str(start_time_seconds), 
        "-i", video_path, 
        "-t", str(config.REPLAY_DURATION), 
        "-c:v", "libx264", "-preset", "veryfast", "-an", 
        "-avoid_negative_ts", "make_zero", "-fflags", "+genpts", 
        "-y", replay_temp
    ]
    
    try:
        process = subprocess.run(replay_command, check=True, capture_output=True, text=True, encoding='utf-8')
        replay_logger.info(f"Recorte temporario criado: {replay_temp}")
        if process.stderr: replay_logger.debug(f"FFMPEG (recorte) stderr: {process.stderr}")
    except subprocess.CalledProcessError as e:
        replay_logger.error(f"Erro ao criar replay temporario para {timestamp_replay}. STDERR:\n{e.stderr}")
        return
    except Exception as e:
        replay_logger.error(f"Erro inesperado ao criar replay temporario para {timestamp_replay}: {e}", exc_info=True)
        return

    selected_music = select_music_by_timestamp(timestamp_replay)
    
    # Garante que o arquivo de música existe e tem tamanho maior que 1KB (não está vazio). 
    # Se falhar, pula para a próxima música automaticamente.
    tentativas = 0
    while (not os.path.exists(selected_music) or os.path.getsize(selected_music) < 1024) and tentativas < len(config.MUSIC_TRACKS):
        replay_logger.warning(f"Musica invalida ou vazia detectada: {selected_music}. Pulando para a proxima...")
        advance_index() # Avança a fila de músicas
        
        # Reescreve o controle temporário para que a câmera 2 saiba qual é a música corrigida
        novo_index = get_next_index()
        with open(os.path.join(config.TEMP_DIR, f"music_by_timestamp_{timestamp_replay}.txt"), "w") as f:
            f.write(str(novo_index))
            
        selected_music = config.MUSIC_TRACKS[novo_index]
        tentativas += 1

    replay_logger.info(f"Musica selecionada para {timestamp_replay}: {os.path.basename(selected_music)}")
    replay_logger.info(f"Aplicando edição e musica ao replay da câmera {camera_id} para o horario {timestamp_replay}...")
    
    # Segundo comando FFmpeg: Aplica filtros complexos (logos, rodapé) e adiciona música
    final_command = [
        "ffmpeg", "-i", replay_temp, 
        "-i", config.LOGO_PATH_LEFT, 
        "-i", config.LOGO_PATH_RIGHT, 
        "-i", config.LOGO_PATH,
        "-i", config.FOOTER_IMAGE_2, 
        "-i", selected_music,
        "-filter_complex",
        # Escala o vídeo principal e os elementos gráficos
        "[0:v]scale=1920:1080[v0];"
        "[1:v]scale=135:135[logo_left];[2:v]scale=150:84[logo_right];"
        "[3:v]scale=1920:1080[p];"
        "[4:v]scale=217:140[footer_2];"
        # Posiciona as logos e o rodapé sobre o vídeo (overlay)
        "[v0][logo_left]overlay=45:25[vll];"
        "[vll][logo_right]overlay=main_w-overlay_w-45:35[vl];"
        "[vl][footer_2]overlay=main_w-overlay_w-45:main_h-overlay_h-25:enable='between(t,0,23)'[video_with_logos];"
        # Concatena o vídeo processado
        "[video_with_logos][p]concat=n=2:v=1:a=0[vid_concat];"
        # Configura o áudio final
        "[5:a]aformat=sample_rates=48000:channel_layouts=stereo[aud_final]",
        "-map", "[vid_concat]", "-map", "[aud_final]",
        "-c:v", "libx264", "-c:a", "aac", "-t", "28", "-preset", "veryfast", "-y", replay_path
    ]

    try:
        process = subprocess.run(final_command, check=True, capture_output=True, text=True, encoding='utf-8')
        replay_logger.info(f"Replay final criado com SUCESSO para a camera {camera_id} e timestamp {timestamp_replay}: {replay_path}")
        if process.stderr: replay_logger.debug(f"FFMPEG (final) stderr: {process.stderr}")
    except subprocess.CalledProcessError as e:
        replay_logger.error(f"Erro ao criar replay final para {timestamp_replay}. STDERR:\n{e.stderr}")
    except Exception as e:
        replay_logger.error(f"Erro inesperado ao criar replay final para {timestamp_replay}: {e}", exc_info=True)
    finally:
        # Limpeza do arquivo temporário de recorte, mantendo apenas o resultado final
        if os.path.exists(replay_temp):
            try:
                os.remove(replay_temp)
                replay_logger.info(f"Arquivo temporario removido: {replay_temp}")
            except Exception as e:
                replay_logger.error(f"Erro ao remover arquivo temporario {replay_temp}: {e}")
    replay_logger.info("----------------------------------------------------------\n")


if __name__ == "__main__":
    # Ponto de entrada: verifica se os argumentos necessários foram passados
    if len(sys.argv) < 3:
        replay_logger.critical("Uso: python replay.py <camera_id> <timestamp_replay>")
        sys.exit(1)

    camera_id = sys.argv[1]
    timestamp_replay = sys.argv[2]
    create_replay(camera_id, timestamp_replay)
