import sublime, sublime_plugin


class SerialMonitorLayoutCommand(sublime_plugin.WindowCommand):
    layouts = [
        {
            "cols": [0.0, 0.5, 1.0],
            "rows": [0.0, 1.0],
            "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]
        },
        {
            "cols": [0.0, 1.0],
            "rows": [0.0, 0.5, 1.0],
            "cells": [[0, 0, 1, 1], [0, 1, 1, 2]]
        }
    ]
    layout_names = ["Left-Right", "Over-Under"]

    def run(self):
        self.window.show_quick_panel(self.layout_names, self.layout_selected)

    def layout_selected(self, index):
        if index == -1:
            return
        self.window.run_command("set_layout", self.layouts[index])

        for view in self.window.views():
            group = 0
            fname = view.file_name()
            if fname and fname.endswith(".py"):
                group = 1
            view.run_command("move_to_group", {"group":1})