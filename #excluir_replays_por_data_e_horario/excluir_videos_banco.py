import mysql.connector

DB_HOST = "br898.hostgator.com.br"
DB_USER = "infi0096_banco_de_dados"
DB_PASSWORD = "Ab151012@@"
DB_NAME = "infi0096_wp199"

def conectar_banco():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        print("Conectado ao banco de dados!")
        return conn
    except mysql.connector.Error as err:
        print(f"Erro ao conectar ao banco: {err}")
        return None

def excluir_registros_wp_replays(data_hora):
    """
    Exclui registros da tabela wp_replays.
    Aceita formatos:
    - DD-MM-YYYY (exclui tudo da data)
    - DD-MM-YYYY_HH-MM-SS (exclui específico)
    """
    conn = conectar_banco()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        
        if "_" in data_hora:
            # Formato com hora
            data_part, hora_part = data_hora.split("_")
            dia, mes, ano = data_part.split("-")
            hora_formatada = hora_part.replace("-", ":")
            data_formatada = f"{ano}-{mes}-{dia} {hora_formatada}"
            sql = "DELETE FROM wp_replays WHERE created_at = %s"
        else:
            # Apenas data
            dia, mes, ano = data_hora.split("-")
            data_formatada = f"{ano}-{mes}-{dia}"
            sql = "DELETE FROM wp_replays WHERE DATE(created_at) = %s"
        
        cursor.execute(sql, (data_formatada,))
        conn.commit()
        print(f"Registros para {data_hora} excluídos com sucesso!")
        
    except mysql.connector.Error as err:
        print(f"Erro ao excluir registros: {err}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Uso: python excluir_videos_banco.py DD-MM-YYYY [ou DD-MM-YYYY_HH-MM-SS]")
    else:
        excluir_registros_wp_replays(sys.argv[1])
        