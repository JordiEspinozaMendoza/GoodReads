from functools import cached_property
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlparse
import re
import os
import redis

mapping = [
    (r"^/books/search", "get_api_search"),
    (r"^/books/(?P<book_file>.+)$", "get_book"),
    (r"^/$", "get_index"),
    (r"^/index$", "get_index"),
    (r"^/search$", "get_search"),
    (r"^/results$", "get_results"),
]


class WebRequestHandler(BaseHTTPRequestHandler):
    def get_book(self, book_file):
        self.url = urlparse(self.path)

        # Create redis connection
        r = redis.StrictRedis(
            host="localhost",
            port=6379,
            db=0,
            charset="utf-8",
            decode_responses=True,
        )

        # Get data from redis
        book = r.get(book_file)

        # Close redis connection
        r.connection_pool.disconnect()

        # Set response
        self.send_response(200)
        # Write headers
        self.wfile.write(book.encode("utf-8"))

    def get_by_file_name(self, file_name):
        file_path = os.path.join("html/", file_name)

        with open(file_path, "r", encoding="utf-8") as file:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(file.read().encode("utf-8"))

    def get_index(self):
        self.get_by_file_name("index.html")

    def get_search(self):
        self.get_by_file_name("search.html")

    def get_api_search(self):
        # get query string
        query_values = dict(parse_qsl(self.url.query))
        param1 = query_values.get("param1")
        param2 = query_values.get("param2")
        param3 = query_values.get("param3")

        # search in redis
        r = redis.StrictRedis(
            host="localhost",
            port=6379,
            db=0,
            charset="utf-8",
            decode_responses=True,
        )

        # Get data from redis from content
        all_books = r.keys("*")

        response = []
        # Search in each book
        for book in all_books:
            book_content = r.get(book)

            if (
                param1 in book_content
                and param2 in book_content
                and param3 in book_content
            ):
                print(f"Book found: {book}")
                print(f"Book content: {book_content}")
                response.append(book)

        # Close redis connection
        r.connection_pool.disconnect()

        # Set response
        self.send_response(200)
        # Write headers
        self.end_headers()
        # Write body
        self.wfile.write(str(response).encode("utf-8"))

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
    r = redis.StrictRedis(host="localhost", port=6379, db=0)
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
