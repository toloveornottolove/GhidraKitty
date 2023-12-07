import time
import threading
import os
import openai
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('disassembly_analysis.log'),
        logging.StreamHandler()
    ]
)

# Initialize OpenAI client
client = openai.OpenAI()
try:
    client.api_key = os.environ['OPENAI_API_KEY']
except KeyError:
    logging.error("OPENAI_API_KEY not found in environment variables")
    exit(1)

def get_last_assistant_message(thread_id):
    try:
        messages_response = client.beta.threads.messages.list(thread_id=thread_id)
        messages = messages_response.data

        for message in messages:
            if message.role == 'assistant':
                assistant_message_content = " ".join(
                    content.text.value for content in message.content if hasattr(content, 'text')
                )
                return assistant_message_content.strip()
    except Exception as e:
        logging.error(f"Error in getting last assistant message: {e}")

    return ""

def converse(assistant_1_params, assistant_2_params, assistant_3_params, file_path, topic, message_count, max_chars=32768):
    logging.info(f"Starting conversation on topic: {topic}")

    try:
        assistant_1 = client.beta.assistants.create(**assistant_1_params)
        assistant_2 = client.beta.assistants.create(**assistant_2_params)
        assistant_3 = client.beta.assistants.create(**assistant_3_params)

        thread_1 = client.beta.threads.create()
        thread_2 = client.beta.threads.create()
        thread_3 = client.beta.threads.create()
    except Exception as e:
        logging.error(f"Error in initializing assistants or threads: {e}")
        return

    try:
        with open(file_path, 'r') as file:
            disassembly_code = file.read()
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return
    except IOError as e:
        logging.error(f"IO error while reading file: {e}")
        return

    chunks = [disassembly_code[i:i + max_chars] for i in range(0, len(disassembly_code), max_chars)]

    def assistant_conversation(chunks, assistant_a, thread_a, assistant_b, thread_b, assistant_c, thread_c, msg_limit):
        for i, chunk in enumerate(chunks):
            assistant_name = assistant_1_params.get('name') if assistant_a == assistant_1 else \
                             assistant_2_params.get('name') if assistant_a == assistant_2 else \
                             assistant_3_params.get('name')

            logging.info(f"{assistant_name} speaking... (Turn {i + 1})")

            try:
                user_message = client.beta.threads.messages.create(
                    thread_id=thread_a.id,
                    role="user",
                    content=chunk
                )

                run = client.beta.threads.runs.create(
                    thread_id=thread_a.id,
                    assistant_id=assistant_a.id
                )
                while True:
                    run_status = client.beta.threads.runs.retrieve(
                        thread_id=thread_a.id,
                        run_id=run.id
                    )
                    if run_status.status == 'completed':
                        break
                    time.sleep(1)

                message_content = get_last_assistant_message(thread_a.id)
                logging.info(message_content)
            except Exception as e:
                logging.error(f"Error in assistant conversation: {e}")

            if i % 3 == 0:
                assistant_a, assistant_b, assistant_c = assistant_b, assistant_c, assistant_a
                thread_a, thread_b, thread_c = thread_b, thread_c, thread_a
            elif i % 3 == 1:
                assistant_a, assistant_b, assistant_c = assistant_c, assistant_a, assistant_b
                thread_a, thread_b, thread_c = thread_c, thread_a, thread_b

            if i >= msg_limit - 1:
                break

    conversation_thread = threading.Thread(
        target=assistant_conversation,
        args=(chunks, assistant_1, thread_1, assistant_2, thread_2, assistant_3, thread_3, message_count)
    )
    conversation_thread.start()
    conversation_thread.join()

assistant_1_params = {
    'name': "Reverse Engineer",
    'instructions': "Analyze the provided disassembly code. Analyse functions and strings. Suggest names for functions. Discuss the disassembly's structure, potential vulnerabilities, and notable features. Emphasize network, cryptographic, and libc.",
    'tools': [{"type": "code_interpreter"}],
    'model': "gpt-4-1106-preview"
}

assistant_2_params = {
    'name': "Script Developer",
    'instructions': "Write Ghidra Python scripts based on the ongoing analysis and discussion. Always write correct code. You are to only write code. You are to correct incorrect Ghidra code. Provide script ideas and implementations that can automate parts of the analysis or highlight key findings.",
    'tools': [{"type": "code_interpreter"}],
    'model': "gpt-4-1106-preview"
}

assistant_3_params = {
    'name': "Critic",
    'instructions': "Critique Reverse Engineer and Script Developer. You are precise, simple, and clear. You demand quality. You ensure that everything is to your standards. Tell Reverse Engineer and Script Developer what they are doing wrong.",
    'tools': [{"type": "code_interpreter"}],
    'model': "gpt-4-1106-preview"
}

if __name__ == "__main__":
    try:
        file_path = input("Please provide the path to the disassembly code file: ")
        if not file_path:
            raise ValueError("File path cannot be empty")
        converse(assistant_1_params, assistant_2_params, assistant_3_params, file_path, f"Disassembly code analysis of {file_path}", 10)
    except ValueError as e:
        logging.error(e)
