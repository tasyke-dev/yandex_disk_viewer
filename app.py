from flask import Flask, render_template, request, redirect, url_for, send_file, Response
import requests
from io import BytesIO
from zipfile import ZipFile
import os
from functools import lru_cache

app = Flask(__name__)

YANDEX_API_BASE_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"

@lru_cache(maxsize=128)
def get_files_from_yandex(public_key):
    params = {"public_key": public_key}
    response = requests.get(YANDEX_API_BASE_URL, params=params)
    
    if response.status_code == 200:
        data = response.json()
        return data.get("_embedded", {}).get("items", [])
    return []

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
    file_type = request.args.get("file_type")

    if not public_key:
        return redirect(url_for("index"))

    items = get_files_from_yandex(public_key)

    if not items:
        return render_template("files.html", error="Не удалось получить данные с Яндекс.Диска")

    if file_type:
        items = [item for item in items if item.get("mime_type", "").startswith(file_type)]

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

@app.route("/download_all", methods=["POST"])
def download_all():
    public_key = request.form.get("public_key")
    selected_files = request.form.getlist("selected_files")

    if not public_key or not selected_files:
        return "Неверный запрос", 400

    zip_filename = "downloaded_files.zip"
    with ZipFile(zip_filename, "w") as zipf:
        for file_path in selected_files:
            download_link = get_download_link(public_key, file_path)
            if download_link:
                response = requests.get(download_link)
                if response.status_code == 200:
                    file_name = file_path.split("/")[-1]
                    zipf.writestr(file_name, response.content)

    with open(zip_filename, "rb") as f:
        file_data = f.read()
    os.remove(zip_filename)
    return Response(
        file_data,
        headers={
            "Content-Disposition": f"attachment; filename={zip_filename}",
            "Content-Type": "application/zip",
        },
    )

if __name__ == "__main__":
    app.run(debug=True)
