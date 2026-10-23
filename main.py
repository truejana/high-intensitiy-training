import csv
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.utils import platform

class HIT(App):
    def build(self):
        self.title = 'HIT Training'
        self.dbpath = Path(self.user_data_dir) / 'hit_training.db'
        self.conn = sqlite3.connect(str(self.dbpath))
        self.conn.execute('CREATE TABLE IF NOT EXISTS exercises (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)')
        self.conn.execute('CREATE TABLE IF NOT EXISTS sets (id INTEGER PRIMARY KEY, exercise_id INTEGER NOT NULL, performed_at TEXT NOT NULL, weight REAL NOT NULL, reps INTEGER NOT NULL, seconds INTEGER, FOREIGN KEY(exercise_id) REFERENCES exercises(id))')
        self.conn.commit()
        self.phase = 'bereit'; self.started = 0; self.elapsed = 0; self.measured = 0; self.target = 90
        self.tabs = TabbedPanel(do_default_tab=False, tab_width=105)
        self.pages = {}
        for name, builder in [('Training',self.training),('Übungen',self.exercises),('Verlauf',self.history),('Fortschritt',self.stats),('Daten',self.data)]:
            tab = TabbedPanelItem(text=name)
            sc = ScrollView(do_scroll_x=False)
            content = BoxLayout(orientation='vertical',spacing=8,padding=12,size_hint_y=None)
            content.bind(minimum_height=content.setter('height'))
            sc.add_widget(content); tab.add_widget(sc); self.tabs.add_widget(tab)
            self.pages[name]=content; builder(content)
        self.refresh()
        Clock.schedule_interval(self.tick, .1)
        return self.tabs
    def label(self,p,s,height=38):
        w=Label(text=s,size_hint_y=None,height=height,halign='left',valign='middle');w.bind(size=lambda a,b:setattr(a,'text_size',(a.width,None)));p.add_widget(w);return w
    def entry(self,p,hint,default=''):
        w=TextInput(text=default,hint_text=hint,multiline=False,size_hint_y=None,height=48);p.add_widget(w);return w
    def button(self,p,title,fn):
        b=Button(text=title,size_hint_y=None,height=48);b.bind(on_release=lambda *_:fn());p.add_widget(b);return b
    def message(self,s):
        self.status.text=s
    def training(self,p):
        self.label(p,'TRAININGSSATZ',48)
        self.ex=Spinner(text='Übung wählen',values=[],size_hint_y=None,height=48);p.add_widget(self.ex)
        self.ex.bind(text=lambda *_:self.last_set())
        self.last=self.label(p,'Noch kein Satz vorhanden',52)
        self.weight=self.entry(p,'Gewicht (kg)');self.reps=self.entry(p,'Wiederholungen');self.duration=self.entry(p,'Satzdauer (Sekunden, optional)')
        self.button(p,'Satz speichern',self.save)
        self.label(p,'HIT-SATZTIMER',48)
        self.goal=self.entry(p,'Zielzeit in Sekunden','90')
        self.phase_label=self.label(p,'Bereit · 10 s Vorlauf',42)
        self.clock_label=self.label(p,'00:00',70)
        self.delta=self.label(p,'Abweichung: —',44)
        for text,fn in [('Start',self.start),('Satz Ende',self.end),('Pause',self.pause),('Reset',self.reset)]:self.button(p,text,fn)
        self.status=self.label(p,'Bereit',64)
    def exercises(self,p):
        self.newname=self.entry(p,'Name der Übung / des Geräts')
        self.button(p,'Übung hinzufügen',self.add_ex)
        self.ex_select=Spinner(text='Übung wählen',size_hint_y=None,height=48);p.add_widget(self.ex_select)
        self.button(p,'Ausgewählte Übung umbenennen (Name oben)',self.rename_ex)
        self.button(p,'Ausgewählte Übung löschen (inklusive Sätze)',self.del_ex)
    def history(self,p):
        self.hist_filter=Spinner(text='Alle Übungen',size_hint_y=None,height=48);p.add_widget(self.hist_filter)
        self.hist_filter.bind(text=lambda *_:self.refresh_history())
        self.hist_select=Spinner(text='Satz auswählen',size_hint_y=None,height=48);p.add_widget(self.hist_select)
        self.button(p,'Ausgewählten Satz löschen',self.del_set)
        self.hist_text=self.label(p,'',500)
    def stats(self,p):
        self.stats_filter=Spinner(text='Übung wählen',size_hint_y=None,height=48);p.add_widget(self.stats_filter)
        self.stats_filter.bind(text=lambda *_:self.refresh_stats())
        self.stats_text=self.label(p,'',520)
    def data(self,p):
        self.label(p,'Alle Daten bleiben lokal auf diesem Gerät.',90)
        self.button(p,'CSV in App-Datenordner exportieren',self.export)
        self.button(p,'Datenbank im App-Datenordner sichern',self.backup)
        self.label(p,'Hinweis: Der App-Datenordner ist unter Android eventuell nicht direkt im Dateimanager zugänglich.',120)
    def names(self):return [r[0] for r in self.conn.execute('SELECT name FROM exercises ORDER BY name COLLATE NOCASE')]
    def refresh(self):
        names=self.names()
        for spinner in (self.ex,self.ex_select,self.stats_filter):
            spinner.values=names
            if spinner.text not in names:spinner.text=names[0] if names else 'Übung wählen'
        self.hist_filter.values=['Alle Übungen']+names
        if self.hist_filter.text not in self.hist_filter.values:self.hist_filter.text='Alle Übungen'
        self.last_set();self.refresh_history();self.refresh_stats()
    def exid(self,name):
        r=self.conn.execute('SELECT id FROM exercises WHERE name=?',(name,)).fetchone();return r[0] if r else None
    def add_ex(self):
        name=self.newname.text.strip()
        if not name:return self.message('Bitte einen Übungsnamen eingeben.')
        try:self.conn.execute('INSERT INTO exercises(name) VALUES (?)',(name,));self.conn.commit()
        except sqlite3.IntegrityError:return self.message('Übung existiert bereits.')
        self.newname.text='';self.refresh();self.ex.text=name;self.message('Übung angelegt.')
    def rename_ex(self):
        eid=self.exid(self.ex_select.text);name=self.newname.text.strip()
        if not eid or not name:return self.message('Übung und neuen Namen wählen.')
        try:self.conn.execute('UPDATE exercises SET name=? WHERE id=?',(name,eid));self.conn.commit()
        except sqlite3.IntegrityError:return self.message('Name bereits vorhanden.')
        self.newname.text='';self.refresh();self.message('Umbenannt.')
    def del_ex(self):
        eid=self.exid(self.ex_select.text)
        if not eid:return
        with self.conn:
            self.conn.execute('DELETE FROM sets WHERE exercise_id=?',(eid,));self.conn.execute('DELETE FROM exercises WHERE id=?',(eid,))
        self.refresh();self.message('Übung und Sätze gelöscht.')
    def save(self):
        eid=self.exid(self.ex.text)
        if not eid:return self.message('Zuerst Übung anlegen.')
        try:
            weight=float(self.weight.text.replace(',','.'));reps=int(self.reps.text);seconds=int(self.duration.text) if self.duration.text.strip() else None
            if not (0<=weight<=2000 and 1<=reps<=10000) or (seconds is not None and not 1<=seconds<=86400):raise ValueError
        except ValueError:return self.message('Gewicht, Wiederholungen oder Dauer ungültig.')
        self.conn.execute('INSERT INTO sets(exercise_id,performed_at,weight,reps,seconds) VALUES (?,?,?,?,?)',(eid,datetime.now().isoformat(timespec='seconds'),weight,reps,seconds));self.conn.commit()
        self.reps.text='';self.duration.text='';self.refresh();self.message('Satz gespeichert.')
    def last_set(self):
        if not hasattr(self,'last'):return
        r=self.conn.execute('SELECT performed_at,weight,reps FROM sets WHERE exercise_id=? ORDER BY performed_at DESC,id DESC LIMIT 1',(self.exid(self.ex.text),)).fetchone()
        self.last.text=f'Letzter Satz: {r[0][:10]} · {r[1]:g} kg × {r[2]}' if r else 'Noch kein Satz vorhanden'
    def refresh_history(self):
        if not hasattr(self,'hist_text'):return
        name=self.hist_filter.text
        sql='SELECT s.id,s.performed_at,e.name,s.weight,s.reps,s.seconds FROM sets s JOIN exercises e ON e.id=s.exercise_id'
        params=[]
        if name!='Alle Übungen' and self.exid(name):sql+=' WHERE s.exercise_id=?';params=[self.exid(name)]
        rows=self.conn.execute(sql+' ORDER BY s.performed_at DESC,s.id DESC LIMIT 500',params).fetchall()
        self.hist_map={f'{r[0]} · {r[2]} · {r[1][:16]}':r[0] for r in rows}
        self.hist_select.values=list(self.hist_map)
        self.hist_text.text='\n'.join(f'{r[1][:16]} | {r[2]} | {r[3]:g} kg × {r[4]}' + (f' · {r[5]} s' if r[5] else '') for r in rows[:22]) or 'Noch keine Sätze.'
    def del_set(self):
        sid=self.hist_map.get(self.hist_select.text)
        if sid:
            self.conn.execute('DELETE FROM sets WHERE id=?',(sid,));self.conn.commit();self.hist_select.text='Satz auswählen';self.refresh();self.message('Satz gelöscht.')
    def refresh_stats(self):
        if not hasattr(self,'stats_text'):return
        rows=self.conn.execute('SELECT performed_at,weight,reps FROM sets WHERE exercise_id=? ORDER BY performed_at DESC,id DESC',(self.exid(self.stats_filter.text),)).fetchall()
        if not rows:self.stats_text.text='Noch keine Trainingsdaten.';return
        lines=[f'Sätze: {len(rows)}',f'Höchstes Gewicht: {max(r[1] for r in rows):g} kg',f'Höchstes Satzvolumen: {max(r[1]*r[2] for r in rows):g} kg × Wdh.',f'Letzter Satz: {rows[0][1]:g} kg × {rows[0][2]} Wdh.','', 'Letzte 12 Sätze:']
        lines += [f'{r[0][:10]}: {r[1]:g} × {r[2]} = {r[1]*r[2]:g}' for r in rows[:12]]
        self.stats_text.text='\n'.join(lines)
    def export(self):
        path=Path(self.user_data_dir)/f'hit_export_{datetime.now():%Y%m%d_%H%M%S}.csv'
        with path.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f,delimiter=';');writer.writerow(['Datum und Uhrzeit','Übung','Gewicht kg','Wiederholungen','Satzdauer Sekunden'])
            writer.writerows(self.conn.execute('SELECT s.performed_at,e.name,s.weight,s.reps,s.seconds FROM sets s JOIN exercises e ON e.id=s.exercise_id ORDER BY s.performed_at,s.id'))
        self.message('CSV erstellt: '+str(path))
    def backup(self):
        path=Path(self.user_data_dir)/f'hit_backup_{datetime.now():%Y%m%d_%H%M%S}.db'
        with sqlite3.connect(str(path)) as target:self.conn.backup(target)
        self.message('Sicherung erstellt: '+str(path))
    def fmt(self,t):return f'{int(max(0,t))//60:02d}:{int(max(0,t))%60:02d}'
    def start(self):
        if self.phase=='pausiert':self.phase=self.paused;self.started=time.monotonic()-self.elapsed
        elif self.phase in ('bereit','fertig'):
            try:self.target=int(self.goal.text);assert 1<=self.target<=86400
            except (ValueError,AssertionError):return self.message('Zielzeit: 1 bis 86400 Sekunden.')
            self.phase='vorlauf';self.started=time.monotonic();self.measured=0;self.delta.text='Abweichung: —'
    def end(self):
        if self.phase!='satz':return
        self.measured=time.monotonic()-self.started;self.phase='nachlauf';self.started=time.monotonic()
    def pause(self):
        if self.phase not in ('vorlauf','satz','nachlauf'):return
        self.elapsed=time.monotonic()-self.started;self.paused=self.phase;self.phase='pausiert';self.phase_label.text='Pausiert · Start zum Fortsetzen'
    def reset(self):self.phase='bereit';self.measured=0;self.phase_label.text='Bereit · 10 s Vorlauf';self.clock_label.text='00:00';self.delta.text='Abweichung: —'
    def tick(self,dt):
        if self.phase not in ('vorlauf','satz','nachlauf'):return
        elapsed=time.monotonic()-self.started
        if self.phase=='vorlauf':
            if elapsed>=10:self.phase='satz';self.started+=10;elapsed=time.monotonic()-self.started
            else:self.phase_label.text='Vorlauf · Position einnehmen';self.clock_label.text=f'{max(0,10-int(elapsed))} s';return
        if self.phase=='satz':
            self.measured=elapsed;self.phase_label.text='SATZ LÄUFT · Satz Ende drücken';self.clock_label.text=self.fmt(elapsed)
            diff=round(elapsed)-self.target;self.delta.text=f'Abweichung: {diff:+d} s';return
        if self.phase=='nachlauf':
            if elapsed>=5:
                self.phase='fertig';self.phase_label.text='Fertig · Satzdauer übernommen';self.clock_label.text=self.fmt(self.measured);self.duration.text=str(max(1,round(self.measured)))
                self.delta.text=f'Abweichung: {round(self.measured)-self.target:+d} s'
            else:self.phase_label.text='Nachlauf · 5 Sekunden';self.clock_label.text=f'{max(0,5-int(elapsed))} s'
    def on_stop(self):self.conn.close()

if __name__=='__main__':HIT().run()
