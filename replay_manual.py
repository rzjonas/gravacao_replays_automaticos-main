import os
import subprocess
import glob
import sys
from datetime import datetime, timedelta
import threading
import time
import config

os.makedirs(config.TEMP_DIR, exist_ok=True)
MUSICA_INDEX_FILE = os.path.join(config.TEMP_DIR, "musica_index.txt")

def get_proximo_indice():
    if not os.path.exists(MUSICA_INDEX_FILE):
        with open(MUSICA_INDEX_FILE, "w") as f:
            f.write("0")
        return 0
    try:
        with open(MUSICA_INDEX_FILE, "r") as f:
            conteudo = f.read().strip()
            if conteudo.isdigit():
                return int(conteudo)
            else:
                with open(MUSICA_INDEX_FILE, "w") as f_corrigido:
                    f_corrigido.write("0")
                return 0
    except:
        return 0

def avancar_indice():
    index = get_proximo_indice()
    novo_index = (index + 1) % len(config.MUSICAS)
    with open(MUSICA_INDEX_FILE, "w") as f:
        f.write(str(novo_index))

def selecionar_musica_por_timestamp(timestamp):
    nome_arquivo = os.path.join(config.TEMP_DIR, f"musica_por_timestamp_{timestamp}.txt")
    
    if not os.path.exists(nome_arquivo):
        index = get_proximo_indice()
        with open(nome_arquivo, "w") as f:
            f.write(str(index))
        avancar_indice()
    else:
        with open(nome_arquivo, "r") as f:
            index = int(f.read())

    limpar_arquivos_antigos_timestamp()
    return config.MUSICAS[index]

def limpar_arquivos_antigos_timestamp():
    arquivos_timestamp = sorted(
        glob.glob(os.path.join(config.TEMP_DIR, "musica_por_timestamp_*.txt")),
        key=os.path.getmtime,
        reverse=True
    )
    for arquivo in arquivos_timestamp[2:]:
        try:
            os.remove(arquivo)
        except Exception as e:
            print(f"Erro ao apagar {arquivo}: {e}")
            
def encontrar_video_e_offset(video_dir, timestamp_replay):
    try:
        dt_alvo = datetime.strptime(timestamp_replay, "%d-%m-%Y_%H-%M-%S")
    except ValueError:
        print(f"Erro: Timestamp do replay em formato invalido: {timestamp_replay}")
        return None, None

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
        print(f"Aviso: Nenhum video encontrado nas pastas de busca para o diretorio {video_dir}")
        return None, None

    video_relevante = None
    dt_inicio_relevante = None

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
            print(f"Aviso: Nao foi possivel extrair data do arquivo: {nome_arquivo}")
            continue

    if not video_relevante:
        print(f"Erro: Nenhum video compativel encontrado para o timestamp {timestamp_replay}")
        return None, None

    offset = (dt_alvo - dt_inicio_relevante).total_seconds()
    return video_relevante, offset

def criar_replay(camera_id, horario_alvo):
    video_dir = config.VIDEO_DIRS.get(camera_id)
    if not video_dir:
        print(f"ID da camera {camera_id} invalido!")
        return

    video_path, offset = encontrar_video_e_offset(video_dir, horario_alvo)
    
    if not video_path:
        print(f"Nenhum video relevante encontrado para a camera {camera_id} no timestamp {horario_alvo}.")
        return

    if offset < 0:
        print(f"Erro: Offset negativo. Horario alvo {horario_alvo} e anterior ao video {os.path.basename(video_path)}")
        return
        
    print(f"Video selecionado para camera {camera_id}: {os.path.basename(video_path)}")
    print(f"Offset calculado: {offset:.2f} segundos")

    os.makedirs(config.REPLAY_DIR, exist_ok=True)
    replay_filename = f"replay_{config.ARENA_NAME}_camera_{camera_id}_{horario_alvo}.mp4"
    replay_path = os.path.join(config.REPLAY_DIR, replay_filename)
    replay_temp = os.path.join(config.REPLAY_DIR, f"replay_temp_{camera_id}_{horario_alvo}.mp4")
    
    start_time_segundos = max(0, offset - config.REPLAY_DURATION - config.REPLAY_OFFSET)
    
    comando_replay = [
        "ffmpeg",
        "-ss", str(start_time_segundos),
        "-i", video_path,
        "-t", str(config.REPLAY_DURATION),
        "-c:v", "libx264", "-preset", "veryfast", "-an",
        "-avoid_negative_ts", "make_zero", "-fflags", "+genpts",
        "-y", replay_temp
    ]
    
    try:
        print(f"Criando recorte temporario para camera {camera_id}...")
        subprocess.run(comando_replay, check=True, capture_output=True, text=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        print(f"Erro ao criar replay temporario (camera {camera_id}): {e.stderr}")
        return

    musica_selecionada = selecionar_musica_por_timestamp(horario_alvo)
    print(f"Musica selecionada para camera {camera_id}: {os.path.basename(musica_selecionada)}")

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
        f"[vl][rodape_2]overlay=main_w-overlay_w-45:main_h-overlay_h-25:enable='between(t,0,{config.REPLAY_DURATION})'[video_com_logos];"
        "[video_com_logos][p]concat=n=2:v=1:a=0[vid_concat];"
        "[5:a]aformat=sample_rates=48000:channel_layouts=stereo[aud_final]",
        "-map", "[vid_concat]", "-map", "[aud_final]",
        "-c:v", "libx264", "-c:a", "aac", "-t", str(config.REPLAY_DURATION + 5), "-preset", "veryfast", "-y", replay_path
    ]

    print(f"Criando replay final da camera {camera_id} para o horario {horario_alvo}: {replay_path}")
    try:
        subprocess.run(comando_final, check=True, capture_output=True, text=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        print(f"Erro ao criar replay final (camera {camera_id}): {e.stderr}")
    finally:
        if os.path.exists(replay_temp):
            os.remove(replay_temp)

def processar_todas_cameras(horario_alvo):
    print(f"Processando replays para o horario: {horario_alvo}")
    
    threads = []
    for camera_id in config.VIDEO_DIRS.keys():
        thread = threading.Thread(target=criar_replay, args=(camera_id, horario_alvo))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()

def executar_upload_cloudinary(timestamp):
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    caminho_upload = os.path.join(diretorio_atual, "upload_cloudinary.py")
    
    if os.path.exists(caminho_upload):
        print(f"Executando upload para o Cloudinary para o timestamp {timestamp}...")
        try:

            subprocess.run(["python", caminho_upload, timestamp], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Erro ao executar upload_cloudinary.py: {e}")
    else:
        print(f"Arquivo upload_cloudinary.py nao encontrado em: {diretorio_atual}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python acionar_replay_manual.py DD-MM-YYYY_HH-MM-SS")
        sys.exit(1)
        
    HORARIO_REPLAY = sys.argv[1]
    
    try:
        datetime.strptime(HORARIO_REPLAY, "%d-%m-%Y_%H-%M-%S")
    except ValueError:
        print("Erro: Formato de data/hora invalido. Use DD-MM-YYYY_HH-MM-SS")
        sys.exit(1)

    print(f"Definido horario do replay: {HORARIO_REPLAY}")
    processar_todas_cameras(HORARIO_REPLAY)
    print("Processamento de geracao de replays concluido!")

    time.sleep(5)
    
    executar_upload_cloudinary(HORARIO_REPLAY)
    