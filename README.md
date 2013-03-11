# Cscope
A plugin to use Cscope for code navigation from inside Sublime Text 2.

## Features
1. Global symbol lookup
2. Global function-definition lookup

## Installation
1. Install Cscope (a Windows port can be found [here](http://code.google.com/p/cscope-win32))
2. Generate a cscope database (cscope.out) in the root directory of your project
3. Check out the repo under your "Packages" directory or install via [Package Control](http://wbond.net/sublime_packages/package_control) and restart Sublime Text.

## Configuration
If you wish to change the way CscopeSublime behaves, you have two options:

1. Modify the corresponding setting in the default CscopeSublime.sublime-settings file in the package's directory
2. Add a setting in your `Settings - User` file prefixed with `CscopeSublime_`.
   For example, to modify the `display_outline` setting and set it to `false`, put the line `"CscopeSublime_display_outline": false` in your settings file.

## Keybindings
<table>
  <tr>
    <td>ctrl/super + \\</td><td>Show Cscope options</td>
  </tr>
  <tr>
    <td>ctrl + l, ctrl + s</td><td>Look up symbol under cursor</td>
  </tr>
  <tr>
    <td>ctrl + l, ctrl + d</td><td>Look up definition under cursor</td>
  </tr>
  <tr>
    <td>ctrl + l, ctrl + e</td><td>Look up functions called by the function under the cursor</td>
  </tr>
  <tr>
    <td>ctrl + l, ctrl + r</td><td>Look up functions calling the function under the cursor</td>
  </tr>
  <tr>
    <td>ctrl + shift + [</td><td>Jump back</td>
  </tr>
  <tr>
    <td>ctrl + shift + ]</td><td>Jump forward</td>
  </tr>
</table>

## Notes
The plugin will recursively search for the cscope database in parent directories of the currently open file until it either finds the database or reaches the root directory.

## License
This whole package is distributed under the MIT license.
