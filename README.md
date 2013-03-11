# Cscope
A plugin to use Cscope for code navigation from inside Sublime Text 2.

## Features
- Global symbol lookup
- Global function-definition lookup

## Installation
- Install Cscope (a Windows port can be found [here](http://code.google.com/p/cscope-win32))
- Generate a cscope database (cscope.out) in the root directory of your project
- Check out the repo under your "Packages" directory or install via [Package Control](http://wbond.net/sublime_packages/package_control) and restart Sublime Text.

## Configuration
If you wish to change the way CscopeSublime behaves, you have two options:

- Modify the corresponding setting in the default CscopeSublime.sublime-settings file in the package's directory
- Add a setting in your `Settings - User` file prefixed with `CscopeSublime_`.
  For example, to modify the `display_outline` setting and set it to `false`, put the line `"CscopeSublime_display_outline": false` in your settings file.

## Keybindings
| ctrl/super + \ | Show Cscope options |
| ctrl+l,ctrl + s | Look up symbol under cursor |
| ctrl+l,ctrl + d | Look up definition under cursor |
| ctrl+l,ctrl + e | Look up the function under cursor callees |
| ctrl+l,ctrl + r | Look up the function under cursor callers |
| ctrl + shift + [ | jump back |
| ctrl + shift + ] | jump forward |

## Notes
The plugin will recursively search for the cscope database in parent directories of the currently open file until it either finds the database or reaches the root directory.

## License
This whole package is distributed under the MIT license.
