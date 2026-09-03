' Starts Dossierbuild with no console window.
'
' The desktop shortcut points here rather than straight at launch.cmd: a .cmd
' always brings a console with it, and the only way to be rid of it is to have
' something else start it hidden. WScript.Shell's third Run argument is the
' window style -- 0 means "no window at all".
'
' The trade-off is that closing a window no longer stops the app, so the
' server keeps running in the background until stop.cmd, a sign-out or a
' restart. Opening the shortcut again just reuses it.

Dim shell, here
Set shell = CreateObject("WScript.Shell")
here = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
shell.Run """" & here & "launch.cmd"" /quiet", 0, False
