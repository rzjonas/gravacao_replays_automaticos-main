##########################################################
Acessar Painel - Multi
http://hdf08bgvb0g.sn.mynetname.net:9090/
http://hdf08bgvb0g.sn.mynetname.net:9091/

RTSP
http://hdf08bgvb0g.sn.mynetname.net:1010/
http://hdf08bgvb0g.sn.mynetname.net:1010/
##########################################################

Antes de qualquer coisa, precisa sempre criar o ambiente virtual separado:

source .venv/bin/activate

Esse é para instalar quando necessário: 

python3 -m venv .venv 

-----------------------------------------------------

python3 infiniteplay_server.py

-----------------------------------------------------

python3 "/home/jonas-zanelato/codigos-gerais/inifiniteplay/gravacao_replays_automaticos-main/#excluir_replays_por_data_e_horario/limpar_registros.py" 02-10-2025 --banco --cloudinary

-----------------------------------------------------

python3 "/home/jonas-zanelato/codigos-gerais/inifiniteplay/gravacao_replays_automaticos-main/#excluir_replays_por_data_e_horario/limpar_registros.py" 29-09-2025_20-46-13 --banco --cloudinary

-----------------------------------------------------

python3 acionar_replay_manual.py "29-09-2025_20-19-26"

----------------------------------------------------- 
 