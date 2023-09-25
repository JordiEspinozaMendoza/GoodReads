from functools import cached_property
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlparse
from utils import CustomHTMLParser, get_formatted_book
import re
import os
import redis
import uuid
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

mapping = [
    (r"^/api/books/search", "get_api_search"),
    (r"^/api/books/suggestion", "get_book_suggestion"),
    (r"^/api/books$", "get_books"),
    (r"^/books/(?P<book_file>.+)$", "get_book"),
    (r"^/$", "get_index"),
    (r"^/index$", "get_index"),
    (r"^/search$", "get_search"),
]


class WebRequestHandler(BaseHTTPRequestHandler):
    @cached_property
    def cookies(self):
        return SimpleCookie(self.headers.get("Cookie"))

    def set_book_cookie(self, session_id, max_age=100):
        c = SimpleCookie()
        c["session"] = session_id
        c["session"]["max-age"] = max_age
        self.send_header("Set-Cookie", c.output(header=""))

    def get_book_session(self):
        c = self.cookies
        if not c or not c.get("session"):
            print("No cookie")
            c = SimpleCookie()
            c["session"] = uuid.uuid4()
        else:
            print("Cookie found")
        return c.get("session").value

    def get_book_suggestion(self):
        session_id = self.get_book_session()
        r = redis.StrictRedis(
            host=os.getenv("REDIS_HOST"),
            port=6379,
            db=0,
            charset="utf-8",
            decode_responses=True,
        )

        books = r.keys("book*")
        books_read = r.lrange(session_id, 0, -1)
        suggestions = []
        read_again = []

        for book in books:
            if book not in books_read:
                suggestion_title = CustomHTMLParser(("h2"), ("title"))
                suggestion_title.feed(r.get(book))
                if suggestion_title.data:
                    suggestions.append(
                        {"title": suggestion_title.data[0], "url": f"/books/{book}"}
                    )
                continue

            read_again_title = CustomHTMLParser(("h2"), ("title"))
            read_again_title.feed(r.get(book))
            if read_again_title.data:
                read_again.append(
                    {"title": read_again_title.data[0], "url": f"/books/{book}"}
                )

        json_data = json.dumps({"suggestions": suggestions, "read_again": read_again})

        self.send_response(200)
        self.end_headers()
        self.wfile.write(json_data.encode("utf-8"))

    def get_book(self, book_file):
        self.url = urlparse(self.path)
        r = redis.StrictRedis(
            host=os.getenv("REDIS_HOST"),
            port=6379,
            db=0,
            charset="utf-8",
            decode_responses=True,
        )

        session_id = self.get_book_session()
        books_read = r.lrange(session_id, 0, -1)

        # Get data from redis
        book = r.get(book_file)

        if f"book{book_file}" not in books_read:
            r.rpush(session_id, book_file)

        # Close redis connection
        r.connection_pool.disconnect()

        # Set response
        self.set_book_cookie(session_id)
        self.send_response(200)
        # Write headers
        self.wfile.write(book.encode("utf-8"))

    def get_books(self):
        r = redis.StrictRedis(
            host=os.getenv("REDIS_HOST"),
            port=6379,
            db=0,
            charset="utf-8",
            decode_responses=True,
        )

        books = r.keys("book*")
        response = []

        for book in books:
            book_content = r.get(book)
            response.append(get_formatted_book(book_content, book))

        r.connection_pool.disconnect()
        json_data = json.dumps({"books": response})

        self.send_response(200)
        self.end_headers()
        self.wfile.write(json_data.encode("utf-8"))

    def get_by_file_name(self, file_name):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        session_id = self.get_book_session()
        self.set_book_cookie(session_id)
        self.end_headers()

        with open(file_name, "r") as f:
            response = f.read()
        return self.wfile.write(response.encode("utf-8"))

    def get_index(self):
        self.get_by_file_name("html/index.html")

    def get_search(self):
        self.get_by_file_name("html/search.html")

    def get_api_search(self):
        try:
            query_values = dict(parse_qsl(self.url.query))
            book_name = query_values.get("book_name")
            author = query_values.get("author")
            description = query_values.get("description")

            if not any([book_name, author, description]):
                response = json.dumps({"books": []})

                self.send_response(200)
                self.end_headers()

                self.wfile.write(response.encode("utf-8"))
                return

            r = redis.StrictRedis(
                host=os.getenv("REDIS_HOST"),
                port=6379,
                db=0,
                charset="utf-8",
                decode_responses=True,
            )

            # Get data from redis from content
            all_books = r.keys("book*")
            books_found = []

            for book in all_books:
                book_content = r.get(book)
                isFound = False

                if book_name and book_name != "":
                    book_name_parser = CustomHTMLParser("h2", "title")
                    book_name_parser.feed(book_content)
                    if book_name.lower() in book_name_parser.data[0].lower():
                        if not isFound:
                            isFound = True
                            books_found.append(get_formatted_book(book_content, book))

                if author and author != "":
                    author_parser = CustomHTMLParser("p", "author")
                    author_parser.feed(book_content)
                    if author.lower() in author_parser.data[0].lower():
                        if not isFound:
                            isFound = True
                            books_found.append(get_formatted_book(book_content, book))

                if description and description != "":
                    description_parser = CustomHTMLParser("p", "description")
                    description_parser.feed(book_content)
                    if description.lower() in description_parser.data[0].lower():
                        if not isFound:
                            isFound = True
                            books_found.append(get_formatted_book(book_content, book))

            r.connection_pool.disconnect()
            json_data = json.dumps({"books": books_found})

            self.send_response(200)
            self.end_headers()
            self.wfile.write(json_data.encode("utf-8"))
        except Exception as e:
            print(f"Error: {e}, line: {sys.exc_info()[-1].tb_lineno}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

    def get_method(self, path):
        for pattern, method in mapping:
            match = re.match(pattern, path)
            if match:
                return (method, match.groupdict())

    def do_GET(self):
        self.url = urlparse(self.path)

        method = self.get_method(self.url.path)
        if method:
            method_name, dict_params = method
            method = getattr(self, method_name)
            method(**dict_params)
            return
        else:
            self.send_error(404, "Not Found")


def set_redis_data():
    r = redis.StrictRedis(host=os.getenv("REDIS_HOST"), port=6379, db=0)
    directory = "html/books"

    for file_name in os.listdir(directory):
        file_path = os.path.join(directory, file_name)

        if r.exists(file_name):
            book = r.get(file_name)

            if book.decode("utf-8") != open(file_path, "r", encoding="utf-8").read():
                with open(file_path, "r", encoding="utf-8") as file:
                    r.set(file_name, file.read())
                    print(f"File {file_name} updated")
                continue
            else:
                print(f"File {file_name} already loaded")
                continue
        else:
            with open(file_path, "r", encoding="utf-8") as file:
                r.set(file_name, file.read())
                print(f"File {file_name} loaded")

    r.connection_pool.disconnect()


if __name__ == "__main__":
    print("Server starting...")
    server = HTTPServer(("0.0.0.0", 80), WebRequestHandler)

    print("Server running...")

    set_redis_data()

    server.serve_forever()
