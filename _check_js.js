// temp verifier: syntax-check inline <script> blocks of html files
var fs = require('fs'), vm = require('vm');
var files = process.argv.slice(2);
var bad = 0;
files.forEach(function (f) {
  var html = fs.readFileSync(f, 'utf8');
  var re = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi, m, i = 0;
  while ((m = re.exec(html)) !== null) {
    i++;
    try { new vm.Script(m[1], { filename: f + '#inline' + i }); }
    catch (e) { bad++; console.log('FAIL ' + f + ' inline#' + i + ': ' + e.message); }
  }
  console.log((bad ? '' : 'ok   ') + f + ' -> ' + i + ' inline script block(s) checked');
});
process.exit(bad ? 1 : 0);
