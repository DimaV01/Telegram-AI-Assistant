import json, os, asyncio, sys, g4f, threading, nest_asyncio, curl_cffi
import tkinter as tk
from tkinter import ttk
from telethon import TelegramClient, events, sync

# Путь к файлу для сохранения данных
DATA_FILE = "data.json"

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    return {}

def save_data():
    data = {
        "api_id": api_id_entry.get(),
        "api_hash": api_hash_entry.get(),
        "phone": phone_entry.get(),
        "target_usernames": target_usernames_entry.get("1.0", tk.END).strip().split(','),
        "code": code_entry.get(),
        "model": model_combobox.get(),
        "system_message": system_message_entry.get("1.0", tk.END).strip(),
    }
    with open(DATA_FILE, "w") as file:
        json.dump(data, file)

def send_code():
    global client, loop
    api_id = api_id_entry.get()
    api_hash = api_hash_entry.get()
    phone = phone_entry.get()

    if not api_id or not api_hash or not phone:
        status_label.config(text="Все поля должны быть заполнены!", fg='red')
        return

    if client and client.is_user_authorized():
        username_label.config(text=client.get_me().username)
        status_label.config(text="Вы уже авторизованы.", fg='red')
        return

    try:
        client = TelegramClient('TGAI', api_id, api_hash, system_version='4.16.30-vxCUSTOM')
        client.connect()

        client.send_code_request(phone)
        status_label.config(text="Код отправлен на ваш телефон.", fg='green')
    except ConnectionError:
        status_label.config(text="Невозможно отправлять запросы пока отключено", fg='red')
    except Exception as e:
        status_label.config(text=f"Не удалось войти в систему: {e}", fg='red')

def verify_code():
    global client, loop
    if not client:
        status_label.config(text="Клиент не инициализирован.", fg='red')
        return

    if client.is_user_authorized():
        username_label.config(text=client.get_me().username)
        status_label.config(text="Вы уже авторизованы.", fg='red')
        return

    try:
        code = code_entry.get()
        client.sign_in(phone=phone_entry.get(), code=code)
        username_label.config(text=client.get_me().username)
        status_label.config(text="Успешно вошли в систему!", fg='green')
    except ConnectionError:
        status_label.config(text="Невозможно отправлять запросы пока отключено", fg='red')
    except Exception as e:
        status_label.config(text=f"Не удалось войти в систему: {e}", fg='red')

def toggle_bot():
    global running, loop
    api_id = api_id_entry.get()
    api_hash = api_hash_entry.get()
    phone = phone_entry.get()
    code = code_entry.get()
    target_usernames = target_usernames_entry.get("1.0", tk.END).strip().split(',')
    model = model_combobox.get()
    system_message = system_message_entry.get("1.0", tk.END).strip()

    if not api_id or not api_hash or not phone or not code or not target_usernames or not model or not system_message:
        status_label.config(text="Все поля должны быть заполнены!", fg='red')
        return

    running = not running
    if running:
        start_stop_button.config(text="Stop")
        status_label.config(text="Бот запущен", fg="green")
        threading.Thread(target=lambda: loop.run_until_complete(start_bot(model, system_message))).start()
    else:
        start_stop_button.config(text="Start")
        status_label.config(text="Бот остановлен", fg="green")
        threading.Thread(target=stop_bot).start()

async def start_bot(model, system_message):
    try:
        global client
        if not client.is_connected():
            await client.connect()
        chat_history = [{"role": "system", "content": system_message}]

        target_usernames = target_usernames_entry.get("1.0", tk.END).strip().split(',')

        if not hasattr(client, 'handler_registered'):
            @client.on(events.NewMessage(from_users=target_usernames))
            async def handle_new_message(event):
                user_message = event.message.message

                try:
                    if not hasattr(event, 'handled') or not event.handled:
                        event.handled = True
                        chat_history.append({"role": "user", "content": user_message})

                        response = g4f.ChatCompletion.create(
                            model=getattr(g4f.models, model),
                            messages=chat_history,
                            stream=True
                        )

                        bot_reply = ""
                        
                        for message in response:
                            bot_reply += message
                            
                        chat_history.append({"role": "assistant", "content": bot_reply})
                        
                        if reply_with_signature.get():
                            await client.send_message(event.sender_id, f"(This reply was generated by {model})\n\n"+bot_reply)
                        else:
                            await client.send_message(event.sender_id, bot_reply)
                            
                        print(chat_history)
                        print(model)
                except Exception as e:
                    await client.send_message(event.sender_id, "Извините, в данный момент помощник не работает")
                    print(e)
                    print(chat_history)

            client.add_event_handler(handle_new_message, events.NewMessage(from_users=target_usernames))
            client.handler_registered = True
        
        await client.run_until_disconnected()
    except Exception as e:
        status_label.config(text=f"Не удалось запустить бота: {e}", fg='red')
    finally:
        chat_history = chat_history[:1]
        print(chat_history)

def stop_bot():
    global running
    if client:
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(client.disconnect()))
    running = False

def log_out():
    try:    
        if os.path.exists('TGAI.session'):
            os.remove('TGAI.session')
        api_id_entry.delete(0, tk.END)
        api_hash_entry.delete(0, tk.END)
        phone_entry.delete(0, tk.END)
        code_entry.delete(0, tk.END)
        status_label.config(text="Вы вышли из системы.", fg='green')
        username_label.config(text="")
    except Exception as e:
        status_label.config(text=f"Завершите работу бота: {e}", fg='red')

def on_closing():
    if os.path.exists('TGAI.session-journal'):
        stop_bot()
    save_data()
    root.destroy()

# Инициализация состояния
running = False
client = None
loop = asyncio.get_event_loop()

# Создание главного окна
root = tk.Tk()
root.title("Telegram AI Assistant")
root.iconbitmap('icon.ico')

# Загрузка сохраненных данных
data = load_data()

tk.Label(root, text="Username:").grid(row=0, column=0, padx=10, pady=5)
username_label = tk.Label(root, text="")
username_label.grid(row=0, column=1, padx=10, pady=5)

tk.Label(root, text="API ID:").grid(row=1, column=0, padx=10, pady=5)
api_id_entry = tk.Entry(root, width=30)
api_id_entry.grid(row=1, column=1, padx=10, pady=5)
api_id_entry.insert(0, data.get("api_id", ""))

tk.Label(root, text="API Hash:").grid(row=2, column=0, padx=10, pady=5)
api_hash_entry = tk.Entry(root, width=30)
api_hash_entry.grid(row=2, column=1, padx=10, pady=5)
api_hash_entry.insert(0, data.get("api_hash", ""))

tk.Label(root, text="Phone Number:").grid(row=3, column=0, padx=10, pady=5)
phone_entry = tk.Entry(root, width=30)
phone_entry.grid(row=3, column=1, padx=10, pady=5)
phone_entry.insert(0, data.get("phone", ""))

send_code_button = tk.Button(root, text="Send Code", command=send_code)
send_code_button.grid(row=3, column=2, padx=10, pady=5)

tk.Label(root, text="Telegram Code:").grid(row=4, column=0, padx=10, pady=5)
code_entry = tk.Entry(root, width=30)
code_entry.grid(row=4, column=1, padx=10, pady=5)
code_entry.insert(0, data.get("code", ""))

verify_code_button = tk.Button(root, text="Verify Code", command=verify_code)
verify_code_button.grid(row=4, column=2, padx=10, pady=5)

tk.Label(root, text="Target Usernames (comma separated):").grid(row=6, column=0, padx=10, pady=5)
target_usernames_entry = tk.Text(root, height=5, width=30)
target_usernames_entry.grid(row=6, column=1, padx=10, pady=5)
target_usernames_entry.insert(tk.END, ",".join(data.get("target_usernames", [])))

tk.Label(root, text="Model:").grid(row=7, column=0, padx=10, pady=5)
model_combobox = ttk.Combobox(root, values=[
    'gpt_35_turbo',
    'gpt_35_turbo_0613',
    'gpt_35_turbo_16k',
    'gpt_35_turbo_16k_0613',
    'gpt_4',
    'gpt_4_0613',
    'gpt_4_32k',
    'gpt_4_32k_0613',
    'gpt_4_turbo',
    'gpt_4o',
    'gpt_4o_mini',
    'claude_3_haiku',
    'claude_3_opus',
    'claude_3_sonnet',
    'claude_v2',
    'huggingchat',
    'huggingface',
    'meta',
    'llama_2_70b_chat',
    'llama3_70b_instruct',
    'llama3_8b_instruct',
    'nous_hermes_2_mixtral_8x7b_dpo',
    'pizzagpt',
    'blackbox',
    'gemini',
    'gemini_pro',
    'gemma_2_27b_it',
    'gemma_2_9b_it',
    'deepinfra',
    'openai_chat',
    'phi_3_mini_4k_instruct',
    'pi',
    'reka'
], width=30)
model_combobox.grid(row=7, column=1, padx=10, pady=5)
model_combobox.set(data.get("model", ""))

tk.Label(root, text="System Message:").grid(row=8, column=0, padx=10, pady=5)
system_message_entry = tk.Text(root, height=5, width=30)
system_message_entry.grid(row=8, column=1, padx=10, pady=5)
system_message_entry.insert(tk.END, data.get("system_message", ""))

reply_with_signature = tk.BooleanVar(value=True)
signature_checkbox = tk.Checkbutton(root, text="Sign AI Replies", variable=reply_with_signature)
signature_checkbox.grid(row=9, column=0, padx=10, pady=5)

start_stop_button = tk.Button(root, text="Start", command=toggle_bot)
start_stop_button.grid(row=10, column=0, columnspan=2, pady=10)

log_out_button = tk.Button(root, text="Log Out", command=log_out)
log_out_button.grid(row=10, column=2, padx=10, pady=10)

status_label = tk.Label(root, text="В любой непонятной ситуации перезаходите в приложение", fg="black")
status_label.grid(row=11, columnspan=3, pady=10)

root.protocol("WM_DELETE_WINDOW", on_closing)

if os.path.exists('TGAI.session'):
    try:
        client = TelegramClient('TGAI', data.get("api_id", ""), data.get("api_hash", ""), system_version='4.16.30-vxCUSTOM')
        client.connect()
        if client.is_user_authorized():
            username_label.config(text=client.get_me().username)
        else:
            client = None
    except Exception as e:
        status_label.config(text=f"Ошибка при восстановлении сессии: {e}", fg='red') 

root.mainloop()
