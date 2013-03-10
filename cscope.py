import sublime, sublime_plugin
import os
import re
import subprocess
import string

CSCOPE_PLUGIN_DIR = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
CSCOPE_SYNTAX_FILE = "Packages/" + CSCOPE_PLUGIN_DIR + "/Lookup Results.hidden-tmLanguage"

class CscopeVisiter(sublime_plugin.TextCommand):
    def __init__(self,view):
        self.view = view

    def run(self, edit):
        if self.view.settings().get('syntax') == CSCOPE_SYNTAX_FILE:
            root_re = re.compile(r'In folder (.+)')
            filepath_re = re.compile(r'(.+):[0-9]+ - ')
            filename_re = re.compile(r'([a-zA-Z0-9_\-\.]+):([0-9]+) - ')

            m = root_re.search(self.view.substr(self.view.line(0)))
            if m:
                root = m.group(1)
                for region in self.view.sel():
                    # Find anything looking like file in whole line at cursor
                    if not region.empty():
                        break

                    whole_line = self.view.substr(self.view.line(region))
                    m = filepath_re.search(whole_line)
                    if m:
                        filepath = os.path.join(root, m.group(1))
                        if ( os.path.isfile(filepath) ):
                            m = filename_re.search(whole_line)
                            if m:
                                filename = m.group(1)
                                lineno = m.group(2)
                                print "Opening file '%s'" % (filepath + ":" + lineno)
                                CscopeCommand.add_to_history( getEncodedPosition(filepath, lineno) )
                                sublime.active_window().open_file(filepath + ":" + lineno, sublime.ENCODED_POSITION)
                            else:
                                print "Something went wrong."
                                # print os.listdir(root)
                        else:
                            print "Unable to open file: %s" % (filepath)
            else:
                print "Unable to determine root for: %s" % (self.view.substr(self.view.line(0)))

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
        # self.panel  = self.view.window().get_output_panel("cscope")

    def update_database(self, filename):
        cdir = os.path.dirname(filename)
        while cdir != os.path.dirname(cdir):
            if ("cscope.out" in os.listdir(cdir)):
                self.root = cdir
                self.database = os.path.join(cdir, "cscope.out")
                # print "Database found: ", self.database
                break
            cdir = os.path.dirname(cdir)

    def run(self, edit, mode):
        # self.word_separators = self.view.settings().get('word_separators')
        # print self.view.sel()
        # self.view.insert(edit, 0, "Hello, World!")
        # print mode
        CscopeCommand.add_to_history( getCurrentPosition(self.view) )

        one = self.view.sel()[0].a
        two = self.view.sel()[0].b
        self.view.sel().add(sublime.Region(one,
                                           two))
        for sel in self.view.sel():
            word = self.view.substr(self.view.word(sel))
            # print "Word: ", word
            options = self.run_cscope(mode, word)
            cscope_view = self.view.window().new_file()
            cscope_view.set_scratch(True)
            cscope_view.set_name(word)

            cscope_edit = cscope_view.begin_edit()
            cscope_view.insert(cscope_edit, 0, "In folder " + self.root + "\n\n" + "\n".join(options))
            cscope_view.end_edit(cscope_edit)

            cscope_view.set_syntax_file(CSCOPE_SYNTAX_FILE)

            cscope_view.set_read_only(True)
            # self.view.window().show_quick_panel(options, self.on_done)
            # self.view.window().run_command("show_panel", {"panel": "output." + "cscope"})

    # switch statement for the different formatted output
    # of Cscope's matches.
    def _append_match_string(self, match, command_mode):
        default = "{0}".format(match["file"])
        if command_mode == 0:
            return "{0}:{1} - {2} - {3}".format(match["file"].replace(self.root, "."), match["line"], match["scope"], match["instance"])
        elif command_mode == 1:
            return "{0}:{1} - {2}".format(match["file"].replace(self.root, "."), match["line"], match["instance"])
        elif command_mode == 2 or command_mode == 3:
            return "{0}:{1} - {2} - {3}".format(match["file"].replace(self.root, "."), match["line"], match["function"], match["instance"])
        else:
            return default

    def run_cscope(self, mode, word):
        # 0 ==> C symbol
        # 1 ==> function definition
        # 2 ==> functions called by this function
        # 3 ==> functions calling this function
        # 4 ==> text string
        # 5 ==> egrep pattern
        # 6 ==> files

        if self.database == None:
            self.update_database(self.view.file_name())

            if self.database == None:
                sublime.status_message("Could not find cscope database: cscope.out")

        newline = ''
        if sublime.platform() == "windows":
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
        if (sublime.platform() == "windows"):
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

        # self.view.window().run_command("show_overlay", {"overlay": "goto", "text": "@"})
        options = []
        for match in self.matches:
            options.append(self._append_match_string(match, mode))

        return options

    def match_output_line(self, line, mode):
        match = None
        output = None

        # set up RegEx for matching cscope results
        if mode == 0:
            match = re.match('(\S+?)\s+?(<global>|\S+)?\s+(\d+)\s+(.+)', line)
            if match:
                output = {  "file": match.group(1),
                            "scope": match.group(2),
                            "line": match.group(3),
                            "instance": match.group(4)
                            }
        elif mode == 1:
            match = re.match('(\S+?)\s+?\S+\s+(\d+)\s+(.+)', line)
            if match:
                output = {  "file": match.group(1),
                            "line": match.group(2),
                            "instance": match.group(3)
                            }
        elif mode == 2 or mode == 3:
            # [path] [function] [line #] [string]
            match = re.match('(\S+)\s+?(\S+)\s+(\d+)\s+(.+)', line)
            if match:
                output = {  "file": match.group(1),
                            "function": match.group(2),
                            "line": match.group(3),
                            "instance": match.group(4)
                            }

        return output
