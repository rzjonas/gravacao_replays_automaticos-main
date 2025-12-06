#!/bin/bash

DIA_SEMANA=$(date +%u)
HORA_ATUAL=$(date +%H%M)

HORA_INICIO=1850  # 18:50
HORA_FIM=2230    # 22:30
DIA_INICIO=1     # Segunda
DIA_FIM=7        # Domingo

if [ "$DIA_SEMANA" -ge $DIA_INICIO ] && [ "$DIA_SEMANA" -le $DIA_FIM ] && \
   [ "$HORA_ATUAL" -ge "$HORA_INICIO" ] && [ "$HORA_ATUAL" -lt "$HORA_FIM" ];
then
  echo "Dentro do horário de operação. Iniciando o servidor..."
  /home/jonas-zanelato/codigos-gerais/inifiniteplay/gravacao_replays_automaticos-main/.venv/bin/python infiniteplay_server.py
else
  echo "Fora do horário de operação. O servidor não será iniciado."
  exit 0
fi
