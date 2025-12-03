import speech_recognition as sr
import threading
import time
import requests
import queue

class VoiceProcessor:
    def __init__(self):
        self.commands = {
            "избушка реакция": self.random_expression,
            "избушка радость": lambda: self.set_expression("happy"),
            "избушка злость": lambda: self.set_expression("angry"),
            "избушка удивление": lambda: self.set_expression("surprised"),
            "избушка грусть": lambda: self.set_expression("sad"),
            "избушка смех": lambda: self.set_expression("laughing"),
            "избушка подмигни": lambda: self.set_expression("winking"),
            "избушка сон": lambda: self.set_expression("sleepy"),
            "избушка нейтрально": lambda: self.set_expression("neutral"),
            "избушка крути": self.start_casino,
            "избушка рычаг": self.pull_lever,
            "избушка отмена": self.exit_casino
        }

        self.recognizer = sr.Recognizer()

        self.microphone = sr.Microphone(
            # device_index=0
            sample_rate=48000,
            chunk_size=2048
        )

        self.command_queue = queue.Queue()
        self.setup_microphone()

    def setup_microphone(self):
        with self.microphone as source:
            print("Калибрую микрофон...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print("Готов к распознаванию")

    def random_expression(self):
        from reaction import get_random_expression
        expression = get_random_expression()
        try:
            requests.post("http://127.0.0.1:8000/change-expression",
                          json={"expression": expression})
            print(f"Выражение изменено: {expression}")
        except Exception as e:
            print(f"Ошибка: {e}")

    def set_expression(self, expression_name):
        try:
            requests.post("http://127.0.0.1:8000/change-expression",
                          json={"expression": expression_name})
            print(f"Выражение изменено: {expression_name}")
        except Exception as e:
            print(f"Ошибка: {e}")

    def start_casino(self):
        import webbrowser
        webbrowser.open("http://127.0.0.1:8000/casino")

    def pull_lever(self):
        try:
            requests.post("http://127.0.0.1:8000/casino/spin")
            print("Рычаг дернут")
        except Exception as e:
            print(f"Ошибка: {e}")

    def exit_casino(self):
        self.set_expression("neutral")

    def process_commands(self):
        while True:
            command = self.command_queue.get()
            if command is None:
                break
            command()
            time.sleep(1)

    def listen(self):
        def callback(recognizer, audio):
            try:
                text = recognizer.recognize_google(audio, language="ru-RU").lower()
                print("Распознано:", text)
                for cmd, func in self.commands.items():
                    if cmd in text:
                        print("Выполняю команду:", cmd)
                        self.command_queue.put(func)
            except:
                pass

        self.recognizer.listen_in_background(self.microphone, callback)
        t = threading.Thread(target=self.process_commands)
        t.daemon = True
        t.start()