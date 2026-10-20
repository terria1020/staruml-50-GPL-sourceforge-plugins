' Mermaid AddIn for StarUML 5.0 - export the selected diagram as Mermaid text (opens Notepad).
Option Explicit

Dim App, Shell, FSO, PyCmd, RepoDir, Sel, Dgm, OutFile, LogFile, Cmd, Rc, FileName

Set App = CreateObject("StarUML.StarUMLApplication")
Set Shell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

Function ReadConfig(Key, DefaultValue)
  Dim Path, F, Line, P
  ReadConfig = DefaultValue
  Path = Shell.ExpandEnvironmentStrings("%APPDATA%") & "\staruml5-mermaid\config.ini"
  If Not FSO.FileExists(Path) Then Exit Function
  Set F = FSO.OpenTextFile(Path, 1)
  Do While Not F.AtEndOfStream
    Line = Trim(F.ReadLine)
    P = InStr(Line, "=")
    If P > 0 Then
      If LCase(Trim(Left(Line, P - 1))) = LCase(Key) Then ReadConfig = Trim(Mid(Line, P + 1))
    End If
  Loop
  F.Close
End Function

PyCmd = ReadConfig("python", "python")
RepoDir = ReadConfig("repo", "")

Set Dgm = Nothing
If App.SelectionManager.GetSelectedModelCount = 1 Then
  Set Sel = App.SelectionManager.GetSelectedModelAt(0)
  If Sel.IsKindOf("UMLDiagram") Then Set Dgm = Sel
End If
If Dgm Is Nothing And App.GetOpenedDiagramCount > 0 Then Set Dgm = App.GetOpenedDiagramAt(App.GetOpenedDiagramCount - 1)

If Dgm Is Nothing Then
  MsgBox "Select a diagram in the Model Explorer first.", vbExclamation, "Mermaid AddIn"
Else
  FileName = App.ProjectManager.FileName
  If FileName = "" Then
    MsgBox "Save the project first.", vbExclamation, "Mermaid AddIn"
  Else
    If App.ProjectManager.Modified Then
      If MsgBox("The project has unsaved changes. Save now?", vbYesNo + vbQuestion, "Mermaid AddIn") = vbYes Then
        App.ProjectManager.SaveProject
      End If
    End If
    OutFile = Shell.ExpandEnvironmentStrings("%TEMP%") & "\" & SafeName(Dgm.Name) & ".mmd"
    LogFile = Shell.ExpandEnvironmentStrings("%TEMP%") & "\staruml5_mermaid_export.log"
    If RepoDir <> "" Then Shell.Environment("PROCESS")("PYTHONPATH") = RepoDir
    Cmd = "cmd /c " & PyCmd & " -m staruml5 export """ & FileName & """ """ & Dgm.Name & """ -o """ & OutFile & """ > """ & LogFile & """ 2>&1"
    Rc = Shell.Run(Cmd, 0, True)
    If Rc <> 0 Then
      MsgBox "Export failed (exit " & Rc & "). See " & LogFile, vbCritical, "Mermaid AddIn"
    Else
      Shell.Run "notepad """ & OutFile & """", 1, False
    End If
  End If
End If

Function SafeName(S)
  Dim Bad, J
  SafeName = S
  Bad = Array("\", "/", ":", "*", "?", """", "<", ">", "|")
  For J = 0 To UBound(Bad)
    SafeName = Replace(SafeName, Bad(J), "_")
  Next
End Function
