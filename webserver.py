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

        # Create redis connection
        r = redis.StrictRedis(host="localhost", port=6379, db=0)

        # Get data from redis
        book = r.get(self.url.path[1:])

        # Close redis connection
        r.connection_pool.disconnect()

        # Set response
        self.send_response(200)
        # Write headers
        self.wfile.write(self.get_response(book).encode("utf-8"))

    def get_response(self, book):
        if book:
            return book.decode("utf-8")
        return """
            <h1> Hola Web </h1>
            <p> Hello World </p>
        """


def set_redis_data():
    r = redis.StrictRedis(host="localhost", port=6379, db=0)
    directory = "html/books"

    for file_name in os.listdir(directory):
        if r.exists(file_name):
            print(f"File {file_name} already loaded")
            continue
        else:
            file_path = os.path.join(directory, file_name)
            with open(file_path, "r", encoding="utf-8") as file:
                r.set(file_name, file.read())
                print(f"File {file_name} loaded")

    r.connection_pool.disconnect()


books = {
    "1": "book 1",
    "2": "book 2",
}

if __name__ == "__main__":
    print("Server starting...")
    server = HTTPServer(("0.0.0.0", 80), WebRequestHandler)

    print("Server running...")

    set_redis_data()

    server.serve_forever()
