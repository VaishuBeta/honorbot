from flask import Flask
from threading import Thread
from main import start_bot  # Import start_bot function from main.py

app = Flask(__name__)

# Start the Discord bot in a background thread when app.py starts
Thread(target=start_bot).start()

@app.route('/')
def home():
    return "Flask + Discord bot is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
