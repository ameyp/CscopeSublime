import sublime, sublime_plugin
import os
import re
import subprocess
import string
import threading

CSCOPE_PLUGIN_DIR = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
CSCOPE_SYNTAX_FILE = "Packages/" + CSCOPE_PLUGIN_DIR + "/Lookup Results.hidden-tmLanguage"

def get_settings():
    return sublime.load_settings("CscopeSublime.sublime-settings")

def get_setting(key, default=None, view=None):
    try:
        if view == None:
            view = sublime.active_window().active_view()
        s = view.settings()
        if s.has("CscopeSublime_%s" % key):
            return s.get("CscopeSublime_%s" % key)
    except:
        pass
    return get_settings().get(key, default)

class CscopeVisiter(sublime_plugin.TextCommand):
    def __init__(self,view):
        self.view = view

    def run_(self, args):
        if self.view.settings().get('syntax') == CSCOPE_SYNTAX_FILE:
            root_re = re.compile(r'In folder (.+)')
            filepath_re = re.compile(r'^(.+):$')
            filename_re = re.compile(r'([a-zA-Z0-9_\-\.]+):')
            line_num_re = re.compile(r'^\s*([0-9]+)')

            m = root_re.search(self.view.substr(self.view.line(0)))
            if not m:
                print "Unable to determine root for: %s" % (self.view.substr(self.view.line(0)))
                return

            root = m.group(1)
            for region in self.view.sel():
                # Find anything looking like file in whole line at cursor
                if not region.empty():
                    break

                match_line = self.view.substr(self.view.line(region))

                m = line_num_re.search(match_line)
                if not m:
                    print "Unable to match line number in " + match_line
                    return

                lineno = m.group(1)
                line_beg = self.view.line(region).begin()
                prev_line_bounds = self.view.line(sublime.Region(line_beg - 1, line_beg - 1))
                file_line = self.view.substr(prev_line_bounds)
                m = filepath_re.search(file_line)

                while m == None:
                    line_beg = prev_line_bounds.begin()
                    prev_line_bounds = self.view.line(sublime.Region(line_beg - 1, line_beg - 1))
                    file_line = self.view.substr(prev_line_bounds)
                    m = filepath_re.search(file_line)

                if not m:
                    print "Unable to match filepath in " + file_line
                    return

                filepath = os.path.join(root, m.group(1))
                if not ( os.path.isfile(filepath) ):
                    print "Unable to open file: %s" % (filepath)
                    return

                m = filename_re.search(file_line)
                if not m:
                    print "Matched filepath, file exists, but unable to match filename in " + file_line
                    return

                filename = m.group(1)
                print "Opening file '%s'" % (filepath + ":" + lineno)
                CscopeCommand.add_to_history( getEncodedPosition(filepath, lineno) )
                sublime.active_window().open_file(filepath + ":" + lineno, sublime.ENCODED_POSITION)
        else:
            self.view.run_command("drag_select", {'event': args['event']})
            self.view.run_command("drag_select", args)

class GobackCommand(sublime_plugin.TextCommand):
    def __init__(self,view):
        self.view = view

    def run(self, edit):
        if not CscopeCommand.is_history_empty():
            file_name = CscopeCommand.pop_latest_from_history()
            while file_name == getCurrentPosition(self.view):
                file_name = CscopeCommand.pop_latest_from_history()

            CscopeCommand.add_to_future( getCurrentPosition(self.view) )
            sublime.active_window().open_file(file_name, sublime.ENCODED_POSITION)

class ForwardCommand(sublime_plugin.TextCommand):
    def __init__(self,view):
        self.view = view

    def run(self, edit):
        if not CscopeCommand.is_future_empty():
            file_name = CscopeCommand.pop_latest_from_future()
            while file_name == getCurrentPosition(self.view):
                file_name = CscopeCommand.pop_latest_from_future()

            CscopeCommand.add_to_history( getCurrentPosition(self.view) )
            sublime.active_window().open_file(file_name, sublime.ENCODED_POSITION)

def getEncodedPosition(file_name, line_num):
    return file_name + ":" + str(line_num)

def getCurrentPosition(view):
    return getEncodedPosition( view.file_name(), view.rowcol( view.sel()[0].a )[0] + 1 )

class CscopeSublimeWorker(threading.Thread):
    _modes = {
        0: "C symbol",
        1: "Global definition",
        2: "Functions called by this function",
        3: "Functions calling this function",
        4: "Text string",
        5: "egrep pattern",
        6: "Files #including this file"
    }

    def __init__(self, view, platform, root, database, symbol, mode):
        super(CscopeSublimeWorker, self).__init__()
        self.view = view
        self.platform = platform
        self.root = root
        self.database = database
        self.symbol = symbol
        self.mode = mode

    # switch statement for the different formatted output
    # of Cscope's matches.
    def append_match_string(self, match, command_mode, nested):
        match_string = "{0}".format(match["file"])
        if command_mode == 0:
            if nested:
                match_string = ("{0:>6}\n{1:>6} [scope: {2}] {3}").format("..", match["line"], match["scope"], match["instance"])
            else:
                match_string = ("\n{0}:\n{1:>6} [scope: {2}] {3}").format(match["file"].replace(self.root, "."), match["line"], match["scope"], match["instance"])
        elif command_mode == 1:
            if nested:
                match_string = ("{0:>6}\n{1:>6} {2}").format("..", match["line"], match["instance"])
            else:
                match_string = ("\n{0}:\n{1:>6} {2}").format(match["file"].replace(self.root, "."), match["line"], match["instance"])
        elif command_mode == 2 or command_mode == 3:
            if nested:
                match_string = ("{0:>6}\n{1:>6} [function: {2}] {3}").format("..", match["line"], match["function"], match["instance"])
            else:
                match_string = ("\n{0}:\n{1:>6} [function: {2}] {3}").format(match["file"].replace(self.root, "."), match["line"], match["function"], match["instance"])

        return match_string


    def match_output_line(self, line, mode):
        match = None
        output = None

        # set up RegEx for matching cscope results
        if mode == 0:
            match = re.match('(\S+?)\s+?(<global>|\S+)?\s+(\d+)\s+(.+)', line)
            if match:
                output = {
                    "file": match.group(1),
                    "scope": match.group(2),
                    "line": match.group(3),
                    "instance": match.group(4)
                }
        elif mode == 1:
            match = re.match('(\S+?)\s+?\S+\s+(\d+)\s+(.+)', line)
            if match:
                output = {
                    "file": match.group(1),
                    "line": match.group(2),
                    "instance": match.group(3)
                }
        elif mode == 2 or mode == 3:
            # [path] [function] [line #] [string]
            match = re.match('(\S+)\s+?(\S+)\s+(\d+)\s+(.+)', line)
            if match:
                output = {
                    "file": match.group(1),
                    "function": match.group(2),
                    "line": match.group(3),
                    "instance": match.group(4)
                }

        return output

    def run_cscope(self, mode, word):
        newline = ''
        if self.platform == "windows":
            newline = '\r\n'
        else:
            newline = '\n'

        # print 'cscope -dL -f {0} -{1} {2}'.format(self.database, str(mode), word)
        cscope_arg_list = ['cscope', '-dL', '-f', self.database, '-' + str(mode) + word]
        popen_arg_list = {
            "shell": False,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE
        }
        if (self.platform == "windows"):
            popen_arg_list["creationflags"] = 0x08000000

        proc = subprocess.Popen(cscope_arg_list, **popen_arg_list)
        output = proc.communicate()[0].split(newline)
        # print output

        self.matches = []
        for i in output:
            match = self.match_output_line(i, mode)
            if match != None:
                self.matches.append(match)
                # print "File ", match.group(1), ", Line ", match.group(2), ", Instance ", match.group(3)

        options = []
        prev_file = ""
        for match in self.matches:
            options.append(self.append_match_string(match, mode, prev_file == match["file"]))
            prev_file = match["file"]

        return options

    def run(self):
        matches = self.run_cscope(self.mode, self.symbol)
        self.num_matches = len(matches)
        self.output = "In folder " + self.root + \
            "\nFound " + str(len(matches)) + " matches for " + self._modes[self.mode] + \
             ": " + self.symbol + "\n" + 50*"-" + "\n\n" + "\n".join(matches)

class CscopeCommand(sublime_plugin.TextCommand):
    _backLines = []
    _forwardLines = []

    @staticmethod
    def is_history_empty():
        return len(CscopeCommand._backLines) == 0

    @staticmethod
    def add_to_history(line):
        print "add_to_history"
        print CscopeCommand._backLines, CscopeCommand._forwardLines
        if CscopeCommand.is_history_empty() or CscopeCommand._backLines[0] != line:
            CscopeCommand._backLines.insert(0, line)
        if len(CscopeCommand._backLines) > 100:
            CscopeCommand._backLines = CscopeCommand._backLines[:100]

    @staticmethod
    def pop_latest_from_history():
        print "pop_latest_from_history"
        print CscopeCommand._backLines, CscopeCommand._forwardLines
        latest = CscopeCommand._backLines[0]
        CscopeCommand._backLines = CscopeCommand._backLines[1:]
        return latest

    @staticmethod
    def is_future_empty():
        return len(CscopeCommand._forwardLines) == 0

    @staticmethod
    def add_to_future(line):
        print "add_to_future"
        print CscopeCommand._backLines, CscopeCommand._forwardLines
        if CscopeCommand.is_future_empty() or CscopeCommand._forwardLines[0] != line:
            CscopeCommand._forwardLines.insert(0, line)
        if len(CscopeCommand._forwardLines) > 100:
            CscopeCommand._forwardLines = CscopeCommand._forwardLines[:100]

    @staticmethod
    def pop_latest_from_future():
        print "pop_latest_from_future"
        print CscopeCommand._backLines, CscopeCommand._forwardLines
        latest = CscopeCommand._forwardLines[0]
        CscopeCommand._forwardLines = CscopeCommand._forwardLines[1:]
        return latest

    def __init__(self, view):
        self.view = view
        self.database = None
        settings = get_settings()

    def update_database(self, filename):
        if get_setting("database_location", "") != "":
            self.database = get_setting("database_location", "")
            self.root = os.path.dirname(self.database)
        else:
            cdir = os.path.dirname(filename)
            while cdir != os.path.dirname(cdir):
                if ("cscope.out" in os.listdir(cdir)):
                    self.root = cdir
                    self.database = os.path.join(cdir, "cscope.out")
                    # print "Database found: ", self.database
                    break
                cdir = os.path.dirname(cdir)

    def update_status(self, workers, count=0, dir=1):
        count = count + dir
        found = False

        for worker in workers:
            if worker.is_alive():
                found = True
                if count == 7:
                    dir = -1
                elif count == 0:
                    dir = 1
                self.view.set_status("CscopeSublime", "Fetching lookup results [%s=%s]" %
                                    (' ' * count, ' ' * (7 - count)))
                sublime.set_timeout(lambda: self.update_status(workers, count, dir), 100)
                break

        if not found:
            self.view.erase_status("CscopeSublime")
            output = ""
            for worker in workers:
                self.display_results(worker.symbol, worker.output)

    def display_results(self, symbol, output):
        cscope_view = self.view.window().new_file()
        cscope_view.set_scratch(True)
        cscope_view.set_name("Cscope results - " + symbol)

        cscope_edit = cscope_view.begin_edit()
        cscope_view.insert(cscope_edit, 0, output)

        if get_setting("display_outline") == True:
            symbol_regions = cscope_view.find_all(symbol, sublime.LITERAL)
            cscope_view.add_regions('cscopesublime-outlines', symbol_regions[1:], "text.find-in-files", "", sublime.DRAW_OUTLINED)

        cscope_view.end_edit(cscope_edit)

        cscope_view.set_syntax_file(CSCOPE_SYNTAX_FILE)
        cscope_view.set_read_only(True)

    def run(self, edit, mode):
        if self.database == None:
            self.update_database(self.view.file_name())

            if self.database == None:
                sublime.error_message("Could not find cscope database: cscope.out")
                return

        CscopeCommand.add_to_history( getCurrentPosition(self.view) )

        one = self.view.sel()[0].a
        two = self.view.sel()[0].b

        self.view.sel().add(sublime.Region(one, two))

        workers = []
        for sel in self.view.sel():
            symbol = self.view.substr(self.view.word(sel))
            worker = CscopeSublimeWorker(
                    view = self.view,
                    platform = sublime.platform(),
                    root = self.root,
                    database = self.database,
                    symbol = symbol,
                    mode = mode
                )
            worker.start()
            workers.append(worker)

        self.update_status(workers)
