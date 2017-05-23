import functools
import sublime


def main_thread(callback, *args, **kwargs):
    """
    Sends the callback to the sublime main thread by using the sublime.set_timeout function.
    Most of the sublime functions need to be called from the main thread

    :param callback: The callback function
    :param args: positional args to send to the callback function
    :param kwargs: keyword args to send to the callback function
    """
    # sublime.set_timeout gets used to send things onto the main thread
    # most sublime.[something] calls need to be on the main thread
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)


def sublime_line_endings_to_serial(text, line_endings):
    """
    Converts the sublime text line endings to the serial line ending given

    :param text: the text to convert line endings for
    :param line_endings: the serial's line endings setting: "CR", "LF", or "CRLF"
    :return: the new text
    """
    if line_endings == "CR":
        return text.replace("\n", "\r")
    if line_endings == "CRLF":
        return text.replace("\n", "\r\n")
    return text


def serial_line_endings_to_sublime(text, line_endings):
    """
    Converts the serial line endings to sublime text line endings

    :param text: the text to convert line endings for
    :param line_endings: the serial's line endings setting: "CR", "LF", or "CRLF"
    :return: the new text
    """
    if line_endings == "CR":
        return text.replace("\r", "\n")
    if line_endings == "CRLF":
        return text.replace("\r", "")
    return text
