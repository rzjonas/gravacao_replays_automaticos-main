import cloudinary
import cloudinary.api
from cloudinary.api import resources
import sys
import re

# Importa as configurações do arquivo separado
from config_excluir import CLOUDINARY_ACCOUNTS, CLOUDINARY_FOLDER

def configurar_cloudinary(account_creds):
    cloud_name = account_creds.get("cloud_name")
    api_key = account_creds.get("api_key")
    api_secret = account_creds.get("api_secret")

    if not all([cloud_name, api_key, api_secret]):
        print(f"Erro: As credenciais para a conta '{account_creds.get('name')}' estão incompletas.")
        return False
        
    try:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        print(f"Cloudinary configurado com sucesso para a conta: {account_creds.get('name')}")
        return True
    except Exception as e:
        print(f"Erro ao configurar a API do Cloudinary para '{account_creds.get('name')}': {e}")
        return False

def _excluir_recursos_da_conta_atual(folder, data_hora):
    public_ids_para_excluir = []
    
    try:
        if "_" in data_hora:
            print(f"Buscando por timestamp específico via API de Busca...")
            expression = f'folder="{folder}" AND filename:"{data_hora}"'
            print(f"Executando busca com a expressão: {expression}")
            search_results = cloudinary.Search().expression(expression).max_results(500).execute()
            recursos = search_results.get("resources", [])
            if recursos:
                public_ids_para_excluir = [res["public_id"] for res in recursos]

        else:
            print(f"Buscando por dia inteiro via listagem de recursos...")
            all_resources = []
            next_cursor = None
            
            while True:
                response = resources(
                    type='upload',
                    resource_type='video',
                    prefix=f"{folder}/",
                    max_results=500,
                    next_cursor=next_cursor
                )
                all_resources.extend(response.get("resources", []))
                next_cursor = response.get("next_cursor")
                if not next_cursor:
                    break
            
            print(f"Total de {len(all_resources)} recursos encontrados na pasta. Filtrando por data '{data_hora}'...")
            
            public_ids_para_excluir = [
                res["public_id"] for res in all_resources if data_hora in res["public_id"]
            ]

        if not public_ids_para_excluir:
            print(f"Nenhum recurso encontrado no Cloudinary para o padrão '{data_hora}' na pasta '{folder}'.")
            return

        print(f"\nRecursos a serem excluídos ({len(public_ids_para_excluir)}):")
        for public_id in public_ids_para_excluir:
            print(f"- {public_id}")

        print("\nEnviando solicitação de exclusão em lote...")
        resultado_exclusao = cloudinary.api.delete_resources(
            public_ids_para_excluir,
            resource_type="video",
            invalidate=True
        )

        print("\nRelatório de exclusão:")
        deleted_info = resultado_exclusao.get('deleted', {})
        for pid, status in deleted_info.items():
            print(f"- {pid}: {status}")

        not_found_info = resultado_exclusao.get('not_found', [])
        if not_found_info:
            print("\nRecursos não encontrados durante a tentativa de exclusão:")
            for pid in not_found_info:
                print(f"- {pid}")

        print(f"\nOperação concluída nesta conta. {len(deleted_info)} recurso(s) excluído(s).")

    except Exception as e:
        print(f"Ocorreu um erro durante a operação com o Cloudinary: {e}")

def excluir_recursos_de_todas_as_contas(folder, data_hora):
    print("--- Iniciando processo de limpeza no Cloudinary em múltiplas contas ---")
    
    if not CLOUDINARY_ACCOUNTS:
        print("Nenhuma conta Cloudinary foi configurada na lista 'CLOUDINARY_ACCOUNTS'.")
        return

    for i, account in enumerate(CLOUDINARY_ACCOUNTS):
        print(f"\n========================================================")
        print(f"PROCESSANDO CONTA {i+1}/{len(CLOUDINARY_ACCOUNTS)}: {account.get('name')}")
        print(f"========================================================")
        
        if configurar_cloudinary(account):
            _excluir_recursos_da_conta_atual(folder, data_hora)
        else:
            print(f"\nA varredura foi pulada para a conta '{account.get('name')}' devido a um erro na configuração.")

    print("\n--- Processo de limpeza em todas as contas Cloudinary finalizado ---")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUso: python excluir_videos_cloudinary.py DD-MM-YYYY [ou DD-MM-YYYY_HH-MM-SS]")
        print("Exemplo (dia inteiro): python excluir_videos_cloudinary.py 25-12-2024")
        print("Exemplo (específico):  python excluir_videos_cloudinary.py 25-12-2024_10-30-00")
        sys.exit(1)
    
    data_hora_arg = sys.argv[1]

    if not re.match(r'^\d{2}-\d{2}-\d{4}(?:_\d{2}-\d{2}-\d{2})?$', data_hora_arg):
        print("\nErro: Formato de data/hora inválido.")
        print("Use DD-MM-YYYY ou DD-MM-YYYY_HH-MM-SS")
        sys.exit(1)
    
    excluir_recursos_de_todas_as_contas(CLOUDINARY_FOLDER, data_hora_arg)