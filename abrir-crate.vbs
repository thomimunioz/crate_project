' Lanzador de CRATE para el acceso directo de la barra de tareas.
' Corre el launcher de Python SIN ventana de consola: con un .cmd o un .lnk
' directo al .py aparece un cuadrado negro que queda abierto todo el rato.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
aqui = fso.GetParentFolderName(WScript.ScriptFullName)
py = "pythonw.exe"
sh.CurrentDirectory = aqui
sh.Run """" & py & """ """ & aqui & "\app\crate.py"" abrir", 0, False
