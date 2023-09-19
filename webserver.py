from functools import cached_property
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlparse
import re
import os
import redis


class WebRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.url = urlparse(self.path)

        ends_with_html = re.search(r"\.html$", self.url.path)

        if ends_with_html:
            # Create redis connection
            r = redis.StrictRedis(host="localhost", port=6379, db=0)

            # Get data from redis
            url_path = self.url.path.split("/")[2].lower()
            book = r.get(url_path)

            # Close redis connection
            r.connection_pool.disconnect()

            # Set response
            self.send_response(200)
            # Write headers
            self.wfile.write(self.get_response(book).encode("utf-8"))

    def validate_endpoint(self):
        endpoint = self.url.path.split("/")[1].lower()

        return endpoint == "" or endpoint == "index.html"

    def get_response(self, book):
        if self.validate_endpoint():
            with open("html/index.html") as f:
                return f.read()
        if book:
            return book.decode("utf-8")
        return """
            File not found
        """


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
