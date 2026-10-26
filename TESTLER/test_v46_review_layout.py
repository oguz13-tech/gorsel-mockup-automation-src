from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Layout(HTMLParser):
    def __init__(self):super().__init__();self.buttons=[];self.details=[];self.report_buttons=[];self.reports_closed=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='details':
            self.details.append(a.get('id'))
            if a.get('id')=='v46-reports':self.reports_closed='open' not in a
        if tag=='button':
            self.buttons.append(a)
            if 'v46-reports' in self.details:self.report_buttons.append(a)
    def handle_endtag(self,tag):
        if tag=='details':self.details.pop()

def test_controls_and_reports_keep_handlers():
    html=(ROOT/'SABLON_V2_MIMARI/templates/index.html').read_text()
    p=Layout();p.feed(html)
    assert 'btnAutoForeground' not in html
    handlers=[b.get('onclick') for b in p.buttons]
    assert handlers.index('showWorkingPreview()')==handlers.index('showOriginalPreview()')+1
    assert p.reports_closed
    reports={b.get('onclick') for b in p.report_buttons}
    assert {'runTemplateHealthScan()','openLastTemplateHealthReport()','openTemplateHealthHistory()',
            'runWorkspaceConsistencyScan()','openLastWorkspaceConsistencyReport()',
            'openWorkspaceConsistencyHistory()','v46BulkAlignmentReport()'}<=reports
    assert handlers.count('restoreOriginal()')==1
    assert '/api/templates/foreground_detect' in (ROOT/'SABLON_V2_MIMARI/app.py').read_text()
