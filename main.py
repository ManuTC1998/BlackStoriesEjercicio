import os
import time
import argparse
from dotenv import load_dotenv
import google.generativeai as genai
import anthropic
import ollama
from colorama import Fore, Style, init

# Inicializar colorama
init(autoreset=True)

# Función para pausar el script
def pause_for_user():
    input(f"{Style.BRIGHT}[PULSA INTRO PARA CONTINUAR]{Style.RESET_ALL}\n")

class JudgeAI:
    def __init__(self, model_name="gemini-2.5-flash", is_ollama_model=False):
        self.model_name = model_name
        self.is_ollama_model = is_ollama_model
        self.client = self._initialize_model(model_name)
        self.history = []
        self.system_prompt = self._load_prompt("judge_prompt.md")
        self.chat_session = None # Para mantener la sesión de chat de Gemini
        self.story = self._generate_initial_story()

    def _initialize_model(self, model_name):
        if "gemini" in model_name:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            return genai.GenerativeModel(model_name)
        elif "claude" in model_name:
            return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        elif self.is_ollama_model: # Usar el nuevo indicador
            return ollama.Client(host=os.getenv("OLLAMA_BASE_URL"))
        else:
            raise ValueError(f"Modelo no soportado: {model_name}")

    def _load_prompt(self, filename):
        with open(f"prompts/{filename}", "r", encoding="utf-8") as f:
            prompt_content = f.read()
        
        # Guardar el prompt utilizado con fecha y hora
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        prompt_history_filename = f"prompts/{filename.replace('.md', '')}_{timestamp}.md"
        with open(prompt_history_filename, "w", encoding="utf-8") as f:
            f.write(prompt_content)
            
        return prompt_content

    def _generate_initial_story(self):
        if "gemini" in self.model_name:
            # Lógica existente para Gemini
            initial_history_for_story_gen = [
                {"role": "user", "parts": [{"text": self.system_prompt + "\nAhora, crea una historia de misterio de Black Story con temática Kingdom Hearts. La historia debe ser detallada y presentar un enigma que la IA Detective deba resolver. No incluyas la respuesta."}]}
            ]
            chat_long = self.client.start_chat(history=initial_history_for_story_gen)
            response_long = chat_long.send_message("Genera la historia larga.")
            long_story_content = response_long.text.strip()

            initial_history_for_short_story_gen = [
                {"role": "user", "parts": [{"text": self.system_prompt + "\nBasado en la siguiente historia larga, crea una versión muy concisa de la historia de misterio de Black Story con temática Kingdom Hearts, que sirva como la 'Black Story inicial' para el juego. Debe ser un resumen muy breve que presente el enigma sin dar la solución. No incluyas la respuesta."}]},
                {"role": "model", "parts": [{"text": long_story_content}]}
            ]
            chat_short = self.client.start_chat(history=initial_history_for_short_story_gen)
            response_short = chat_short.send_message("Genera la versión corta de la historia.")
            short_story_content = response_short.text.strip()
            
            # Inicializar la sesión de chat principal del juez con la historia corta
            self.chat_session = self.client.start_chat(history=[
                {"role": "user", "parts": [{"text": self.system_prompt + "\nAquí está la historia inicial del juego:\n" + short_story_content}]},
                {"role": "model", "parts": [{"text": "Entendido. Estoy listo para juzgar."}]}
            ])

        elif self.is_ollama_model:
            # Lógica para Ollama
            # Generar historia larga
            messages_long = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": "Crea una historia de misterio detallada de al menos 150 palabras con un enigma. No incluyas la respuesta ni la solución."}
            ]
            response_long = self.client.chat(model=self.model_name, messages=messages_long)
            long_story_content = response_long['message']['content'].strip()

            # Generar historia corta
            messages_short = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Basado en la siguiente historia larga, crea un resumen muy breve (máximo 30 palabras) que presente el enigma sin dar la solución. No incluyas la respuesta.\nHistoria larga:\n{long_story_content}"}
            ]
            response_short = self.client.chat(model=self.model_name, messages=messages_short)
            short_story_content = response_short['message']['content'].strip()

            # Para Ollama, el chat_session se gestiona de forma diferente, no hay un objeto de sesión persistente como en Gemini.
            # El historial se pasa en cada llamada a `client.chat`.
            # Sin embargo, para mantener la consistencia con la estructura del juez, podemos inicializar `self.history`
            # con el prompt del sistema y la historia corta.
            self.history.append({"role": "system", "content": self.system_prompt})
            self.history.append({"role": "user", "content": "Aquí está la historia inicial del juego:\n" + short_story_content})
            self.history.append({"role": "model", "content": "Entendido. Estoy listo para juzgar."})
            self.chat_session = None # No se usa para Ollama de esta manera

        else:
            raise ValueError("La generación de historias iniciales solo está implementada para Gemini y Ollama.")
        
        # Guardar las historias en la carpeta 'stories' (común para ambos)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        story_filename = f"stories/story_{timestamp}.md"
        with open(story_filename, "w", encoding="utf-8") as f:
            f.write(f"--- Historia Larga ({timestamp}) ---\n")
            f.write(long_story_content)
            f.write(f"\n\n--- Historia Corta ({timestamp}) ---\n")
            f.write(short_story_content)
            f.write("\n")
        
        # Envolver la historia corta generada en los tags para consistencia
        return f"<Black Story inicial>\n{short_story_content}\n</Black Story inicial>"

    def get_initial_story(self):
        return self.story

    def respond_to_question(self, question):
        # Añadir la pregunta del detective al historial del juez
        self.history.append({"role": "user", "content": question})

        if "gemini" in self.model_name:
            if not self.chat_session:
                raise RuntimeError("La sesión de chat de Gemini no ha sido inicializada.")
            
            response = self.chat_session.send_message(question)
            answer = response.text.strip()
        elif "claude" in self.model_name:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=100,
                system=self.system_prompt,
                messages=[{"role": "user", "content": question}] # Claude espera solo el último mensaje del usuario
            )
            answer = response.content[0].text.strip()
        elif self.is_ollama_model: # Usar el nuevo indicador
            messages_for_model = [{"role": "system", "content": self.system_prompt}] + self.history
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
    def __init__(self, model_name="gemini-2.5-flash", is_ollama_model=False):
        self.model_name = model_name
        self.is_ollama_model = is_ollama_model
        self.client = self._initialize_model(model_name)
        self.history = []
        self.system_prompt = self._load_prompt("detective_prompt.md")

    def _initialize_model(self, model_name):
        if "gemini" in model_name:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            return genai.GenerativeModel(model_name)
        elif "claude" in model_name:
            return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        elif self.is_ollama_model: # Usar el nuevo indicador
            return ollama.Client(host=os.getenv("OLLAMA_BASE_URL"))
        else:
            raise ValueError(f"Modelo no soportado: {model_name}")

    def _load_prompt(self, filename):
        with open(f"prompts/{filename}", "r", encoding="utf-8") as f:
            return f.read()

    def get_next_move(self, judge_history):
        if "gemini" in self.model_name:
            # Construir el historial para Gemini, asegurando la alternancia user/model
            # El system_prompt se fusiona con el primer mensaje del usuario
            gemini_history = []
            
            # Añadir el system_prompt como parte del primer mensaje del usuario
            initial_user_message = self.system_prompt
            if judge_history:
                initial_user_message += "\n" + judge_history[0]["content"]
                gemini_history.append({"role": "user", "parts": [{"text": initial_user_message}]})
                # Añadir el resto del historial del juez
                for i in range(1, len(judge_history)):
                    msg = judge_history[i]
                    gemini_history.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
            else:
                gemini_history.append({"role": "user", "parts": [{"text": initial_user_message}]})
            
            # Añadir el historial propio del detective
            for entry in self.history:
                gemini_history.append({"role": entry["role"], "parts": [{"text": entry["content"]}]})

            user_instruction = "Formula una pregunta de sí/no o propone una solución si crees que la tienes. Si propones una solución, usa la palabra clave 'SOLUCIÓN:'."
            
            chat = self.client.start_chat(history=gemini_history)
            response = chat.send_message(user_instruction)
            next_move = response.text.strip()
        elif "claude" in self.model_name:
            messages_for_model = [{"role": "system", "content": self.system_prompt}]
            for entry in judge_history:
                if entry["role"] == "user":
                    messages_for_model.append({"role": "assistant", "content": entry["content"]})
                elif entry["role"] == "model":
                    messages_for_model.append({"role": "user", "content": entry["content"]})
            messages_for_model.extend(self.history)
            user_instruction = "Formula una pregunta de sí/no o propone una solución si crees que la tienes. Si propones una solución, usa la palabra clave 'SOLUCIÓN:'."
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=200,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_instruction}] # Claude espera solo el último mensaje del usuario
            )
            next_move = response.content[0].text.strip()
        elif self.is_ollama_model: # Usar el nuevo indicador
            messages_for_model = [{"role": "system", "content": self.system_prompt}]
            for entry in judge_history:
                # Asegurarse de que el historial se construya correctamente para Ollama
                # El rol 'user' en judge_history se convierte en 'assistant' para el detective
                # y el rol 'model' en judge_history se convierte en 'user' para el detective
                if entry["role"] == "user":
                    messages_for_model.append({"role": "assistant", "content": entry["content"]})
                elif entry["role"] == "model":
                    messages_for_model.append({"role": "user", "content": entry["content"]})
            messages_for_model.extend(self.history)
            user_instruction = "Formula una pregunta de sí/no o propone una solución si crees que la tienes. Si propones una solución, usa la palabra clave 'SOLUCIÓN:'."
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

    parser = argparse.ArgumentParser(description="Simulación del juego Black Story con IAs.")
    parser.add_argument("-m1", "--model1", type=str, default="gemini-2.5-flash",
                        help="Modelo de IA a usar para el Juez (ej. gemini-2.5-flash, claude-3-opus-20240229, ollama gemma3:270m).")
    parser.add_argument("-m2", "--model2", type=str, default="gemini-2.5-flash",
                        help="Modelo de IA a usar para el Detective (ej. gemini-2.5-flash, claude-3-opus-20240229, ollama gemma3:270m).")
    args = parser.parse_args()

    # Procesar el modelo para el Juez
    model_arg_judge = args.model1
    is_ollama_model_judge = False
    if model_arg_judge.startswith("ollama "):
        model_name_judge = model_arg_judge[len("ollama "):].strip()
        is_ollama_model_judge = True
    else:
        model_name_judge = model_arg_judge

    # Procesar el modelo para el Detective
    model_arg_detective = args.model2
    is_ollama_model_detective = False
    if model_arg_detective.startswith("ollama "):
        model_name_detective = model_arg_detective[len("ollama "):].strip()
        is_ollama_model_detective = True
    else:
        model_name_detective = model_arg_detective

    judge_ai = JudgeAI(model_name=model_name_judge, is_ollama_model=is_ollama_model_judge)
    detective_ai = DetectiveAI(model_name=model_name_detective, is_ollama_model=is_ollama_model_detective)

    print(f"{Fore.CYAN}IA 1 ({judge_ai.model_name}): {judge_ai.get_initial_story()}{Style.RESET_ALL}")
    pause_for_user()

    game_over = False
    while not game_over:
        detective_move = detective_ai.get_next_move(judge_ai.history)
        print(f"{Fore.MAGENTA}IA 2 ({detective_ai.model_name}): {detective_move}{Style.RESET_ALL}")
        pause_for_user()

        judge_response = judge_ai.respond_to_question(detective_move)
        print(f"{Fore.CYAN}IA 1 ({judge_ai.model_name}): {judge_response}{Style.RESET_ALL}")
        pause_for_user()

        if "SOLUCIÓN:" in detective_move:
            if judge_response == "Es correcto":
                game_over = True
                print(f"{Fore.GREEN}¡La IA Detective ha resuelto el misterio!{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}IA 1 ({judge_ai.model_name}): No es correcto.{Style.RESET_ALL}")
                pause_for_user()
        
        if judge_response == "Es correcto" and "SOLUCIÓN:" not in detective_move:
            # Esto no debería ocurrir si el juez sigue las reglas, pero es una salvaguarda
            game_over = True
            print(f"{Fore.RED}¡La IA Juez ha terminado el juego inesperadamente!{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
