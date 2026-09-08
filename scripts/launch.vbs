' Starts Dossierbuild with no console window.
'
' The desktop shortcut points here rather than straight at launch.cmd: a .cmd
' always brings a console with it, and the only way to be rid of it is to have
' something else start it hidden. WScript.Shell's third Run argument is the
' window style -- 0 means "no window at all".
'
' There is nothing to close, and nothing that needs closing. The page
' heartbeats while it is open and says so when it goes; the server exits a few
' seconds later on its own (see dossier/api/lifetime.py). So the app leaves no
' window in the taskbar while it runs and no process behind when it is done --
' which is the whole reason there is no stop icon.

Dim shell, here
Set shell = CreateObject("WScript.Shell")
here = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
shell.Run """" & here & "launch.cmd"" /quiet", 0, False
