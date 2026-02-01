# filename: create_folder_and_add_text.py

import os

def execute(folder_name, text_content):
    if not folder_name or not text_content:
        raise ValueError("Folder name and text content must be provided")

    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    file_path = os.path.join(folder_name, "output.txt")
    with open(file_path, 'w') as file:
        file.write(text_content)