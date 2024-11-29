from flask import Flask, render_template

app = Flask(__name__)

# Ruta principal
@app.route('/')
def home():
    return "¡Bienvenido a la aplicación de Tickets!"

if __name__ == '__main__':
    app.run(debug=True)
