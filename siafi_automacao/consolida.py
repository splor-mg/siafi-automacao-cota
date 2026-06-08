import pandas as pd
import os
import shutil
from openpyxl import Workbook
 
# Caminhos das pastas e arquivos
folder_paths = [
    r'C:/Users/x70167581686/OneDrive - CAMG/General/@dcmefo/2026/Robo - Remanejamento e aprovacao de cota/Remanejamentos/',
    r'C:/Users/x70167581686/OneDrive - CAMG/General/@dcmefo/2026/Robo - Remanejamento e aprovacao de cota/Remanejamentos (SEGOV)/'
]
 
output_file = r'C:/Users/x70167581686/OneDrive - CAMG/General/@dcmefo/2026/Robo - Remanejamento e aprovacao de cota/Robo (IPU 2)/copia.xlsx'
 
processed_folder = r'C:/Users/x70167581686/OneDrive - CAMG/General/@dcmefo/2026/Robo - Remanejamento e aprovacao de cota/Realizados/'
 
# Função para criar arquivo de saída se não existir
def create_output_file_if_not_exists(output_file):
    if not os.path.exists(output_file):
        wb = Workbook()
        wb.save(output_file)
 
# Função para combinar arquivos Excel de múltiplas pastas
def combine_excel_files(folder_paths, output_file, processed_folder):
 
    # Criar pasta de processados se não existir
    if not os.path.exists(processed_folder):
        os.makedirs(processed_folder)
 
    # Criar arquivo de saída se não existir
    create_output_file_if_not_exists(output_file)
 
    dataframes = []
 
    # Percorrer as pastas de origem
    for folder_path in folder_paths:
        files_in_folder = os.listdir(folder_path)
        xlsx_files = [f for f in files_in_folder if f.endswith('.xlsx')]
 
        for filename in xlsx_files:
            file_path = os.path.join(folder_path, filename)
 
            try:
                # Ler planilha
                df = pd.read_excel(file_path)
 
                # Ajustar colunas I e J (índices 8 e 9)
                for col_index in [8, 9]:
                    if col_index < len(df.columns):
                        col_name = df.columns[col_index]
                        df[col_name] = (
                            pd.to_numeric(df[col_name], errors='coerce')
                            .round(2)
                        )
 
                dataframes.append(df)
                print(f"Arquivo {filename} lido e ajustado com sucesso.")
 
                # Mover arquivo processado
                shutil.move(
                    file_path,
                    os.path.join(processed_folder, filename)
                )
 
            except Exception as e:
                print(f"Erro ao processar o arquivo {filename}: {e}")
 
    # Verificar se houve leitura de dados
    if not dataframes:
        print("Nenhum dado foi lido das planilhas.")
        return
 
    # Consolidar dados
    combined_df = pd.concat(dataframes, ignore_index=True)
 
    # Salvar arquivo final
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        combined_df.to_excel(
            writer,