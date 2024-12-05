from flask import Flask, render_template, request, redirect, url_for, send_file
import requests
from io import BytesIO
from zipfile import ZipFile
import os
from functools import lru_cache
from typing import List, Optional, Dict, Any

app = Flask(__name__)

YANDEX_API_BASE_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"


@lru_cache(maxsize=128)
def get_files_from_yandex(public_key: str, folder_path: str = "") -> List[Dict[str, Any]]:
    """
    Получает список файлов и папок из публичного ресурса Яндекс.Диска.

    :param public_key: публичный ключ для доступа к ресурсу
    :param folder_path: путь к папке на Яндекс.Диске (по умолчанию пусто)
    :return: список файлов и папок
    """
    params = {"public_key": public_key, "path": folder_path}
    response = requests.get(YANDEX_API_BASE_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        return data.get("_embedded", {}).get("items", [])
    return []


def get_download_link(public_key: str, file_path: str) -> Optional[str]:
    """
    Получает ссылку для скачивания файла с Яндекс.Диска.

    :param public_key: публичный ключ для доступа к ресурсу
    :param file_path: путь к файлу на Яндекс.Диске
    :return: ссылка для скачивания файла или None, если ссылка не найдена
    """
    params = {"public_key": public_key, "path": file_path}
    response = requests.get(f"{YANDEX_API_BASE_URL}/download", params=params)
    if response.status_code == 200:
        return response.json().get("href")
    return None


@app.route("/", methods=["GET", "POST"])
def index() -> Any:
    """
    Главная страница приложения. Обрабатывает форму для ввода публичного ключа.

    :return: шаблон главной страницы
    """
    if request.method == "POST":
        public_key = request.form.get("public_key")
        if public_key:
            return redirect(url_for("view_files", public_key=public_key, folder_path=""))
    return render_template("index.html")


@app.route("/files")
def view_files() -> Any:
    """
    Страница для отображения файлов и папок с Яндекс.Диска.

    :return: шаблон страницы с файлами или ошибкой
    """
    public_key = request.args.get("public_key")
    folder_path = request.args.get("folder_path", "")
    file_type = request.args.get("file_type", "")

    if not public_key:
        return redirect(url_for("index"))

    params = {"public_key": public_key, "path": folder_path}
    response = requests.get(YANDEX_API_BASE_URL, params=params)
    if response.status_code != 200:
        return render_template("files.html", error="Не удалось получить данные с Яндекс.Диска")

    data = response.json()
    items = data.get("_embedded", {}).get("items", [])

    if not items:
        return render_template("files.html", public_key=public_key, error="Папка пуста или данные отсутствуют")

    if file_type:
        items = [
            item for item in items
            if (
                (file_type == "directory" and item["type"] == "dir") or
                ("media_type" in item and item["media_type"].startswith(file_type)) or
                (
                    file_type == "image/" and item["name"].lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.jfif')) or
                    file_type == "application/" and item["name"].lower().endswith(('.pdf', '.docx', '.pptx', '.txt', '.xlsx')) or
                    file_type == "video/" and item["name"].lower().endswith(('.mp4', '.mkv', '.avi'))
                )
            )
        ]

    return render_template("files.html", items=items, public_key=public_key, folder_path=folder_path, file_type=file_type)


@app.route("/download")
def download_file() -> Any:
    """
    Обрабатывает запрос на скачивание файла с Яндекс.Диска.

    :return: файл для скачивания или ошибка
    """
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
        file_name = os.path.basename(file_path)
        return send_file(file_data, as_attachment=True, download_name=file_name)

    return "Ошибка при загрузке файла", 400


def add_to_zip(zipf: ZipFile, public_key: str, file_path: str, folder_name: str = "") -> None:
    """
    Добавляет файлы и папки из Яндекс.Диска в ZIP-архив.

    :param zipf: объект ZipFile для записи
    :param public_key: публичный ключ для доступа к ресурсу
    :param file_path: путь к файлу или папке на Яндекс.Диске
    :param folder_name: имя папки в архиве (по умолчанию пусто)
    """
    items = get_files_from_yandex(public_key, file_path)

    for item in items:
        if item["type"] == "file":
            download_link = get_download_link(public_key, item["path"])
            if download_link:
                response = requests.get(download_link)
                if response.status_code == 200:
                    file_name = os.path.join(folder_name, item["name"])
                    zipf.writestr(file_name, response.content)
        
        elif item["type"] == "dir":
            new_folder = os.path.join(folder_name, item["name"])
            add_to_zip(zipf, public_key, item["path"], new_folder)


@app.route("/download_all", methods=["POST"])
def download_all() -> Any:
    """
    Обрабатывает запрос на скачивание нескольких файлов в виде ZIP-архива.

    :return: ZIP-архив с выбранными файлами
    """
    public_key = request.form.get("public_key")
    selected_files = request.form.getlist("selected_files")

    if not public_key or not selected_files:
        return "Неверный запрос", 400

    zip_filename = "downloaded_files.zip"
    memory_file = BytesIO()

    with ZipFile(memory_file, "w") as zipf:
        for file_path in selected_files:
            if file_path.endswith("/"):
                add_to_zip(zipf, public_key, file_path, os.path.basename(file_path.rstrip("/")))
            else:
                download_link = get_download_link(public_key, file_path)
                if download_link:
                    response = requests.get(download_link)
                    if response.status_code == 200:
                        file_name = os.path.basename(file_path)
                        zipf.writestr(file_name, response.content)

    memory_file.seek(0)

    return send_file(
        memory_file,
        as_attachment=True,
        download_name=zip_filename,
        mimetype="application/zip",
    )


if __name__ == "__main__":
    app.run(debug=True)
