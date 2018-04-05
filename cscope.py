import sublime, sublime_plugin
import os
import re
import subprocess
import string
import threading
import errno

CSCOPE_PLUGIN_DIR = os.path.basename(os.path.dirname(os.path.realpath(__file__)))

# Package Control on ST3 compresses the package into a single "package-name.sublime-package" file,
# but ST3 internally treats the location of the package's contents as being in "Packages/packages-name/"
if CSCOPE_PLUGIN_DIR.find(".sublime-package") != -1:
    CSCOPE_PLUGIN_DIR = CSCOPE_PLUGIN_DIR[0:CSCOPE_PLUGIN_DIR.find(".sublime-package")]

CSCOPE_SYNTAX_FILE = "Packages/" + CSCOPE_PLUGIN_DIR + "/Lookup Results.hidden-tmLanguage"
CSCOPE_SEARCH_MODES = {
    0: "C symbol",
    1: "global definition",
    2: "functions called by this function",
    3: "functions calling this function",
    4: "text string",
    # intentionally not providing 5/Change this text string
    6: "egrep pattern",
    7: "file named",
    8: "files #including this file"
}
CSCOPE_CMD_DATABASE_REBUILD = "database_rebuild"

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


class CscopeDatabase(object):
    def __init__(self, view, executable):
        self.view = view
        self.executable = executable
        self.root = None
        self.location = None

    def update_location(self, filename):
        self.root = None
        self.location = None
        project_info = None
        project_info_paths = []

        # project_data is only available in ST3. we need to add this check
        # to not break our plugin for ST2 users. see also issue #51.
        if hasattr(self.view.window(), 'project_data'):
            project_info = self.view.window().project_data()
            if project_info and 'folders' in project_info:
               project_info_paths = [folder['path'] for folder in project_info['folders']]

        # if the user provided database_location, validate it before using it
        database_location = get_setting('database_location')

        if database_location:
            print('CScopeDatabase: user provided database_location: {}'
                  .format(database_location))

            # if it's not a string, it's not valid
            if not isinstance(database_location, str):
                sublime.error_message('Cscope: Invalid database_location: {}'
                                      .format(database_location))
                return

            # expand user directory if it was used
            if database_location.startswith('~'):
                database_location = os.path.expanduser(database_location)

            # if the user-provided database does not end with "cscope.out", this
            # is an invalid location
            if not database_location.endswith('cscope.out'):
                sublime.error_message('Cscope: Invalid database_location: {}. '
                                      'Filename must end with cscope.out.'
                                      .format(database_location))
                return

            database_location_dir = os.path.dirname(database_location)

            # the directory _must_ exist because we use this as cwd for subprocess
            # commands
            if not os.path.isdir(database_location_dir):
                sublime.error_message('Cscope: Invalid database_location: {}. '
                                      'Directory does not exist.'
                                      .format(database_location))
                return

            self.location = database_location
            self.root = database_location_dir

            print('CScopeDatabase: using location: {}, root: {}'
                  .format(self.location, self.root))
            return
        else:
            cdir_list = []
            if (filename):
                cdir_list = [os.path.dirname(filename)]
            elif (project_info):
                cdir_list = project_info_paths
            else:
                print('CscopeDatabase: No project or filename.')
                return

            for cdir in cdir_list:
                while cdir != os.path.dirname(cdir):
                    if ("cscope.out" in os.listdir(cdir)):
                        self.root = cdir
                        self.location = os.path.join(cdir, "cscope.out")
                        print('CscopeDatabase: Database found: ', self.location)
                        return
                    cdir = os.path.dirname(cdir)

            # If we haven't found an existing database location and root
            # directory, and the user has a project defined for this, and
            # there's only one path in that project, let's just assume that that
            # path is the root of the project. This should be a safe assumption
            # and should allow us to create an initial database, if one doesn't
            # exist, in a sane place.
            if self.root is None and self.location is None and len(project_info_paths) == 1:
                self.root = project_info_paths[0]
                print('CscopeDatabase: Database not found but setting root: {}'
                      .format(self.root))

    def rebuild(self):
        if not (self.root and os.path.isdir(self.root)):
            sublime.error_message('Cscope: No working directory found. '
                                  'Unable to rebuild database.')
            return

        cscope_arg_list = get_setting('database_build_command')

        # If the user provided a custom command to build their cscope database,
        # use it, otherwise use a hopefully sane default
        if not (cscope_arg_list and isinstance(cscope_arg_list, list)):
            cscope_arg_list = [self.executable, '-Rbq']

        print('CscopeDatabase: Rebuilding database in directory: {}, using command: {}'
              .format(self.root, cscope_arg_list))

        popen_arg_list = {
            "shell": False,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": self.root
        }

        try:
            proc = subprocess.Popen(cscope_arg_list, **popen_arg_list)
        except OSError as e:
            sublime.error_message('Cscope ERROR. Command: {} failed! Error: {}'
                                  .format(cscope_arg_list, e))

        output, erroroutput = proc.communicate()
        print('CscopeDatabase: Rebuild done.')


class CscopeVisiter(sublime_plugin.TextCommand):
    def __init__(self, view):
        self.view = view

    def run(self, edit):
        if self.view.settings().get('syntax') == CSCOPE_SYNTAX_FILE:
            root_re = re.compile(r'In folder (.+)')
            filepath_re = re.compile(r'^(.+):$')
            filename_re = re.compile(r'([a-zA-Z0-9_\-\.]+):')
            linenum_re = re.compile(r'^\s*([0-9]+)')

            m = root_re.search(self.view.substr(self.view.line(0)))
            if not m:
                print("Unable to determine root for: %s" % (self.view.substr(self.view.line(0))))
                return

            root = m.group(1)
            for region in self.view.sel():
                # Find anything looking like file in whole line at cursor
                if not region.empty():
                    break

                match_line = self.view.substr(self.view.line(region))

                re_match_linenum = linenum_re.search(match_line)
                re_match_filepath = filepath_re.search(match_line)

                if not re_match_linenum and not re_match_filepath:
                    print("Unable to match line number or file path in " + match_line)
                    return

                # if this line had a line number, use it and look up for the filename
                if re_match_linenum:
                    lineno = re_match_linenum.group(1)
                    line_beg = self.view.line(region).begin()
                    prev_line_bounds = self.view.line(sublime.Region(line_beg - 1, line_beg - 1))
                    file_line = self.view.substr(prev_line_bounds)

                    re_match_filepath = filepath_re.search(file_line)

                    while re_match_filepath == None:
                        line_beg = prev_line_bounds.begin()
                        prev_line_bounds = self.view.line(sublime.Region(line_beg - 1, line_beg - 1))
                        file_line = self.view.substr(prev_line_bounds)
                        re_match_filepath = filepath_re.search(file_line)

                    if not re_match_filepath:
                        print("Unable to match filepath in " + file_line)
                        return

                elif re_match_filepath:
                    lineno = "1"
                    file_line = match_line

                filepath = os.path.join(root, re_match_filepath.group(1))
                if not ( os.path.isfile(filepath) ):
                    print("Unable to open file: %s" % (filepath))
                    return

                re_match_filename = filename_re.search(file_line)
                if not re_match_filename:
                    print("Matched filepath, file exists, but unable to match filename in " + file_line)
                    return

                filename = re_match_filename.group(1)
                print("Opening file '%s'" % (filepath + ":" + lineno))
                CscopeCommand.add_to_history( getEncodedPosition(filepath, lineno) )
                sublime.active_window().open_file(filepath + ":" + lineno, sublime.ENCODED_POSITION)


class GobackCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
        self.view = view

    def run(self, edit):
        if not CscopeCommand.is_history_empty():
            file_name = CscopeCommand.pop_latest_from_history()
            while file_name == getCurrentPosition(self.view):
                file_name = CscopeCommand.pop_latest_from_history()

            CscopeCommand.add_to_future( getCurrentPosition(self.view) )
            sublime.active_window().open_file(file_name, sublime.ENCODED_POSITION)


class ForwardCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
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
    if view.file_name():
        return getEncodedPosition( view.file_name(), view.rowcol( view.sel()[0].a )[0] + 1 )
    else:
        return None


class CscopeSublimeDatabaseRebuildWorker(threading.Thread):
    def __init__(self, database):
        super(CscopeSublimeDatabaseRebuildWorker, self).__init__()
        self.database = database

    def run(self):
        self.database.rebuild()


class CscopeSublimeSearchWorker(threading.Thread):
    def __init__(self, view, platform, database, symbol, mode, executable):
        super(CscopeSublimeSearchWorker, self).__init__()
        self.view = view
        self.platform = platform
        self.database = database
        self.symbol = symbol
        self.mode = mode
        self.executable = executable
        self.output = ""

    # switch statement for the different formatted output
    # of Cscope's matches.
    def append_match_string(self, match, command_mode, nested):
        match_string = "{0}".format(match["file"])
        if command_mode in [0, 4, 6, 8]:
            if nested:
                match_string = ("{0:>6}\n{1:>6} [scope: {2}] {3}").format("..", match["line"], match["scope"], match["instance"])
            else:
                match_string = ("\n{0}:\n{1:>6} [scope: {2}] {3}").format(match["file"].replace(self.database.root, "."), match["line"], match["scope"], match["instance"])
        elif command_mode == 1:
            if nested:
                match_string = ("{0:>6}\n{1:>6} {2}").format("..", match["line"], match["instance"])
            else:
                match_string = ("\n{0}:\n{1:>6} {2}").format(match["file"].replace(self.database.root, "."), match["line"], match["instance"])
        elif command_mode in [2, 3]:
            if nested:
                match_string = ("{0:>6}\n{1:>6} [function: {2}] {3}").format("..", match["line"], match["function"], match["instance"])
            else:
                match_string = ("\n{0}:\n{1:>6} [function: {2}] {3}").format(match["file"].replace(self.database.root, "."), match["line"], match["function"], match["instance"])
        elif command_mode == 7:
                match_string = ("\n{0}:").format(match["file"].replace(self.database.root, "."))

        return match_string


    def match_output_line(self, line, mode):
        match = None
        output = None

        # set up RegEx for matching cscope results
        if mode in [0, 4, 6, 7, 8]:
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
        elif mode in [2, 3]:
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
        newline = '\n'

        cscope_arg_list = [self.executable, '-dL', '-f', self.database.location, '-' + str(mode) + word]
        popen_arg_list = {
            "shell": False,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": self.database.root,
            "universal_newlines": True
        }
        if (self.platform == "windows"):
            popen_arg_list["creationflags"] = 0x08000000
            popen_arg_list["stdin"] = subprocess.PIPE

        try:
            proc = subprocess.Popen(cscope_arg_list, **popen_arg_list)
        except OSError as e:
            sublime.error_message('Cscope ERROR. Command: {} failed! Error: {}'
                                  .format(cscope_arg_list, e))

        output, erroroutput = proc.communicate()

        output = output.split(newline)

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
        self.output = "In folder " + self.database.root + \
            "\nFound " + str(len(matches)) + " matches for " + CSCOPE_SEARCH_MODES[self.mode] + \
             ": " + self.symbol + "\n" + 50*"-" + "\n\n" + "\n".join(matches)


class CscopeCommand(sublime_plugin.TextCommand):
    _backLines = []
    _forwardLines = []

    cscope_output_info  = {}

    @staticmethod
    def is_history_empty():
        return len(CscopeCommand._backLines) == 0

    @staticmethod
    def add_to_history(line):
        print("add_to_history")
        print(CscopeCommand._backLines, CscopeCommand._forwardLines)
        if CscopeCommand.is_history_empty() or CscopeCommand._backLines[0] != line:
            CscopeCommand._backLines.insert(0, line)
        if len(CscopeCommand._backLines) > 100:
            CscopeCommand._backLines = CscopeCommand._backLines[:100]

    @staticmethod
    def pop_latest_from_history():
        print("pop_latest_from_history")
        print(CscopeCommand._backLines, CscopeCommand._forwardLines)
        latest = CscopeCommand._backLines[0]
        CscopeCommand._backLines = CscopeCommand._backLines[1:]
        return latest

    @staticmethod
    def is_future_empty():
        return len(CscopeCommand._forwardLines) == 0

    @staticmethod
    def add_to_future(line):
        print("add_to_future")
        print(CscopeCommand._backLines, CscopeCommand._forwardLines)
        if CscopeCommand.is_future_empty() or CscopeCommand._forwardLines[0] != line:
            CscopeCommand._forwardLines.insert(0, line)
        if len(CscopeCommand._forwardLines) > 100:
            CscopeCommand._forwardLines = CscopeCommand._forwardLines[:100]

    @staticmethod
    def pop_latest_from_future():
        print("pop_latest_from_future")
        print(CscopeCommand._backLines, CscopeCommand._forwardLines)
        latest = CscopeCommand._forwardLines[0]
        CscopeCommand._forwardLines = CscopeCommand._forwardLines[1:]
        return latest

    def __init__(self, view):
        self.view = view
        self.database = None
        self.executable = None
        self.workers = []
        settings = get_settings()

    def update_status(self, count=0, dir=1):
        count = count + dir
        workInProgress = False

        for worker in self.workers:
            if worker.is_alive():
                workInProgress = True
                if count == 7:
                    dir = -1
                elif count == 0:
                    dir = 1

                statusSearchers = ""
                statusRebuilders = ""

                if isinstance(worker, CscopeSublimeSearchWorker):
                    statusSearchers = "Fetching lookup results. "

                if isinstance(worker, CscopeSublimeDatabaseRebuildWorker):
                    statusRebuilders = "Rebuilding cross-reference database. "

                self.view.set_status("CscopeSublime",
                                     "Cscope: {}{}[{}={}]"
                                     .format(statusSearchers, statusRebuilders,
                                             ' ' * count, ' ' * (7 - count)))
                sublime.set_timeout(lambda: self.update_status(count, dir), 100)
                break

        if not workInProgress:
            self.view.erase_status("CscopeSublime")
            output = ""
            for worker in self.workers:
                if isinstance(worker, CscopeSublimeSearchWorker):
                    self.display_results(worker.symbol, worker.output)

            self.workers = []

    def display_results(self, symbol, output):
        cscope_view = self.view.window().new_file()
        cscope_view.set_scratch(True)
        cscope_view.set_name("Cscope results - " + symbol)
        CscopeCommand.cscope_output_info['view'] = cscope_view
        CscopeCommand.cscope_output_info['pos'] = 0
        CscopeCommand.cscope_output_info['text'] = output
        CscopeCommand.cscope_output_info['symbol'] = symbol

        cscope_view.run_command("display_cscope_results")

        cscope_view.set_syntax_file(CSCOPE_SYNTAX_FILE)
        cscope_view.set_read_only(True)

    def run(self, edit, mode):
        self.mode = mode
        self.executable = get_setting("executable", "cscope")

        # Create a new database object every time we run. This way, if our user
        # deleted cscope files or recreated them, we have a correct understanding
        # of the current state.
        self.database = CscopeDatabase(view = self.view,
                                       executable = self.executable)
        self.database.update_location(self.view.file_name())

        if mode == CSCOPE_CMD_DATABASE_REBUILD:
            self.rebuild_database()
            return

        if self.database.location == None:
            sublime.error_message("Could not find cscope database: cscope.out")
            return

        cur_pos = getCurrentPosition(self.view)
        if cur_pos:
            CscopeCommand.add_to_history(cur_pos)

        # Search for the first word that is selected. While Sublime Text uses
        # multiple selections, we only want the first selection since simultaneous
        # multiple cscope lookups don't make sense.
        first_selection = self.view.sel()[0]
        one = first_selection.a
        two = first_selection.b

        self.view.sel().add(sublime.Region(one, two))

        symbol = self.view.substr(self.view.word(first_selection))
        if get_setting("prompt_before_searching") == True:
            sublime.active_window().show_input_panel('Search Cscope for ' + CSCOPE_SEARCH_MODES[self.mode] + ':',
                                                     symbol,
                                                     self.on_search_confirmed,
                                                     None,
                                                     None)
        else:
            self.on_search_confirmed(symbol)

    def on_search_confirmed(self, symbol):
        worker = CscopeSublimeSearchWorker(
                view = self.view,
                platform = sublime.platform(),
                database = self.database,
                symbol = symbol,
                mode = self.mode,
                executable = self.executable
            )
        worker.start()
        self.workers.append(worker)
        self.update_status()

    def rebuild_database(self):
        worker = CscopeSublimeDatabaseRebuildWorker(self.database)
        worker.start()
        self.workers.append(worker)
        self.update_status()


class DisplayCscopeResultsCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        self.view.insert(edit, CscopeCommand.cscope_output_info['pos'], CscopeCommand.cscope_output_info['text'])
        if get_setting("display_outline") == True:
            symbol_regions = self.view.find_all(CscopeCommand.cscope_output_info['symbol'], sublime.LITERAL)
            self.view.add_regions('cscopesublime-outlines', symbol_regions[1:], "text.find-in-files", "", sublime.DRAW_OUTLINED)
