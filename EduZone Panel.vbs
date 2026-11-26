' Opens the EduZone panel (tools\panel) without any terminal window. Double-click to run.
' Already running? It just shows the panel again.
Dim shell, fso, root
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
On Error Resume Next
shell.Run "node """ & root & "\tools\panel\server.mjs"" --start", 0, False
If Err.Number <> 0 Then MsgBox "Node.js was not found. Install it from nodejs.org and try again.", 48, "EduZone Panel"
