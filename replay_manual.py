import os
import subprocess
import glob
import sys
from datetime import datetime, timedelta
import threading
import time
import config

# Garante que a pasta temporária exista antes de qualquer operação
os.makedirs(config.TEMP_DIR, exist_ok=True)
MUSIC_INDEX_FILE = os.path.join(config.TEMP_DIR, "music_index.txt")

def get_next_index():
    # Tenta ler o índice da última música usada para manter uma rotação
    # Se o arquivo não existir ou estiver corrompido, reseta para 0
    if not os.path.exists(MUSIC_INDEX_FILE):
        with open(MUSIC_INDEX_FILE, "w") as f:
            f.write("0")
        return 0
    try:
        with open(MUSIC_INDEX_FILE, "r") as f:
            content = f.read().strip()
            if content.isdigit():
                return int(content)
            else:
                with open(MUSIC_INDEX_FILE, "w") as f_corrected:
                    f_corrected.write("0")
                return 0
    except:
        return 0

def advance_index():
    # Atualiza o índice para a próxima música da lista, criando um loop (volta ao 0 quando acaba)
    index = get_next_index()
    new_index = (index + 1) % len(config.MUSIC_TRACKS)
    with open(MUSIC_INDEX_FILE, "w") as f:
        f.write(str(new_index))

def select_music_by_timestamp(timestamp):
    # Cria um vínculo entre o timestamp e a música escolhida.
    # Isso garante que, se reprocessarmos o mesmo momento, a música seja a mesma.
    filename = os.path.join(config.TEMP_DIR, f"music_by_timestamp_{timestamp}.txt")
    
    if not os.path.exists(filename):
        index = get_next_index()
        with open(filename, "w") as f:
            f.write(str(index))
        advance_index()
    else:
        with open(filename, "r") as f:
            index = int(f.read())

    cleanup_old_timestamp_files()
    return config.MUSIC_TRACKS[index]

def cleanup_old_timestamp_files():
    # Manutenção: Remove arquivos temporários antigos para não lotar o disco
    timestamp_files = sorted(
        glob.glob(os.path.join(config.TEMP_DIR, "music_by_timestamp_*.txt")),
        key=os.path.getmtime,
        reverse=True
    )
    # Mantém apenas os 2 mais recentes
    for file_path in timestamp_files[2:]:
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Erro ao apagar {file_path}: {e}")
            
def find_video_and_offset(video_dir, timestamp_replay):
    try:
        target_dt = datetime.strptime(timestamp_replay, "%d-%m-%Y_%H-%M-%S")
    except ValueError:
        print(f"Erro: Timestamp do replay em formato invalido: {timestamp_replay}")
        return None, None

    current_date_str = target_dt.strftime("%d-%m-%Y")
    prev_date_str = (target_dt - timedelta(days=1)).strftime("%d-%m-%Y")
    
    # Busca nas pastas do dia atual e do dia anterior.
    # Isso é crucial para eventos que ocorrem logo após a meia-noite (virada do dia).
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
        print(f"Aviso: Nenhum video encontrado nas pastas de busca para o diretorio {video_dir}")
        return None, None

    relevant_video = None
    relevant_start_dt = None

    # Itera sobre os vídeos encontrados para achar qual contém o momento do replay
    for video_path in candidate_videos:
        try:
            filename = os.path.basename(video_path)
            parts = filename.split('_')
            datetime_str = f"{parts[-2]}_{parts[-1].replace('.ts', '')}"
            video_start_dt = datetime.strptime(datetime_str, "%d-%m-%Y_%H-%M-%S")

            # Encontra o vídeo que começou antes do momento alvo, mas é o mais recente possível
            if video_start_dt <= target_dt:
                if relevant_video is None or video_start_dt > relevant_start_dt:
                    relevant_video = video_path
                    relevant_start_dt = video_start_dt
        except (IndexError, ValueError):
            print(f"Aviso: Nao foi possivel extrair data do arquivo: {filename}")
            continue

    if not relevant_video:
        print(f"Erro: Nenhum video compativel encontrado para o timestamp {timestamp_replay}")
        return None, None

    # Calcula o deslocamento (offset) em segundos dentro do vídeo encontrado
    offset = (target_dt - relevant_start_dt).total_seconds()
    return relevant_video, offset

def create_replay(camera_id, target_timestamp):
    video_dir = config.VIDEO_DIRS.get(camera_id)
    if not video_dir:
        print(f"ID da camera {camera_id} invalido!")
        return

    video_path, offset = find_video_and_offset(video_dir, target_timestamp)
    
    if not video_path:
        print(f"Nenhum video relevante encontrado para a camera {camera_id} no timestamp {target_timestamp}.")
        return

    if offset < 0:
        print(f"Erro: Offset negativo. Horario alvo {target_timestamp} e anterior ao video {os.path.basename(video_path)}")
        return
        
    print(f"Video selecionado para camera {camera_id}: {os.path.basename(video_path)}")
    print(f"Offset calculado: {offset:.2f} segundos")

    os.makedirs(config.REPLAY_DIR, exist_ok=True)
    replay_filename = f"replay_{config.ARENA_NAME}_camera_{camera_id}_{target_timestamp}.mp4"
    replay_path = os.path.join(config.REPLAY_DIR, replay_filename)
    replay_temp = os.path.join(config.REPLAY_DIR, f"replay_temp_{camera_id}_{target_timestamp}.mp4")
    
    # Define o ponto de corte inicial (segurança para não cortar exato demais)
    start_time_seconds = max(0, offset - config.REPLAY_DURATION - config.REPLAY_OFFSET)
    
    # Passo 1: Recorte rápido usando FFmpeg sem recodificação de áudio (-an)
    # Isso gera um arquivo temporário menor para processarmos depois
    replay_command = [
        "ffmpeg",
        "-ss", str(start_time_seconds),
        "-i", video_path,
        "-t", str(config.REPLAY_DURATION),
        "-c:v", "libx264", "-preset", "veryfast", "-an",
        "-avoid_negative_ts", "make_zero", "-fflags", "+genpts",
        "-y", replay_temp
    ]
    
    try:
        print(f"Criando recorte temporario para camera {camera_id}...")
        subprocess.run(replay_command, check=True, capture_output=True, text=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        print(f"Erro ao criar replay temporario (camera {camera_id}): {e.stderr}")
        return

    selected_music = select_music_by_timestamp(target_timestamp)
    
    # Garante que o arquivo de música existe e tem tamanho maior que 1KB (não está vazio). 
    # Se falhar, pula para a próxima música automaticamente.
    tentativas = 0
    while (not os.path.exists(selected_music) or os.path.getsize(selected_music) < 1024) and tentativas < len(config.MUSIC_TRACKS):
        print(f"Musica invalida ou vazia detectada: {selected_music}. Pulando para a proxima...")
        advance_index() # Avança a fila de músicas
        
        # Reescreve o controle temporário para que a câmera 2 saiba qual é a música corrigida
        novo_index = get_next_index()
        with open(os.path.join(config.TEMP_DIR, f"music_by_timestamp_{target_timestamp}.txt"), "w") as f:
            f.write(str(novo_index))
            
        selected_music = config.MUSIC_TRACKS[novo_index]
        tentativas += 1

    print(f"Musica selecionada para camera {camera_id}: {os.path.basename(selected_music)}")

    # Passo 2: Aplicação de filtros complexos (Logos, Rodapé e Áudio)
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

    print(f"Criando replay final da camera {camera_id} para o horario {target_timestamp}: {replay_path}")
    try:
        subprocess.run(final_command, check=True, capture_output=True, text=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        print(f"Erro ao criar replay final (camera {camera_id}): {e.stderr}")
    finally:
        # Limpeza: remove o arquivo intermediário para economizar espaço
        if os.path.exists(replay_temp):
            os.remove(replay_temp)

def process_all_cameras(target_timestamp):
    print(f"Processando replays para o horario: {target_timestamp}")
    
    threads = []
    # Itera sobre todas as câmeras configuradas e inicia uma thread para cada
    # Isso permite que os vídeos sejam processados simultaneamente (paralelismo)
    for camera_id in config.VIDEO_DIRS.keys():
        thread = threading.Thread(target=create_replay, args=(camera_id, target_timestamp))
        threads.append(thread)
        thread.start()
    
    # Aguarda todas as threads terminarem antes de seguir
    for thread in threads:
        thread.join()

def execute_cloudinary_upload(timestamp):
    # Chama o script separado responsável pelo upload para a nuvem
    current_dir = os.path.dirname(os.path.abspath(__file__))
    upload_script_path = os.path.join(current_dir, "upload_cloudinary.py")
    
    if os.path.exists(upload_script_path):
        print(f"Executando upload para o Cloudinary para o timestamp {timestamp}...")
        try:

            subprocess.run(["python", upload_script_path, timestamp], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Erro ao executar upload_cloudinary.py: {e}")
    else:
        print(f"Arquivo upload_cloudinary.py nao encontrado em: {current_dir}")

if __name__ == "__main__":
    # Ponto de entrada: Valida os argumentos da linha de comando
    if len(sys.argv) < 2:
        print("Uso: python replay_manual.py DD-MM-YYYY_HH-MM-SS")
        sys.exit(1)
        
    REPLAY_TIMESTAMP = sys.argv[1]
    
    try:
        datetime.strptime(REPLAY_TIMESTAMP, "%d-%m-%Y_%H-%M-%S")
    except ValueError:
        print("Erro: Formato de data/hora invalido. Use DD-MM-YYYY_HH-MM-SS")
        sys.exit(1)

    print(f"Definido horario do replay: {REPLAY_TIMESTAMP}")
    
    # Inicia o processamento paralelo das câmeras
    process_all_cameras(REPLAY_TIMESTAMP)
    print("Processamento de geracao de replays concluido!")

    time.sleep(5)
    
    # Após gerar os vídeos locais, inicia o upload
    execute_cloudinary_upload(REPLAY_TIMESTAMP)