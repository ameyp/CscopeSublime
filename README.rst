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
3. Check out the repo under``Packages`` and restart Sublime Text.

.. _here: http://code.google.com/p/cscope-win32

Overview
========
Only jump-to-definition works at the moment. Default keybinding is Ctrl+]. Rewinding to the previous position in the stack with Ctrl+t hasn't been added yet. The plugin will recursively search for the cscope database in parent directories of the currently open file until it either finds the database or reaches the root directory.