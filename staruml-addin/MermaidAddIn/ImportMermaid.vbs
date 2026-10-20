' Mermaid AddIn for StarUML 5.0 - import a Mermaid file into the selected package.
' Needs Python 3 and this repository; install.bat writes %APPDATA%\staruml5-mermaid\config.ini
Option Explicit

Dim App, Shell, FSO, PyCmd, RepoDir, MmdPath, Frag, LogFile, Target, Cmd, Rc, N, Pkg, I

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

Function FindTargetPackage()
  Dim Sel, Prj, E, J
  Set FindTargetPackage = Nothing
  If App.SelectionManager.GetSelectedModelCount = 1 Then
    Set Sel = App.SelectionManager.GetSelectedModelAt(0)
    If Sel.IsKindOf("UMLPackage") Then
      Set FindTargetPackage = Sel
      Exit Function
    End If
  End If
  Set Prj = App.GetProject()
  For J = 0 To Prj.GetOwnedElementCount - 1
    Set E = Prj.GetOwnedElementAt(J)
    If E.IsKindOf("UMLPackage") Then
      If FindTargetPackage Is Nothing Or E.Name = "Design Model" Then Set FindTargetPackage = E
    End If
  Next
End Function

PyCmd = ReadConfig("python", "python")
RepoDir = ReadConfig("repo", "")

Set Target = FindTargetPackage()
If Target Is Nothing Then
  MsgBox "Select a model or package in the Model Explorer first.", vbExclamation, "Mermaid AddIn"
Else
  MmdPath = InputBox("Mermaid file (.mmd / .md) to import into package '" & Target.Name & "':" & vbCrLf & vbCrLf & _
                     "Supported: classDiagram, sequenceDiagram, flowchart / graph", "Mermaid AddIn - Import")
  MmdPath = Replace(Trim(MmdPath), """", "")
  If MmdPath <> "" Then
    If Not FSO.FileExists(MmdPath) Then
      MsgBox "File not found: " & MmdPath, vbExclamation, "Mermaid AddIn"
    Else
      Frag = Shell.ExpandEnvironmentStrings("%TEMP%") & "\staruml5_mermaid_import.mfj"
      LogFile = Shell.ExpandEnvironmentStrings("%TEMP%") & "\staruml5_mermaid_import.log"
      If FSO.FileExists(Frag) Then FSO.DeleteFile Frag
      If RepoDir <> "" Then Shell.Environment("PROCESS")("PYTHONPATH") = RepoDir
      Cmd = "cmd /c " & PyCmd & " -m staruml5 fragment """ & MmdPath & """ -o """ & Frag & """ > """ & LogFile & """ 2>&1"
      Rc = Shell.Run(Cmd, 0, True)
      If Rc <> 0 Or Not FSO.FileExists(Frag) Then
        MsgBox "Conversion failed (exit " & Rc & "). See " & LogFile & vbCrLf & vbCrLf & ReadLog(LogFile), vbCritical, "Mermaid AddIn"
      Else
        N = Target.GetOwnedElementCount
        App.ProjectManager.ImportModelFragment Target, Frag
        If Target.GetOwnedElementCount > N Then
          Set Pkg = Target.GetOwnedElementAt(Target.GetOwnedElementCount - 1)
          App.SelectInModelExplorer Pkg
          OpenFirstDiagram Pkg
        End If
      End If
    End If
  End If
End If

Function ReadLog(Path)
  Dim F
  ReadLog = ""
  If FSO.FileExists(Path) Then
    Set F = FSO.OpenTextFile(Path, 1)
    If Not F.AtEndOfStream Then ReadLog = Left(F.ReadAll, 1500)
    F.Close
  End If
End Function

Sub OpenFirstDiagram(P)
  Dim K, C, J
  If P.GetOwnedDiagramCount > 0 Then
    App.OpenDiagram P.GetOwnedDiagramAt(0)
    Exit Sub
  End If
  ' sequence diagrams live in CollaborationInstanceSet > InteractionInstanceSet,
  ' activity diagrams in ActivityGraph: search all diagrams owned below P
  Dim MC, D
  Set MC = App.MetaModel.FindMetaClass("UMLDiagram")
  For K = MC.GetInclusiveInstanceCount - 1 To 0 Step -1
    Set D = MC.GetInclusiveInstanceAt(K)
    If InStr(D.Pathname, P.Pathname & "::") = 1 Then
      App.OpenDiagram D
      Exit Sub
    End If
  Next
End Sub
