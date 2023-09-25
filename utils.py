from html.parser import HTMLParser
import sys


class CustomHTMLParser(HTMLParser):
    def __init__(self, tagArray: tuple, tagValue: tuple):
        super().__init__()
        self.data = []
        self.capture = False
        self.tagArray = tagArray
        self.tagValue = tagValue

    def handle_starttag(self, tag, attrs):
        if tag in self.tagArray:
            for name, value in attrs:
                if name == "id" and value in self.tagValue:
                    self.capture = True

    def handle_endtag(self, tag):
        if tag in self.tagArray:
            self.capture = False

    def handle_data(self, data):
        if self.capture:
            self.data.append(data)


def get_formatted_book(book, book_key):
    try:
        book_name_parser = CustomHTMLParser(("h2"), ("title"))
        book_name_parser.feed(book)
        book_name = book_name_parser.data[0]

        author_parser = CustomHTMLParser(("p"), ("author"))
        author_parser.feed(book)
        author = author_parser.data[0]

        description_parser = CustomHTMLParser(("p"), ("description"))
        description_parser.feed(book)
        description = description_parser.data[0]

        return {
            "book_name": book_name,
            "author": author,
            "description": description,
            "url": f"/books/{book_key}",
        }
    except Exception as e:
        print(f"Error: {e}, line: {sys.exc_info()[-1].tb_lineno}")
