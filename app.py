from flask import Flask, render_template, request, redirect, url_for
import requests

app = Flask(__name__)

YANDEX_API_BASE_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        public_key = request.form.get("public_key")
        if public_key:
            return redirect(url_for("view_files", public_key=public_key))
    return render_template("index.html")

@app.route("/files")
def view_files():
    public_key = request.args.get("public_key")
    if not public_key:
        return redirect(url_for("index"))

    # Запрос к API Яндекс.Диска
    params = {"public_key": public_key}
    response = requests.get(YANDEX_API_BASE_URL, params=params)
    if response.status_code != 200:
        return render_template("files.html", error="Не удалось получить данные с Яндекс.Диска")

    data = response.json()
    items = data.get("_embedded", {}).get("items", [])
    return render_template("files.html", items=items, public_key=public_key)
