import re

_trailing_commas = re.compile(r",\s*([\]}])")
_c_style_comment = re.compile(r"^\s*//.*", re.MULTILINE)
_multiline_comment = re.compile(r"^\s*/\*.*\*/", re.DOTALL | re.MULTILINE)

def clean_json(text):
    # Remove single-line comments
    text = _c_style_comment.sub("", text)
    # Remove multi-line comments
    text = _multiline_comment.sub("", text)
    # Replace trailing commas
    text = _trailing_commas.sub(r"\1", text)

    return text
