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

Overview
========
Only global symbol lookup and jump to function definition work at the moment. Default keybinding is Ctrl/Super+\. Rewinding to the previous position in the stack with Ctrl+t hasn't been added yet. The plugin will recursively search for the cscope database in parent directories of the currently open file until it either finds the database or reaches the root directory.