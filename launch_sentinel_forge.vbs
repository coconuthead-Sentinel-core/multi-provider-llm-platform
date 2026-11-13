' launch_sentinel_forge.vbs
'
' One-click launcher for the Sentinel Forge / Quantum Nexus Forge full
' stack. Starts the FastAPI server hidden (no console window) if it is
' not already running, waits up to 60s for it to come up, then opens
' the dashboard in the default browser.
'
' Wire this file to a Desktop shortcut — see
'   install_dashboard_shortcut.ps1 (sibling file).

Option Explicit

Dim oShell, fso, projectDir, logFile, dashboardUrl, healthUrl
Set oShell = CreateObject("WScript.Shell")
Set fso    = CreateObject("Scripting.FileSystemObject")

projectDir   = fso.GetParentFolderName(WScript.ScriptFullName)
logFile      = oShell.ExpandEnvironmentStrings("%TEMP%\sentinel-forge-uvicorn.log")
dashboardUrl = "http://127.0.0.1:8000/ui/dashboard.html"
healthUrl    = "http://127.0.0.1:8000/api/healthz"

' --- helper: is the server already responding? -------------------------
Function IsServerUp()
    Dim http, ok
    ok = False
    On Error Resume Next
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "GET", healthUrl, False
    http.Send
    If Err.Number = 0 Then
        If http.status >= 200 And http.status < 500 Then ok = True
    End If
    On Error GoTo 0
    IsServerUp = ok
End Function

' --- start server if needed --------------------------------------------
If Not IsServerUp() Then
    Dim cmd
    cmd = "cmd /c cd /d """ & projectDir & """ && py -3 -m uvicorn main:app --host 127.0.0.1 --port 8000 > """ & logFile & """ 2>&1"
    ' 0 = hidden window, False = do not wait
    oShell.Run cmd, 0, False

    ' Poll healthz for up to 60 seconds
    Dim i
    For i = 1 To 60
        WScript.Sleep 1000
        If IsServerUp() Then Exit For
    Next

    If Not IsServerUp() Then
        MsgBox "Sentinel Forge did not start within 60 seconds." & vbCrLf & _
               "Check the log file:" & vbCrLf & logFile, _
               vbExclamation, "Sentinel Forge Launcher"
        WScript.Quit 1
    End If
End If

' --- open dashboard in default browser ---------------------------------
' Run a URL string and Windows shell-executes it = opens default browser.
oShell.Run """" & dashboardUrl & """", 1, False
