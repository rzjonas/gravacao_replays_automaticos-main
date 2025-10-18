import sys
import io

# Força a codificação de saída para UTF-8
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

# --- INÍCIO DA CONFIGURAÇÃO DE LOGGING ---

# 1. Logger de Orquestração (Nível Alto) - camera_recorder.log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)-8s - ORQUESTRADOR - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('camera_recorder.log', encoding='utf-8')
    ]
)
orchestrator_logger = logging.getLogger(__name__)

# 2. Logger do Servidor (Nível Detalhado) - infiniteplay_server.log
server_logger = logging.getLogger('infiniteplay_server')
server_logger.setLevel(logging.INFO)
server_logger.propagate = False 
if not server_logger.handlers:
    server_handler = logging.FileHandler('infiniteplay_server.log', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s.%(msecs)03d - %(levelname)-8s - SERVIDOR - (%(funcName)s) - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    server_handler.setFormatter(formatter)
    server_logger.addHandler(server_handler)

# --- FIM DA CONFIGURAÇÃO DE LOGGING ---


replay_em_execucao = False

def get_local_time():
    utc_time = datetime.now(timezone.utc)
    return utc_time.astimezone(timezone(timedelta(seconds=config.TIMEZONE_OFFSET)))

def criar_diretorio_se_nao_existir(diretorio):
    try:
        if not os.path.exists(diretorio):
            os.makedirs(diretorio)
            server_logger.info(f"Diretorio criado com sucesso: {diretorio}")
            return True
        server_logger.debug(f"Diretorio ja existe: {diretorio}")
        return False
    except Exception as e:
        server_logger.error(f"Falha ao criar diretorio {diretorio}: {str(e)}", exc_info=True)
        raise

def gravar_video(camera_rtsp, camera_id):
    server_logger.info(f"Iniciando thread de gravacao para camera {camera_id}")
    base_video_dir = config.VIDEO_DIRS.get(str(camera_id))
    if not base_video_dir:
        server_logger.error(f"Diretorio de video base nao configurado para camera {camera_id}")
        return

    while True:
        try:
            # Cria um subdiretório baseado na data atual
            agora = get_local_time()
            data_diretorio_str = agora.strftime("%d-%m-%Y")
            video_dir_diario = os.path.join(base_video_dir, data_diretorio_str)
            criar_diretorio_se_nao_existir(video_dir_diario)

            timestamp = agora.strftime("%d-%m-%Y_%H-%M-%S")
            video_filename = f"video_{config.ARENA_NAME}_camera_{camera_id}_{timestamp}.ts"
            video_path = os.path.join(video_dir_diario, video_filename)
            
            server_logger.info(f"Iniciando nova gravacao para camera {camera_id}: {video_path}")
            comando_ffmpeg = ["ffmpeg", "-rtsp_transport", "tcp", "-fflags", "+genpts", "-i", camera_rtsp, "-c:v", "copy", "-y", video_path]
            
            start_time = time.time()
            server_logger.info(f"Executando FFmpeg para camera {camera_id}: {' '.join(comando_ffmpeg)}")
            process = subprocess.run(comando_ffmpeg, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
            elapsed = time.time() - start_time
            if process.stderr: server_logger.debug(f"FFmpeg output (camera {camera_id}): {process.stderr}")
            server_logger.info(f"Gravacao concluida para camera {camera_id}: {video_path} (Duracao: {elapsed:.2f}s)")
        
        except subprocess.CalledProcessError as e:
            server_logger.error(f"Falha na gravacao para camera {camera_id}. Codigo: {e.returncode}, Erro: {e.stderr}")
            time.sleep(5)
        except Exception as e:
            server_logger.error(f"Erro inesperado na gravacao para camera {camera_id}: {str(e)}", exc_info=True)
            time.sleep(5)


def chamar_replay(timestamp_replay):
    global replay_em_execucao
    if replay_em_execucao:
        orchestrator_logger.warning(f"Replay ja em execucao. Ignorando chamada para timestamp {timestamp_replay}")
        return False
    replay_em_execucao = True
    orchestrator_logger.info(f"Disparando processo de replay para timestamp: {timestamp_replay}.")
    
    def executar_replay_script(camera_id, timestamp):
        try:
            subprocess.run([sys.executable, "replay.py", str(camera_id), timestamp], check=True)
        except subprocess.CalledProcessError as e:
            server_logger.error(f"Script replay.py falhou para camera {camera_id} (timestamp: {timestamp}) com codigo {e.returncode}.")
        except Exception as e:
            server_logger.error(f"Erro inesperado ao executar replay.py para camera {camera_id}: {str(e)}", exc_info=True)

    max_tentativas = 3
    tentativa = 1
    replays_validos = False
    replays = []
    while tentativa <= max_tentativas and not replays_validos:
        server_logger.info(f"Tentativa {tentativa} de gerar replays para timestamp: {timestamp_replay}")
        try:
            threads = []
            for camera_id in [1, 2]:
                thread = threading.Thread(target=executar_replay_script, args=(camera_id, timestamp_replay), name=f"ReplayCamera{camera_id}-{timestamp_replay}")
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
            replays_validos, replays = validar_replays(timestamp_replay)
            if not replays_validos:
                server_logger.warning(f"Replays invalidos na tentativa {tentativa}. Limpando arquivos e tentando novamente...")
                limpar_replays_invalidos(replays)
                tentativa += 1
                time.sleep(5)
            else:
                server_logger.info(f"Replays gerados e validados com sucesso na tentativa {tentativa}")
                break
        except Exception as e:
            server_logger.error(f"Erro ao processar replay na tentativa {tentativa}: {str(e)}", exc_info=True)
            tentativa += 1
            time.sleep(5)
    
    if tentativa > max_tentativas and not replays_validos:
        orchestrator_logger.critical(f"Falha ao gerar replays validos apos {max_tentativas} tentativas para timestamp: {timestamp_replay}")
        limpar_replays_invalidos(replays)
        
    replay_em_execucao = False
    orchestrator_logger.info(f"Processo de replay concluido para timestamp: {timestamp_replay}")
    return replays_validos

def chamar_upload_cloudinary(timestamp_replay):
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
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Replay acionado. Timestamp: {timestamp_replay}!".encode('utf-8'))

                def processar_replay_e_upload_thread(ts):
                    replays_validos = chamar_replay(ts)
                    if replays_validos:
                        orchestrator_logger.info(f"Replays validados para timestamp {ts}. Aguardando 5s para iniciar upload.")
                        time.sleep(5)
                        chamar_upload_cloudinary(ts)
                    else:
                        orchestrator_logger.error(f"Falha na validacao dos replays para timestamp {ts}. Upload nao sera executado.")

                threading.Thread(target=processar_replay_e_upload_thread, args=(timestamp_replay,), name=f"ReplayAndUploadThread-{timestamp_replay}").start()
                orchestrator_logger.info(f"Thread de replay e upload iniciada para timestamp: {timestamp_replay}.")
                
            except Exception as e:
                orchestrator_logger.error(f"Erro ao processar requisicao de replay: {str(e)}", exc_info=True)
                self.send_response(500)
                self.end_headers()
        else:
            server_logger.warning(f"Requisicao para caminho nao encontrado: {self.path}")
            self.send_response(404)
            self.end_headers()

def validar_replays(timestamp_replay):
    replays = []
    for camera_id in [1, 2]:
        replay_path = os.path.join(config.REPLAY_DIR, f"replay_{config.ARENA_NAME}_camera_{camera_id}_{timestamp_replay}.mp4")
        if os.path.exists(replay_path) and os.path.getsize(replay_path) > 0:
            replays.append(replay_path)
        else:
            server_logger.warning(f"Replay para camera {camera_id} nao encontrado ou vazio para timestamp {timestamp_replay}: {replay_path}")
            return False, replays
    server_logger.info(f"Replays validados com sucesso para timestamp: {timestamp_replay}")
    return True, replays

def limpar_replays_invalidos(replays):
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
        for camera_id, rtsp_url in [(1, config.CAMERA_1_RTSP_URL), (2, config.CAMERA_2_RTSP_URL)]:
            threading.Thread(target=gravar_video, args=(rtsp_url, camera_id), name=f"GravarCamera{camera_id}", daemon=True).start()
        
        # Threads de backup foram removidas
        
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