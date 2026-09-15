import pyautogui
import ollama
import os

def analisar_tela(pergunta_usuario):
    print("📸 Jarvis abrindo os olhos... Tirando print da tela.")
    
    # Caminho do print
    image_path = "temp_screen.png"
    
    # Tira o print e salva
    screenshot = pyautogui.screenshot()
    screenshot.save(image_path)
    
    # Envia para o modelo de visão Moondream
    # O contexto da pergunta ajuda o Moondream a focar no que você quer
    try:
        res = ollama.chat(model="moondream", messages=[
            {
                'role': 'user', 
                'content': f"Com base na imagem da minha tela, responda: {pergunta_usuario}", 
                'images': [image_path]
            }
        ])
        
        return res['message']['content']
    except Exception as e:
        return f"Senhor, tive uma falha ao processar a visão: {e}"
    finally:
        # Garante que o print seja deletado mesmo se a análise falhar
        if os.path.exists(image_path):
            os.remove(image_path)
