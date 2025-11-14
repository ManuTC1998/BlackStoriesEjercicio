import os
import time
from dotenv import load_dotenv
import google.generativeai as genai
import anthropic
import ollama

# Función para pausar el script
def pause_for_user():
    input("[PULSA INTRO PARA CONTINUAR]\n")

class JudgeAI:
    def __init__(self, model_name="gemini-pro"):
        self.model_name = model_name
        self.client = self._initialize_model(model_name)
        self.history = []
        self.system_prompt = self._load_prompt("judge_prompt.md")
        self.story = self._extract_story_from_prompt(self.system_prompt)

    def _initialize_model(self, model_name):
        if "gemini" in model_name:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            return genai.GenerativeModel(model_name)
        elif "claude" in model_name:
            return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        elif "llama" in model_name:
            return ollama.Client(host=os.getenv("OLLAMA_BASE_URL"))
        else:
            raise ValueError(f"Modelo no soportado: {model_name}")

    def _load_prompt(self, filename):
        with open(f"prompts/{filename}", "r", encoding="utf-8") as f:
            return f.read()

    def _extract_story_from_prompt(self, prompt_content):
        start_tag = "<Black Story inicial>"
        end_tag = "</Black Story inicial>"
        start_index = prompt_content.find(start_tag)
        end_index = prompt_content.find(end_tag)
        if start_index != -1 and end_index != -1:
            return prompt_content[start_index + len(start_tag):end_index].strip()
        return "No se encontró la historia inicial en el prompt."

    def get_initial_story(self):
        return self.story

    def respond_to_question(self, question):
        # Para Gemini, el historial se maneja en el chat.
        # Para Anthropic y Ollama, se pasa en cada llamada.
        
        # Añadir la pregunta del detective al historial del juez
        self.history.append({"role": "user", "content": question})

        messages_for_model = [{"role": "system", "content": self.system_prompt}] + self.history

        if "gemini" in self.model_name:
            # Gemini maneja el historial internamente en el objeto chat
            # Necesitamos inicializar el chat con el system_prompt y la historia previa
            chat_history_for_gemini = []
            for msg in messages_for_model:
                if msg["role"] == "system":
                    chat_history_for_gemini.append({"role": "user", "content": msg["content"]})
                    chat_history_for_gemini.append({"role": "model", "content": "Entendido. Estoy listo para juzgar."})
                else:
                    chat_history_for_gemini.append(msg)
            
            chat = self.client.start_chat(history=chat_history_for_gemini)
            response = chat.send_message(question) # La última pregunta ya está en self.history
            answer = response.text.strip()
        elif "claude" in self.model_name:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=100,
                system=self.system_prompt,
                messages=[{"role": "user", "content": question}] # Claude espera solo el último mensaje del usuario
            )
            answer = response.content[0].text.strip()
        elif "llama" in self.model_name:
            response = self.client.chat(
                model=self.model_name,
                messages=messages_for_model
            )
            answer = response['message']['content'].strip()
        else:
            raise ValueError(f"Modelo no soportado para responder: {self.model_name}")

        # Añadir la respuesta del juez al historial
        self.history.append({"role": "model", "content": answer})
        return answer

class DetectiveAI:
    def __init__(self, model_name="llama3"):
        self.model_name = model_name
        self.client = self._initialize_model(model_name)
        self.history = []
        self.system_prompt = self._load_prompt("detective_prompt.md")

    def _initialize_model(self, model_name):
        if "gemini" in model_name:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            return genai.GenerativeModel(model_name)
        elif "claude" in model_name:
            return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        elif "llama" in model_name:
            return ollama.Client(host=os.getenv("OLLAMA_BASE_URL"))
        else:
            raise ValueError(f"Modelo no soportado: {model_name}")

    def _load_prompt(self, filename):
        with open(f"prompts/{filename}", "r", encoding="utf-8") as f:
            return f.read()

    def get_next_move(self, judge_history):
        # Construir el historial para el detective, incluyendo el system_prompt y el historial del juez
        messages_for_model = [{"role": "system", "content": self.system_prompt}]
        
        # Convertir el historial del juez a un formato que el detective pueda usar
        for entry in judge_history:
            if entry["role"] == "user":
                messages_for_model.append({"role": "assistant", "content": entry["content"]})
            elif entry["role"] == "model":
                messages_for_model.append({"role": "user", "content": entry["content"]})
        
        # Añadir el historial propio del detective
        messages_for_model.extend(self.history)

        user_instruction = "Formula una pregunta de sí/no o propone una solución si crees que la tienes. Si propones una solución, usa la palabra clave 'SOLUCIÓN:'."

        if "gemini" in self.model_name:
            chat = self.client.start_chat(history=messages_for_model)
            response = chat.send_message(user_instruction)
            next_move = response.text.strip()
        elif "claude" in self.model_name:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=200,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_instruction}] # Claude espera solo el último mensaje del usuario
            )
            next_move = response.content[0].text.strip()
        elif "llama" in self.model_name:
            response = self.client.chat(
                model=self.model_name,
                messages=messages_for_model + [{"role": "user", "content": user_instruction}]
            )
            next_move = response['message']['content'].strip()
        else:
            raise ValueError(f"Modelo no soportado para preguntar/solucionar: {self.model_name}")

        self.history.append({"role": "user", "content": next_move})
        return next_move

def main():
    load_dotenv()

    judge_ai = JudgeAI(model_name="gemini-pro") # O el modelo que se prefiera para el juez
    detective_ai = DetectiveAI(model_name="llama3") # O el modelo que se prefiera para el detective

    print(f"IA 1 ({judge_ai.model_name}): {judge_ai.get_initial_story()}")
    pause_for_user()

    game_over = False
    while not game_over:
        detective_move = detective_ai.get_next_move(judge_ai.history)
        print(f"IA 2 ({detective_ai.model_name}): {detective_move}")
        pause_for_user()

        judge_response = judge_ai.respond_to_question(detective_move)
        print(f"IA 1 ({judge_ai.model_name}): {judge_response}")
        pause_for_user()

        if "SOLUCIÓN:" in detective_move:
            if judge_response == "Es correcto":
                game_over = True
                print("¡La IA Detective ha resuelto el misterio!")
            else:
                print(f"IA 1 ({judge_ai.model_name}): No es correcto.")
                pause_for_user()
        
        if judge_response == "Es correcto" and "SOLUCIÓN:" not in detective_move:
            # Esto no debería ocurrir si el juez sigue las reglas, pero es una salvaguarda
            game_over = True
            print("¡La IA Juez ha terminado el juego inesperadamente!")


if __name__ == "__main__":
    main()
