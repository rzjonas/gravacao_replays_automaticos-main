import sys
import io

# Força a codificação UTF-8 na saída do terminal para evitar erros de caracteres (comum em alguns ambientes)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os
import time
import logging
import threading
import subprocess
from datetime import datetime, timezone, timedelta
import config
from http.server import BaseHTTPRequestHandler, HTTPServer

# Configuração do Logger do Orquestrador (Log geral do sistema)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)-8s - ORCHESTRATOR - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('camera_recorder.log', encoding='utf-8')
    ]
)
orchestrator_logger = logging.getLogger(__name__)

# Configuração do Logger do Servidor HTTP (Logs específicos das requisições)
server_logger = logging.getLogger('infiniteplay_server')
server_logger.setLevel(logging.INFO)
server_logger.propagate = False 
if not server_logger.handlers:
    server_handler = logging.FileHandler('infiniteplay_server.log', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s.%(msecs)03d - %(levelname)-8s - SERVER - (%(funcName)s) - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    server_handler.setFormatter(formatter)
    server_logger.addHandler(server_handler)

# Flag global para controle de concorrência (evita criar dois replays simultaneamente)
replay_in_progress = False

def get_local_time():
    """Retorna a data/hora atual ajustada pelo fuso horário definido no config."""
    utc_time = datetime.now(timezone.utc)
    return utc_time.astimezone(timezone(timedelta(seconds=config.TIMEZONE_OFFSET)))

def create_directory_if_not_exists(directory):
    """Função utilitária para garantir que a pasta de destino exista."""
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
            server_logger.info(f"Diretorio criado com sucesso: {directory}")
            return True
        server_logger.debug(f"Diretorio ja existe: {directory}")
        return False
    except Exception as e:
        server_logger.error(f"Falha ao criar diretorio {directory}: {str(e)}", exc_info=True)
        raise

def record_video(camera_rtsp, camera_id):
    """
    Loop infinito responsável por gravar o stream RTSP da câmera.
    Ele roda em uma thread separada para não bloquear o servidor.
    """
    server_logger.info(f"Iniciando thread de gravacao para camera {camera_id}")
    base_video_dir = config.VIDEO_DIRS.get(str(camera_id))
    
    if not base_video_dir:
        server_logger.error(f"Diretorio de video base nao configurado para camera {camera_id}")
        return

    while True:
        try:
            # Organiza as gravações em pastas por dia
            now = get_local_time()
            date_dir_str = now.strftime("%d-%m-%Y")
            daily_video_dir = os.path.join(base_video_dir, date_dir_str)
            create_directory_if_not_exists(daily_video_dir)

            timestamp = now.strftime("%d-%m-%Y_%H-%M-%S")
            video_filename = f"video_{config.ARENA_NAME}_camera_{camera_id}_{timestamp}.ts"
            video_path = os.path.join(daily_video_dir, video_filename)
            
            server_logger.info(f"Iniciando nova gravacao para camera {camera_id}: {video_path}")
            
            # Chama o FFmpeg via subprocesso para capturar o stream sem re-encodar (copy)
            ffmpeg_command = ["ffmpeg", "-rtsp_transport", "tcp", "-fflags", "+genpts", "-i", camera_rtsp, "-c:v", "copy", "-y", video_path]
            
            start_time = time.time()
            server_logger.info(f"Executando FFmpeg para camera {camera_id}: {' '.join(ffmpeg_command)}")
            
            # O script fica "preso" aqui enquanto o FFmpeg estiver gravando
            process = subprocess.run(ffmpeg_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
            
            elapsed = time.time() - start_time
            if process.stderr: 
                server_logger.debug(f"FFmpeg output (camera {camera_id}): {process.stderr}")
            
            server_logger.info(f"Gravacao concluida para camera {camera_id}: {video_path} (Duracao: {elapsed:.2f}s)")
        
        except subprocess.CalledProcessError as e:
            # Se o FFmpeg falhar, loga o erro e espera um pouco antes de tentar de novo
            server_logger.error(f"Falha na gravacao para camera {camera_id}. Codigo: {e.returncode}, Erro: {e.stderr}")
            time.sleep(5)
        except Exception as e:
            server_logger.error(f"Erro inesperado na gravacao para camera {camera_id}: {str(e)}", exc_info=True)
            time.sleep(5)

def trigger_replay(timestamp_replay):
    """Orquestra a criação dos clipes de replay chamando o script externo."""
    global replay_in_progress
    
    # Verifica se já existe um replay rodando para evitar sobrecarga
    if replay_in_progress:
        orchestrator_logger.warning(f"Replay ja em execucao. Ignorando chamada para timestamp {timestamp_replay}")
        return False
    
    replay_in_progress = True
    orchestrator_logger.info(f"Disparando processo de replay para timestamp: {timestamp_replay}.")
    
    def execute_replay_script(camera_id, timestamp):
        try:
            # Executa o script replay.py isoladamente para cada câmera
            subprocess.run([sys.executable, "replay.py", str(camera_id), timestamp], check=True)
        except subprocess.CalledProcessError as e:
            server_logger.error(f"Script replay.py falhou para camera {camera_id} (timestamp: {timestamp}) com codigo {e.returncode}.")
        except Exception as e:
            server_logger.error(f"Erro inesperado ao executar replay.py para camera {camera_id}: {str(e)}", exc_info=True)

    max_attempts = 3
    attempt = 1
    valid_replays = False
    replays = []

    # Lógica de retry: tenta gerar o replay até 3 vezes se falhar
    while attempt <= max_attempts and not valid_replays:
        server_logger.info(f"Tentativa {attempt} de gerar replays para timestamp: {timestamp_replay}")
        try:
            threads = []
            # Dispara o processamento das duas câmeras em paralelo para ganhar tempo
            for camera_id in [1, 2]:
                thread = threading.Thread(target=execute_replay_script, args=(camera_id, timestamp_replay), name=f"ReplayCamera{camera_id}-{timestamp_replay}")
                thread.start()
                threads.append(thread)
            
            # Aguarda ambas as threads terminarem
            for thread in threads:
                thread.join()
            
            valid_replays, replays = validate_replays(timestamp_replay)
            
            if not valid_replays:
                server_logger.warning(f"Replays invalidos na tentativa {attempt}. Limpando arquivos e tentando novamente...")
                cleanup_invalid_replays(replays)
                attempt += 1
                time.sleep(5)
            else:
                server_logger.info(f"Replays gerados e validados com sucesso na tentativa {attempt}")
                break
        except Exception as e:
            server_logger.error(f"Erro ao processar replay na tentativa {attempt}: {str(e)}", exc_info=True)
            attempt += 1
            time.sleep(5)
    
    if attempt > max_attempts and not valid_replays:
        orchestrator_logger.critical(f"Falha ao gerar replays validos apos {max_attempts} tentativas para timestamp: {timestamp_replay}")
        cleanup_invalid_replays(replays)
        
    replay_in_progress = False
    orchestrator_logger.info(f"Processo de replay concluido para timestamp: {timestamp_replay}")
    return valid_replays

def trigger_cloudinary_upload(timestamp_replay):
    """Chama o script externo de upload para a nuvem."""
    orchestrator_logger.info(f"Disparando processo de upload para Cloudinary para timestamp: {timestamp_replay}.")
    try:
        start_time = time.time()
        subprocess.run([sys.executable, "upload_cloudinary.py", timestamp_replay], check=True, text=True, encoding='utf-8')
        elapsed = time.time() - start_time
        orchestrator_logger.info(f"Script de upload para Cloudinary concluido com SUCESSO para timestamp {timestamp_replay} (Tempo: {elapsed:.2f}s)")
    except subprocess.CalledProcessError as e:
        orchestrator_logger.error(f"Script upload_cloudinary.py FALHOU para timestamp {timestamp_replay} com codigo {e.returncode}.")
    except Exception as e:
        orchestrator_logger.error(f"Erro inesperado no processo de upload (timestamp: {timestamp_replay}): {str(e)}", exc_info=True)

class ReplayHandler(BaseHTTPRequestHandler):
    def log_request(self, code='-', size='-'):
        server_logger.info(f"{self.address_string()} - \"{self.requestline}\" - Codigo: {code}")

    def do_GET(self):
        if self.path == '/replay':
            try:
                timestamp_replay = get_local_time().strftime("%d-%m-%Y_%H-%M-%S")
                orchestrator_logger.info(f"Recebida requisicao de replay. Timestamp gerado: {timestamp_replay}")
                
                # Resposta imediata ao cliente (Botão físico ou API) para não travar a interface
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Replay acionado. Timestamp: {timestamp_replay}!".encode('utf-8'))

                # Processamento pesado (gerar vídeo e upload) roda em thread separada (Background Task)
                def process_replay_and_upload_thread(ts):
                    valid_replays = trigger_replay(ts)
                    if valid_replays:
                        orchestrator_logger.info(f"Replays validados para timestamp {ts}. Aguardando 5s para iniciar upload.")
                        time.sleep(5)
                        trigger_cloudinary_upload(ts)
                    else:
                        orchestrator_logger.error(f"Falha na validacao dos replays para timestamp {ts}. Upload nao sera executado.")

                threading.Thread(target=process_replay_and_upload_thread, args=(timestamp_replay,), name=f"ReplayAndUploadThread-{timestamp_replay}").start()
                orchestrator_logger.info(f"Thread de replay e upload iniciada para timestamp: {timestamp_replay}.")
                
            except Exception as e:
                orchestrator_logger.error(f"Erro ao processar requisicao de replay: {str(e)}", exc_info=True)
                self.send_response(500)
                self.end_headers()
        else:
            server_logger.warning(f"Requisicao para caminho nao encontrado: {self.path}")
            self.send_response(404)
            self.end_headers()

def validate_replays(timestamp_replay):
    replays = []
    for camera_id in [1, 2]:
        replay_path = os.path.join(config.REPLAY_DIR, f"replay_{config.ARENA_NAME}_camera_{camera_id}_{timestamp_replay}.mp4")
        # Verifica se o arquivo existe e tem tamanho maior que 0
        if os.path.exists(replay_path) and os.path.getsize(replay_path) > 0:
            replays.append(replay_path)
        else:
            server_logger.warning(f"Replay para camera {camera_id} nao encontrado ou vazio para timestamp {timestamp_replay}: {replay_path}")
            return False, replays
    server_logger.info(f"Replays validados com sucesso para timestamp: {timestamp_replay}")
    return True, replays

def cleanup_invalid_replays(replays):
    for replay_path in replays:
        try:
            os.remove(replay_path)
            server_logger.info(f"Replay invalido removido: {replay_path}")
        except Exception as e:
            server_logger.error(f"Erro ao remover replay invalido {replay_path}: {str(e)}")

def run_server(port=8888):
    server_address = ('', port)
    httpd = HTTPServer(server_address, ReplayHandler)
    orchestrator_logger.info(f'Servidor HTTP iniciado na porta {port}')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        orchestrator_logger.info("Servidor HTTP recebeu sinal de interrupcao")
    except Exception as e:
        orchestrator_logger.critical(f"Erro fatal no servidor HTTP: {str(e)}", exc_info=True)
    finally:
        orchestrator_logger.info("Servidor HTTP encerrando")
        httpd.server_close()

def main():
    orchestrator_logger.info("======================================================")
    orchestrator_logger.info("Iniciando sistema de gravacao e replay")
    try:
        # Inicia threads de gravação para cada câmera (Daemon=True permite fechar junto com o programa principal)
        for camera_id, rtsp_url in [(1, config.CAMERA_1_RTSP_URL), (2, config.CAMERA_2_RTSP_URL)]:
            threading.Thread(target=record_video, args=(rtsp_url, camera_id), name=f"RecordCamera{camera_id}", daemon=True).start()
        
        # Inicia o servidor HTTP na thread principal
        server_thread = threading.Thread(target=run_server, name="HTTPServer")
        server_thread.start()
        orchestrator_logger.info("Todas as threads foram inicializadas com sucesso.")
        
        server_thread.join() 

    except KeyboardInterrupt:
        orchestrator_logger.info("Recebido sinal de interrupcao. Encerrando sistema...")
    except Exception as e:
        orchestrator_logger.critical(f"Erro critico no sistema: {str(e)}", exc_info=True)
    finally:
        orchestrator_logger.info("Sistema encerrado.")
        orchestrator_logger.info("======================================================\n")

if __name__ == "__main__":
    main()
