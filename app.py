from flask import Flask, render_template, request, redirect, url_for, send_file
import requests
from io import BytesIO

app = Flask(__name__)

YANDEX_API_BASE_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"

def get_download_link(public_key, file_path):
    params = {"public_key": public_key, "path": file_path}
    response = requests.get(f"{YANDEX_API_BASE_URL}/download", params=params)
    if response.status_code == 200:
        return response.json().get("href")
    return None

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

@app.route("/download")
def download_file():
    public_key = request.args.get("public_key")
    file_path = request.args.get("file_path")

    if not public_key or not file_path:
        return "Неверный запрос", 400

    download_link = get_download_link(public_key, file_path)
    if not download_link:
        return "Не удалось получить ссылку на скачивание", 400

    response = requests.get(download_link)
    if response.status_code == 200:
        file_data = BytesIO(response.content)
        file_name = file_path.split("/")[-1]
        return send_file(file_data, as_attachment=True, download_name=file_name)

    return "Ошибка при загрузке файла", 400