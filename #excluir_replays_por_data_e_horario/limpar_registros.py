import sys
import re

# Constante do Drive foi removida
CLOUDINARY_FOLDER = "arena_cema_esportes"

def limpar_registros(data_hora, usar_cloudinary=False, usar_banco=False):
    """
    Orquestra a limpeza de registros no Cloudinary e/ou Banco de Dados,
    com base nos flags fornecidos.
    """
    print(f"--- Iniciando processo de limpeza para '{data_hora}' ---")

    # Bloco de execução para o Google Drive foi completamente removido

    # Bloco de execução para o Cloudinary
    if usar_cloudinary:
        print("\n[SERVIÇO: Cloudinary]")
        try:
            from excluir_videos_cloudinary import excluir_recursos_de_todas_as_contas
            
            excluir_recursos_de_todas_as_contas(CLOUDINARY_FOLDER, data_hora)
            print("[Cloudinary] Tarefa concluída.")
        except Exception as e:
            print(f"[ERRO Cloudinary] Não foi possível concluir a operação: {e}")

    # Bloco de execução para o Banco de Dados
    if usar_banco:
        print("\n[SERVIÇO: Banco de Dados]")
        try:
            from excluir_videos_banco import excluir_registros_wp_replays
            
            excluir_registros_wp_replays(data_hora)
            print("[Banco de Dados] Tarefa concluída.")
        except Exception as e:
            print(f"[ERRO Banco de Dados] Não foi possível concluir a operação: {e}")

    print(f"\n--- Orquestração para '{data_hora}' finalizada. ---")


if __name__ == "__main__":
    args = sys.argv[1:]
    
    if len(args) < 2:
        # A mensagem de uso foi atualizada para remover a menção ao --drive e --delete-temp
        print("\nUso: python limpar_registros.py <data_hora> <serviço(s)>")
        print("   <data_hora>:   DD-MM-YYYY ou DD-MM-YYYY_HH-MM-SS")
        print("   <serviço(s)>:  Pelo menos um dos seguintes: --cloudinary, --banco")
        sys.exit(1)

    data_hora_arg = args[0]
    flags = set(args[1:])

    if not re.match(r'^\d{2}-\d{2}-\d{4}(?:_\d{2}-\d{2}-\d{2})?$', data_hora_arg):
        print(f"\n[ERRO] Formato de data inválido: '{data_hora_arg}'. Use DD-MM-YYYY ou DD-MM-YYYY_HH-MM-SS.")
        sys.exit(1)

    # A verificação dos flags do drive foi removida
    executar_cloudinary = "--cloudinary" in flags
    executar_banco = "--banco" in flags

    if not any([executar_cloudinary, executar_banco]):
        print("\n[ERRO] Nenhum serviço selecionado. Especifique pelo menos um: --cloudinary, ou --banco.")
        sys.exit(1)

    limpar_registros(
        data_hora=data_hora_arg,
        usar_cloudinary=executar_cloudinary,
        usar_banco=executar_banco
        # Parâmetros do drive foram removidos da chamada da função
    )
