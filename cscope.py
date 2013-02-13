import sublime, sublime_plugin
import os
import re
import subprocess
import string

class CscopeVisiter(sublime_plugin.EventListener):
    def on_selection_modified(self, view):
        if view.settings().get('syntax') == "Packages/CscopeSublime/Lookup Results.hidden-tmLanguage":
            root_re = re.compile(r'In folder (.+)')
            filepath_re = re.compile(r'(.+):[0-9]+ - ')
            filename_re = re.compile(r'([a-zA-Z0-9_\-\.]+):([0-9]+) - ')

            m = root_re.search(view.substr(view.line(0)))
            if m:
                root = m.group(1)
                for region in view.sel():
                    # Find anything looking like file in whole line at cursor
                    if not region.empty():
                        break

                    whole_line = view.substr(view.line(region))
                    m = filepath_re.search(whole_line)
                    if m:
                        filepath = os.path.join(root, m.group(1))
                        if ( os.path.isfile(filepath) ):
                            m = filename_re.search(whole_line)
                            if m:
                                filename = m.group(1)
                                lineno = m.group(2)
                                print "Opening file '%s'" % (filepath + ":" + lineno)
                                sublime.active_window().open_file(filepath + ":" + lineno, sublime.ENCODED_POSITION)
                            else:
                                print "Something went wrong."
                                # print os.listdir(root)
                        else:
                            print "Unable to open file: %s" % (filepath)
            else:
                print "Unable to determine root for: %s" % (view.substr(view.line(0)))

class CscopeCommand(sublime_plugin.TextCommand):
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

            cscope_view.set_syntax_file("Packages/CscopeSublime/Lookup Results.hidden-tmLanguage")

            cscope_view.set_read_only(True)
            # self.view.window().show_quick_panel(options, self.on_done)
            # self.view.window().run_command("show_panel", {"panel": "output." + "cscope"})

    
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
            options.append("%(file)s:%(line)s - %(instance)s" % match)
        
        return options
    
    def match_output_line(self, line, mode):
        match = None
        output = None

        if mode == 0:
            match = re.match('(\S+?)\s+?(<global>)?\s+(\d+)\s+(.+)', line)
        elif mode == 1:
            match = re.match('(\S+?)\s+?\S+\s+(\d+)\s+(.+)', line)
 
        if match != None:
            if match.lastindex == 4:
                output = {
                        "file": match.group(1),
                        "line": match.group(3),
                        "instance": match.group(4)
                        }
            else:
                output = {
                        "file": match.group(1),
                        "line": match.group(2),
                        "instance": match.group(3)
                        }
        """
        if output != None:
            print output["file"]
        """

        return output
