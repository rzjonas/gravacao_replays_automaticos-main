import os
import subprocess
import glob
import sys
import config
import logging
from datetime import datetime, timedelta

# --- INÍCIO DA CONFIGURAÇÃO DE LOGGING ---
replay_logger = logging.getLogger('replay_logger')
replay_logger.setLevel(logging.INFO)
replay_logger.propagate = False
if not replay_logger.handlers:
    handler = logging.FileHandler('replay.log', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - (%(funcName)s) - %(message)s')
    handler.setFormatter(formatter)
    replay_logger.addHandler(handler)
# --- FIM DA CONFIGURAÇÃO DE LOGGING ---

def validate_timestamp(timestamp):
    if not timestamp or len(timestamp) != 19: return False
    if timestamp[2] != '-' or timestamp[5] != '-' or timestamp[10] != '_' or timestamp[13] != '-' or timestamp[16] != '-': return False
    for i in [0, 1, 3, 4, 6, 7, 8, 9, 11, 12, 14, 15, 17, 18]:
        if not timestamp[i].isdigit(): return False
    return True

def get_proximo_indice():
    MUSICA_INDEX_FILE = os.path.join(config.TEMP_DIR, "musica_index.txt")
    if not os.path.exists(MUSICA_INDEX_FILE):
        with open(MUSICA_INDEX_FILE, "w") as f: f.write("0")
        return 0
    try:
        with open(MUSICA_INDEX_FILE, "r") as f:
            conteudo = f.read().strip()
            if conteudo.isdigit(): return int(conteudo)
            else:
                with open(MUSICA_INDEX_FILE, "w") as f_corrigido: f_corrigido.write("0")
                return 0
    except Exception: return 0

def avancar_indice():
    MUSICA_INDEX_FILE = os.path.join(config.TEMP_DIR, "musica_index.txt")
    index = get_proximo_indice()
    novo_index = (index + 1) % len(config.MUSICAS)
    with open(MUSICA_INDEX_FILE, "w") as f: f.write(str(novo_index))

def selecionar_musica_por_timestamp(timestamp):
    nome_arquivo = os.path.join(config.TEMP_DIR, f"musica_por_timestamp_{timestamp}.txt")
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    if not os.path.exists(nome_arquivo):
        index = get_proximo_indice()
        with open(nome_arquivo, "w") as f: f.write(str(index))
        avancar_indice()
    else:
        with open(nome_arquivo, "r") as f: index = int(f.read())
    limpar_arquivos_antigos_timestamp()
    return config.MUSICAS[index]

def limpar_arquivos_antigos_timestamp():
    arquivos_timestamp = sorted(glob.glob(os.path.join(config.TEMP_DIR, "musica_por_timestamp_*.txt")), key=os.path.getmtime, reverse=True)
    for arquivo in arquivos_timestamp[2:]:
        try:
            os.remove(arquivo)
            replay_logger.info(f"Arquivo de indice de musica antigo removido: {os.path.basename(arquivo)}")
        except Exception as e:
            replay_logger.error(f"Erro ao apagar arquivo de indice de musica {arquivo}: {e}")

def encontrar_video_e_offset(video_dir, timestamp_replay):
    try:
        dt_alvo = datetime.strptime(timestamp_replay, "%d-%m-%Y_%H-%M-%S")
    except ValueError:
        replay_logger.error(f"Timestamp do replay em formato invalido: {timestamp_replay}")
        return None, None

    # Define as pastas do dia atual e do dia anterior para busca
    data_atual_str = dt_alvo.strftime("%d-%m-%Y")
    data_anterior_str = (dt_alvo - timedelta(days=1)).strftime("%d-%m-%Y")
    
    pastas_busca = [
        os.path.join(video_dir, data_atual_str),
        os.path.join(video_dir, data_anterior_str)
    ]

    videos_candidatos = []
    for pasta in pastas_busca:
        if os.path.exists(pasta):
            arquivos = glob.glob(os.path.join(pasta, f"video_{config.ARENA_NAME}_camera_*.ts"))
            videos_candidatos.extend(arquivos)

    if not videos_candidatos:
        replay_logger.warning(f"Nenhum video encontrado nas pastas {pastas_busca}")
        return None, None

    video_relevante = None
    dt_inicio_relevante = None

    # Encontra o vídeo que começou mais recentemente, mas ANTES do timestamp do replay
    for video_path in videos_candidatos:
        try:
            nome_arquivo = os.path.basename(video_path)
            partes = nome_arquivo.split('_')
            data_hora_str = f"{partes[-2]}_{partes[-1].replace('.ts', '')}"
            dt_inicio_video = datetime.strptime(data_hora_str, "%d-%m-%Y_%H-%M-%S")

            if dt_inicio_video <= dt_alvo:
                if video_relevante is None or dt_inicio_video > dt_inicio_relevante:
                    video_relevante = video_path
                    dt_inicio_relevante = dt_inicio_video
        except (IndexError, ValueError):
            replay_logger.warning(f"Nao foi possivel extrair data do arquivo: {nome_arquivo}")
            continue

    if not video_relevante:
        replay_logger.error(f"Nenhum video compativel encontrado para o timestamp {timestamp_replay}")
        return None, None

    offset = (dt_alvo - dt_inicio_relevante).total_seconds()
    return video_relevante, offset


def criar_replay(camera_id, timestamp_replay):
    replay_logger.info("----------------------------------------------------------")
    replay_logger.info(f"Iniciando processo CRIAR_REPLAY para Camera: {camera_id}, Timestamp: {timestamp_replay}")
    
    video_dir = config.VIDEO_DIRS.get(str(camera_id))
    if not video_dir:
        replay_logger.error(f"ID da camera {camera_id} invalido!")
        return

    if not validate_timestamp(timestamp_replay):
        replay_logger.error(f"Timestamp invalido: {timestamp_replay}. Deve estar no formato DD-MM-YYYY_HH-MM-SS.")
        return

    video_path, offset = encontrar_video_e_offset(video_dir, timestamp_replay)
    
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

    start_time_segundos = max(0, offset - config.REPLAY_DURATION - config.REPLAY_OFFSET)
    comando_replay = ["ffmpeg", "-ss", str(start_time_segundos), "-i", video_path, "-t", str(config.REPLAY_DURATION), "-c:v", "libx264", "-preset", "veryfast", "-an", "-avoid_negative_ts", "make_zero", "-fflags", "+genpts", "-y", replay_temp]
    
    try:
        process = subprocess.run(comando_replay, check=True, capture_output=True, text=True, encoding='utf-8')
        replay_logger.info(f"Recorte temporario criado: {replay_temp}")
        if process.stderr: replay_logger.debug(f"FFMPEG (recorte) stderr: {process.stderr}")
    except subprocess.CalledProcessError as e:
        replay_logger.error(f"Erro ao criar replay temporario para {timestamp_replay}. STDERR:\n{e.stderr}")
        return
    except Exception as e:
        replay_logger.error(f"Erro inesperado ao criar replay temporario para {timestamp_replay}: {e}", exc_info=True)
        return

    musica_selecionada = selecionar_musica_por_timestamp(timestamp_replay)
    replay_logger.info(f"Musica selecionada para {timestamp_replay}: {os.path.basename(musica_selecionada)}")
    replay_logger.info(f"Aplicando edição e musica ao replay da câmera {camera_id} para o horario {timestamp_replay}...")
    
    comando_final = [
        "ffmpeg", "-i", replay_temp, "-i", config.LOGO_PATH_LEFT, "-i", config.LOGO_PATH_RIGHT, "-i", config.LOGO_PATH,
        "-i", config.IMAGEM_RODAPE_2, "-i", musica_selecionada,
        "-filter_complex",
        "[0:v]scale=1920:1080[v0];"
        "[1:v]scale=135:135[logo_left];[2:v]scale=150:84[logo_right];"
        "[3:v]scale=1920:1080[p];"
        "[4:v]scale=200:133[rodape_2];"
        "[v0][logo_left]overlay=45:25[vll];"
        "[vll][logo_right]overlay=main_w-overlay_w-45:35[vl];"
        "[vl][rodape_2]overlay=main_w-overlay_w-45:main_h-overlay_h-25:enable='between(t,0,23)'[video_com_logos];"
        "[video_com_logos][p]concat=n=2:v=1:a=0[vid_concat];"
        "[5:a]aformat=sample_rates=48000:channel_layouts=stereo[aud_final]",
        "-map", "[vid_concat]", "-map", "[aud_final]",
        "-c:v", "libx264", "-c:a", "aac", "-t", "28", "-preset", "veryfast", "-y", replay_path
    ]

    try:
        process = subprocess.run(comando_final, check=True, capture_output=True, text=True, encoding='utf-8')
        replay_logger.info(f"Replay final criado com SUCESSO para a camera {camera_id} e timestamp {timestamp_replay}: {replay_path}")
        if process.stderr: replay_logger.debug(f"FFMPEG (final) stderr: {process.stderr}")
    except subprocess.CalledProcessError as e:
        replay_logger.error(f"Erro ao criar replay final para {timestamp_replay}. STDERR:\n{e.stderr}")
    except Exception as e:
        replay_logger.error(f"Erro inesperado ao criar replay final para {timestamp_replay}: {e}", exc_info=True)
    finally:
        if os.path.exists(replay_temp):
            try:
                os.remove(replay_temp)
                replay_logger.info(f"Arquivo temporario removido: {replay_temp}")
            except Exception as e:
                replay_logger.error(f"Erro ao remover arquivo temporario {replay_temp}: {e}")
    replay_logger.info("----------------------------------------------------------\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        replay_logger.critical("Uso: python replay.py <camera_id> <timestamp_replay>")
        sys.exit(1)

    camera_id = sys.argv[1]
    timestamp_replay = sys.argv[2]
    criar_replay(camera_id, timestamp_replay)
    