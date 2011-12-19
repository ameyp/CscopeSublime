import sublime, sublime_plugin
import os
import re
import subprocess

class JumpToDefinitionCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
        self.view = view
        self.database = None
        #self.panel  = self.view.window().get_output_panel("cscope")

    def run(self, edit):
        # self.word_separators = self.view.settings().get('word_separators')
        # print self.view.sel()
        # self.view.insert(edit, 0, "Hello, World!")
        if self.database == None:
            self.find_database()

        newline = ''
        if sublime.platform() == "windows":
            newline = '\r\n'
        else:
            newline = '\n'

        one = self.view.sel()[0].a
        two = self.view.sel()[0].b
        self.view.sel().add(sublime.Region(one,
                                           two))
        for sel in self.view.sel():
            word = self.view.substr(self.view.word(sel))
            #print "Word: ", word
            # 0 ==> C symbol
            # 1 ==> function definition
            # 2 ==> functions called by this function
            # 3 ==> functions calling this function
            # 4 ==> text string
            # 5 ==> egrep pattern
            # 6 ==> files
            arg_list = ['cscope', '-dL', '-f', self.database, '-1' + word]
            if (sublime.platform() == "windows"):
                self.proc = subprocess.Popen(arg_list,
                                         creationflags=0x08000000,
                                         shell=False,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
            else:
                self.proc = subprocess.Popen(arg_list,
                                         shell=False,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
            output = self.proc.communicate()[0].split(newline)
            print output
            self.matches = []
            for i in output:
                match = re.match('(\S+?)\s+?' + word + '\s+(\d+)\s+(.+)', i)
                if match != None:
                    self.matches.append({
                                    "file": match.group(1),
                                    "line": match.group(2),
                                    "instance": match.group(3)
                                    })
                    #print "File ", match.group(1), ", Line ", match.group(2), ", Instance ", match.group(3)
 
            #self.view.window().run_command("show_overlay", {"overlay": "goto", "text": "@"})
            options = []
            for match in self.matches:
                options.append("%(file)s:%(line)s - %(instance)s" % match)
            self.view.window().show_quick_panel(options, self.on_done)
            #self.view.window().run_command("show_panel", {"panel": "output." + "cscope"})
    
    def on_done(self, picked):
        if picked == -1:
            return
        
        line = self.matches[picked]["line"]
        filepath = os.path.join(self.root, self.matches[picked]["file"])
        if os.path.isfile(filepath):
            sublime.active_window().open_file(filepath + ":" + line, sublime.ENCODED_POSITION)

    def find_database(self):
        cdir = os.path.dirname(self.view.file_name())
        while cdir != os.path.dirname(cdir):
            if ("cscope.out" in os.listdir(cdir)):
                self.database = os.path.join(cdir, "cscope.out")
                self.root = cdir
                #print "Database found: ", self.database
                break
            cdir = os.path.dirname(cdir)
        
        if self.database == None:
            sublime.status_message("Could not find cscope database: cscope.out")
