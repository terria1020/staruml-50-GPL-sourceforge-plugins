// StarUML 5.0 COM bridge (Windows Script Host / JScript).
//
//   cscript //nologo //U staruml_bridge.js <command> [args...]
//
// Commands (all paths are Windows paths):
//   status                              running StarUML / current project
//   open <file.uml> [--force]           open a project (refuses to drop unsaved changes without --force)
//   reload [--force]                    re-open the current project from disk
//   save                                save the current project
//   list                                list diagrams of the current project
//   show <diagram> [package]            open a diagram tab
//   layout <diagram> [package]          run StarUML's automatic layout and save
//   export <diagram> <out.(jpg|bmp|emf|wmf)> [package]
//   import-fragment <file.mfj> [packagePath]   import a model fragment (default: selected package / Design Model)
//
// Output: one JSON object on stdout. Exit code 0 = ok, 1 = error.

function q(s) {
  s = String(s);
  var out = '"';
  for (var i = 0; i < s.length; i++) {
    var c = s.charAt(i), k = s.charCodeAt(i);
    if (c == '"' || c == '\\') out += '\\' + c;
    else if (k < 32 || k > 126) out += '\\u' + ('000' + k.toString(16)).slice(-4);  // ASCII-only output: no code page issues
    else out += c;
  }
  return out + '"';
}
function obj(o) {
  var parts = [];
  for (var k in o) {
    var v = o[k];
    if (v === null || v === undefined) parts.push(q(k) + ':null');
    else if (typeof v == 'number' || typeof v == 'boolean') parts.push(q(k) + ':' + v);
    else if (typeof v == 'object' && v.length !== undefined) {
      var a = [];
      for (var i = 0; i < v.length; i++) a.push(typeof v[i] == 'object' ? obj(v[i]) : q(v[i]));
      parts.push(q(k) + ':[' + a.join(',') + ']');
    } else if (typeof v == 'object') parts.push(q(k) + ':' + obj(v));
    else parts.push(q(k) + ':' + q(v));
  }
  return '{' + parts.join(',') + '}';
}
function done(o) { o.ok = true; WScript.Echo(obj(o)); WScript.Quit(0); }
function fail(msg) { WScript.Echo(obj({ ok: false, error: msg })); WScript.Quit(1); }

// Arguments may carry non-ASCII text escaped as \uXXXX (the Python wrapper does
// this) so they survive any console code page, including Wine's.
function unesc(s) {
  return String(s).replace(/\\u([0-9a-fA-F]{4})/g, function (m, h) { return String.fromCharCode(parseInt(h, 16)); });
}
var args = [];
var force = false;
for (var i = 0; i < WScript.Arguments.length; i++) {
  var a = unesc(WScript.Arguments(i));
  if (a == '--force') force = true; else args.push(a);
}
if (args.length == 0) fail('no command');
var cmd = args[0];

var app;
try { app = new ActiveXObject('StarUML.StarUMLApplication'); }
catch (e) { fail('cannot start/connect StarUML (is StarUML 5 installed and registered?): ' + e.message); }
var pm = app.ProjectManager;

function pathOf(m) {
  // (no try/break inside loops: Wine's JScript engine crashes on that pattern)
  var names = [];
  var guard = 0;
  while (m && guard < 64 && !m.IsKindOf('UMLProject')) {
    guard++;
    names.unshift(m.Name);
    if (m.IsKindOf('UMLDiagram')) m = m.DiagramOwner;
    else if (m.IsKindOf('UMLModelElement')) m = m.Namespace;
    else m = null;
  }
  return names.join('::');
}
function ownerPackage(d) {
  var o = d.DiagramOwner;
  while (o) {
    if (o.IsKindOf('UMLPackage') || o.IsKindOf('UMLProject')) return o;
    if (o.IsKindOf('UMLInteractionInstanceSet')) o = o.Context;
    else if (o.IsKindOf('UMLInteraction')) o = o.Context;
    else if (o.IsKindOf('UMLCollaborationInstanceSet') || o.IsKindOf('UMLCollaboration')) o = o.RepresentedClassifier ? o.RepresentedClassifier : o.Namespace;
    else if (o.IsKindOf('UMLStateMachine')) o = o.Context;
    else if (o.IsKindOf('UMLModelElement')) o = o.Namespace;
    else return null;
  }
  return null;
}
function allDiagrams() {
  var mc = app.MetaModel.FindMetaClass('UMLDiagram');
  var out = [];
  for (var i = 0; i < mc.GetInclusiveInstanceCount(); i++) out.push(mc.GetInclusiveInstanceAt(i));
  return out;
}
function findDiagram(name, pkg) {
  var ds = allDiagrams(), hits = [];
  for (var i = 0; i < ds.length; i++) {
    if (ds[i].Name != name) continue;
    if (pkg) { var p = ownerPackage(ds[i]); if (!p || pathOf(p) != pkg) continue; }
    hits.push(ds[i]);
  }
  if (hits.length == 0) fail('diagram not found: ' + name);
  if (hits.length > 1) fail('diagram name is ambiguous, pass the package path: ' + name);
  return hits[0];
}
function guardUnsaved() {
  if (pm.Modified && !force) fail('current project has unsaved changes (save it or pass --force)');
}

try {
  if (cmd == 'status') {
    done({ file: pm.FileName, modified: pm.Modified, title: app.GetProject().Title });
  } else if (cmd == 'open') {
    guardUnsaved();
    pm.CloseProject();
    pm.OpenProject(args[1]);
    done({ file: pm.FileName });
  } else if (cmd == 'reload') {
    var f = pm.FileName;
    if (!f) fail('no project file is open');
    guardUnsaved();
    pm.CloseProject();
    pm.OpenProject(f);
    done({ file: f });
  } else if (cmd == 'save') {
    pm.SaveProject();
    done({ file: pm.FileName });
  } else if (cmd == 'list') {
    var ds = allDiagrams(), list = [];
    for (var i = 0; i < ds.length; i++) {
      var p = ownerPackage(ds[i]);
      list.push({ name: ds[i].Name, type: ds[i].GetClassName(), package: p ? pathOf(p) : '' });
    }
    done({ file: pm.FileName, diagrams: list });
  } else if (cmd == 'show') {
    var d = findDiagram(args[1], args[2]);
    app.OpenDiagram(d);
    done({ diagram: d.Name });
  } else if (cmd == 'layout') {
    var d = findDiagram(args[1], args[2]);
    app.OpenDiagram(d);
    d.DiagramView.LayoutDiagram();
    pm.SaveProject();
    done({ diagram: d.Name, file: pm.FileName });
  } else if (cmd == 'export') {
    var d = findDiagram(args[1], args[3]);
    var out = args[2];
    app.OpenDiagram(d);
    WScript.Sleep(300);
    var ext = out.substring(out.lastIndexOf('.') + 1).toLowerCase();
    if (ext == 'jpg' || ext == 'jpeg') d.DiagramView.ExportDiagramAsJPEG(out);
    else if (ext == 'bmp') d.DiagramView.ExportDiagramAsBitmap(out);
    else if (ext == 'emf' || ext == 'wmf') d.DiagramView.ExportDiagramAsMetafile(out);
    else fail('unsupported image type: ' + ext);
    done({ diagram: d.Name, image: out });
  } else if (cmd == 'import-fragment') {
    var target = null;
    if (args[2]) {
      target = app.FindByPathname('::' + args[2]);
      if (!target) target = app.FindByPathname(args[2]);
      if (!target) fail('package not found: ' + args[2]);
    } else if (app.SelectionManager.GetSelectedModelCount() == 1 &&
               app.SelectionManager.GetSelectedModelAt(0).IsKindOf('UMLPackage')) {
      target = app.SelectionManager.GetSelectedModelAt(0);
    } else {
      var prj = app.GetProject();
      for (var i = 0; i < prj.GetOwnedElementCount(); i++) {
        var e = prj.GetOwnedElementAt(i);
        if (e.IsKindOf('UMLPackage') && (e.Name == 'Design Model' || !target)) target = e;
      }
      if (!target) fail('no package to import into');
    }
    pm.ImportModelFragment(target, args[1]);
    done({ package: pathOf(target), fragment: args[1] });
  } else {
    fail('unknown command: ' + cmd);
  }
} catch (e) {
  fail(cmd + ' failed: ' + (e.description || e.message || ('COM error ' + e.number)));
}
