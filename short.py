import qrcode
import random
import json
import re
import logging

from io import BytesIO
from urllib.parse import urlparse
from flask import Flask, request, redirect, render_template, send_file
from db import DBError, mysql_db

class tools():
    characters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

    def __init__(self, config: dict, logger=None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.db = mysql_db(config, self.logger)
    
    def _generate_short_code(self, length):
        """Генерация случайного короткого кода"""
        return ''.join(random.choice(self.characters) for _ in range(length))
    
    def _validate_custom_code(self, code):
        """Проверка пользовательского кода"""
        if not code:
            return False, "Код не может быть пустым"
        
        if len(code) < 3 or len(code) > 20:
            return False, "Длина кода должна быть от 3 до 20 символов"
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', code):
            return False, "Код может содержать только буквы, цифры, дефис и подчеркивание"
        
        return True, None
    
    def _code_exists(self, code):
        """Проверка существования кода в базе"""
        rows = self.db.fetch_all("check_code_exists", code)
        return bool(rows and rows[0]["count"] > 0)

    def _get_first(self, query_name, *args):
        rows = self.db.fetch_all(query_name, *args)
        return rows[0] if rows else None

    def get_link(self, short_code):
        """Получение информации о ссылке по коду"""
        link = self._get_first("select_link_by_code", short_code)
        
        if not link:
            return None
        
        if link['is_multi']:
            items = self.db.fetch_all("select_link_items", link['id'])
            
            return {
                "id": link['id'],
                "short_code": link['short_code'],
                "multi": True,
                "items": items,
                "click_count": link['click_count']
            }
        
        return {
            "id": link['id'],
            "short_code": link['short_code'],
            "multi": False,
            "original_url": link['original_url'],
            "click_count": link['click_count']
        }

    def add_click(self, link_id):
        """Увеличение счетчика переходов"""
        try:
            return bool(self.db.execute_write("update_click_count", link_id, return_id=False))
        except DBError:
            return False
    
    def create_short_link(self, url, custom_code=None, length=5):
        """Создание обычной короткой ссылки"""
        try:
            # Проверка на ссылку на собственный домен
            try:
                if url.rsplit("/")[2] == request.host:
                    return f'Сокращение ссылок ведущих на "{request.host}" запрещено.', 400
            except:
                return "Некорректный URL", 400
            
            existing_link = self._get_first("select_link_by_url", url)
            
            if existing_link:
                short_url = ''.join((request.url_root, existing_link['short_code']))
                return short_url, 200
            
            # Генерируем или проверяем пользовательский код
            if custom_code:
                valid, error = self._validate_custom_code(custom_code)
                if not valid:
                    return error, 400
                
                if self._code_exists(custom_code):
                    return f'Код "{custom_code}" уже используется. Выберите другой.', 400
                
                short_code = custom_code
            else:
                # Генерируем случайный код
                for _ in range(10):
                    short_code = self._generate_short_code(length)
                    if not self._code_exists(short_code):
                        break
                else:
                    return f'После 10 попыток генерации уникального кода не удалось. Попробуйте другую длину.', 500
            
            self.db.execute_write("insert_simple_link", short_code, url, return_id=False)
            
            short_url = ''.join((request.url_root, short_code))
            return short_url, 200
        except DBError:
            return "Ошибка обращения к базе данных", 500

    def create_multi_link(self, urls, descriptions, custom_code=None, length=5):
        """Создание мульти-ссылки"""
        link_id = None
        try:
            if len(urls) > 40:
                return f'Максимальное количество ссылок в одной мульти ссылке 40, а вы попытались создать {len(urls)}.', 400
            
            if len(urls) < 2:
                return 'Для мульти-ссылки нужно минимум 2 URL', 400
            
            # Генерируем или проверяем пользовательский код
            if custom_code:
                valid, error = self._validate_custom_code(custom_code)
                if not valid:
                    return error, 400
                
                if self._code_exists(custom_code):
                    return f'Код "{custom_code}" уже используется. Выберите другой.', 400
                
                short_code = custom_code
            else:
                # Генерируем случайный код
                for _ in range(10):
                    short_code = self._generate_short_code(length)
                    if not self._code_exists(short_code):
                        break
                else:
                    return f'После 10 попыток генерации уникального кода не удалось. Попробуйте другую длину.', 500
            
            link_id = self.db.execute_write("insert_multi_link", short_code)
            
            for position, (url, description) in enumerate(zip(urls, descriptions)):
                self.db.execute_write("insert_link_item", link_id, url, description, position, return_id=False)
            
            short_url = ''.join((request.url_root, short_code))
            return short_url, 200
        except DBError:
            if link_id:
                try:
                    self.db.execute_write("delete_link_by_id", link_id, return_id=False)
                except DBError:
                    pass
            return "Ошибка обращения к базе данных", 500


class shoter:
    def __init__(self, name):
        self.app = Flask(name)

        try:
            with open("config.json") as file:
                config = json.load(file)
            
            self.tools = tools(config, self.app.logger)
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
            print("Создайте файл config.json со следующей структурой:")
            print(json.dumps({
                "db_config": {
                    "MYSQL_HOST": "localhost",
                    "MYSQL_USER": "user",
                    "MYSQL_PASSWORD": "password",
                    "MYSQL_DB": "database"
                },
                "SQL_QUERIES_FILE": "sql_queries.json",
                "SQL_CREATE_FILE": "db_init.sql",
                "CONFIG_FILE": "config.json",
                "MYSQL_RETRY_COUNT": 4,
                "MYSQL_RETRY_DELAY": 0.5,
                "sql_install": False
            }, indent=2))
            raise

        self.setup_routes()
    
    def crop_url(self, url, url_len = 25):
        parsed_url = urlparse(url)
        crop = parsed_url.netloc + parsed_url.path
        return crop[:url_len] + "..." if len(crop) > url_len else crop
    
    def setup_routes(self):
        # Если будет не найденный файл
        @self.app.errorhandler(404)
        def not_found(ex):
            return render_template('error.html', message=ex, home_url=request.host_url), 404

        # Оповещение о прочих ошибках сервера
        @self.app.errorhandler(Exception)
        def handle_exception(ex):    
            return render_template('error.html', message=ex, home_url=request.host_url), 500

        # Функция для генерации QR-кода
        @self.app.route('/make_qr')
        def generate_qr_code():
            data = request.args.get('url')
            color = request.args.get('color')

            if not color:
                color = "black"
                
            if not data:
                return 'Отсутствует аргумент', 400    

            # Создание QR-кода
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)

            # Генерация изображения QR-кода
            img = qr.make_image(fill_color=color, back_color="white")

            # Создание объекта BytesIO для временного хранения изображения в памяти
            image_io = BytesIO()

            # Сохранение изображения в объект BytesIO
            img.save(image_io)

            # Перемещение указателя объекта BytesIO в начало
            image_io.seek(0)

            return send_file(image_io, mimetype='image/png')

        # Главная страница
        @self.app.route('/', methods=['GET'])
        def home():
            return render_template('index.html', home_url = request.url_root)

        # Результат сокращения ссылки
        @self.app.route('/', methods=['POST'])
        def shorten_link():
            try:
                original_url = request.form['url']
                custom_code = request.form.get('custom_code', '').strip()
                size = request.form.get('size', '5')
            except:
                return render_template('error.html', message='Отсутствует аргумент', home_url=request.host_url), 400
            
            # Если указан пользовательский код, используем его
            if custom_code:
                new_url = self.tools.create_short_link(original_url, custom_code=custom_code)
            else:
                try:
                    size = int(size)
                    if size > 5 or size < 3:
                        return render_template('error.html', message=f'Минимальная длина ссылки 3, а максимальная 5, вами была указана {size}.', home_url=request.host_url), 400
                except Exception as ex:
                    return render_template('error.html', message=ex, home_url=request.host_url), 400
                
                new_url = self.tools.create_short_link(original_url, length=size)
            
            if not new_url[1] == 200:
                return render_template('error.html', message=new_url[0], home_url=request.host_url), new_url[1]
            
            return redirect("".join((new_url[0], "+info")))

        @self.app.route('/create_multi', methods=['GET'])
        def create_multi_index():
            return render_template('create_multi.html', home_url = request.url_root)

        @self.app.route('/create_multi', methods=['POST'])
        def create_multi():
            try:
                urls = request.form.getlist('url')
                descriptions = request.form.getlist('description')
                custom_code = request.form.get('custom_code', '').strip()
                size = request.form.get('size', '5')
            except:
                return render_template('error.html', message='Отсутствует аргумент', home_url=request.host_url), 400

            if len(urls) < 2:
                return render_template('error.html', message='Невозможно создать мульти-ссылку, если количество ссылок меньше двух', home_url=request.host_url), 400
            
            elif len(urls) != len(descriptions):
                return render_template('error.html', message="Количество ссылок и описаний не совпадает", home_url=request.host_url), 400
            
            # Если указан пользовательский код, используем его
            if custom_code:
                new_url = self.tools.create_multi_link(urls, descriptions, custom_code=custom_code)
            else:
                try:
                    size = int(size)
                    if size > 5 or size < 3:
                        return render_template('error.html', message=f'Минимальная длина ссылки 3, а максимальная 5, вами была указана {size}.', home_url=request.host_url), 400
                except Exception as ex:
                    return render_template('error.html', message=ex, home_url=request.host_url), 400
                
                new_url = self.tools.create_multi_link(urls, descriptions, length=size)
            
            if not new_url[1] == 200:
                return render_template('error.html', message=new_url[0], home_url=request.host_url), new_url[1]
            
            return redirect(new_url[0])
    
        # Переадресация по сокращённому коду
        @self.app.route('/<short_code>+<action>')
        def show_stat(short_code: str, action: str):
            def show_info(link_info: dict):
                return render_template(
                    'result.html', 
                    count=link_info["click_count"], 
                    short_code=short_code,
                    home_url=request.url_root,
                    original_url=link_info["original_url"],
                    short_url="".join((request.url_root, short_code)),
                    original_url_favicon="".join(("https://", link_info["original_url"].rsplit("/")[2], "/favicon.ico"))
                ) 

            actions = {
                "info": "show_info(link)"
            }

            if action in actions.keys():
                if len(short_code) > 20:
                    return render_template('error.html', message="Длина кода сокращённой ссылки не может превышать 20 символов.", home_url=request.url_root), 400
            
                link = self.tools.get_link(short_code)
                
                if not link:
                    return render_template('error.html', message="Ссылка не найдена", home_url=request.url_root), 404
                
                if link["multi"]:
                    return render_template('error.html', message="Мульти-ссылки не поддерживают действия.", home_url=request.url_root), 400
                
                return eval(actions[action])
            else:
                return render_template('error.html', message="Неизвестное действие.", home_url=request.url_root), 400

        # Переадресация по сокращённому коду
        @self.app.route('/<short_code>')
        def redirect_to_original_url(short_code: str):
            if len(short_code) > 20:
                return render_template('error.html', message="Длина кода сокращённой ссылки не может превышать 20 символов.", home_url=request.url_root), 400
            
            link = self.tools.get_link(short_code)

            if not link:
                return render_template('no.html', short_code=short_code, home_url=request.host_url), 404

            if link["multi"]:
                return render_template(
                    'result_multi.html',
                    results=link["items"],
                    short_url="".join((request.url_root, short_code)), 
                    home_url=request.url_root,
                    len=len,
                    short_code=short_code,
                    crop = self.crop_url
                )

            self.tools.add_click(link["id"])
            return redirect(link["original_url"])

shoter_app = shoter(__name__)
app = shoter_app.app

if __name__ == '__main__':
    app.run(debug=True)
