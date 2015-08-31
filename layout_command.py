import sublime_plugin


class SerialMonitorLayoutCommand(sublime_plugin.WindowCommand):
    layouts = [
        {  # Left-Right params
            "cols": [0.0, 0.5, 1.0],
            "rows": [0.0, 1.0],
            "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]
        },
        {  # Over-Under params
            "cols": [0.0, 1.0],
            "rows": [0.0, 0.5, 1.0],
            "cells": [[0, 0, 1, 1], [0, 1, 1, 2]]
        }
    ]
    layout_names = ["Left-Right", "Over-Under"]

    def run(self, **args):
        def layout_selected(index):
            if index == -1:
                return
            self.window.run_command("set_layout", self.layouts[index])
            self._arrange_views()

        if "layout" in args:
            idx = self.layout_names.index(args["layout"])
            layout_selected(idx)
        else:
            self.window.show_quick_panel(self.layout_names, layout_selected)

    def _arrange_views(self):
        last_focused = self.window.active_view()

        for view in self.window.views():
            group = 0
            if view.is_read_only():
                group = 1
            self.window.focus_view(view)
            self.window.run_command("move_to_group", {"group": group})

        self.window.focus_view(last_focused)
