=========
Cscope
=========

A rendition of Vim's command-line mode for Sublime Text 2.

License
=======

This whole package is distributed under the MIT license.

Installation
============

1. Install Cscope (a Windows port can be found `here`_)
2. Generate a cscope database (cscope.out) in the root directory of your project
3. Check out the repo under``Packages`` or install via `Package Control` and restart Sublime Text.

.. _here: http://code.google.com/p/cscope-win32
.. _Package Control: http://wbond.net/sublime_packages/package_control

Update
======
* "Find C symbols":Match the symbols in other files.
* Add two mode:"Find the functions called by this function" and "Find the functions calling this function".
* Add "Goback"(ctr+shift+]) and "Forward"(ctr+shift+[) features to jump among the positions.
All the modification are based on fork from "https://github.com/ameyp/CscopeSublime".

Issues
======
In Mac OS, the python may not find the "cscope" even if you had been installed it well. 
The simple solution is, find the cscope.py, in line 98, cscope_arg_list = [ ...], change "cscope" to "{path}/cscope".({path} you can get from "which cscope".
