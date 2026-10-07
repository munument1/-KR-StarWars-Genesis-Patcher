"""Windows UI for the local Genesis Korean patcher test build."""
import argparse,json,os,queue,sys,threading,uuid
from pathlib import Path
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
from installer_backend import generate,apply,restore,sha,safe

def package_dir():
    return Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'installer-data'

class App:
    def __init__(self,root):
        self.root=root;self.events=queue.Queue();self.stage=None;self.busy=False
        root.title('Star Wars Genesis 한글 패처 · v0.2.0 시험판');root.geometry('780x560');root.minsize(700,500)
        root.protocol('WM_DELETE_WINDOW',self.close)
        style=ttk.Style();style.theme_use('clam')
        self.game=tk.StringVar();self.state=tk.StringVar(value='Genesis의 Game 폴더를 선택해 주세요.')
        frame=ttk.Frame(root,padding=20);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='STAR WARS GENESIS  ·  한국어 패치',font=('맑은 고딕',17,'bold')).pack(anchor='w')
        ttk.Label(frame,text='8.8.32용 v0.2.0 시험판 · 기존 한패 활용 + 제네시스 용어 보정 · Pretendard 한글 폰트',wraplength=720).pack(anchor='w',pady=(8,5))
        ttk.Label(frame,text='AI·Codex 번역 검토와 메뉴·한글 폰트·행성 이름 HUD 출력 확인을 반영했습니다. 전체 퀘스트 검증은 진행 전입니다.',wraplength=720).pack(anchor='w',pady=(0,16))
        row=ttk.Frame(frame);row.pack(fill='x')
        self.entry=ttk.Entry(row,textvariable=self.game);self.entry.pack(side='left',fill='x',expand=True)
        self.browse=ttk.Button(row,text='폴더 선택',command=self.choose);self.browse.pack(side='right',padx=(8,0))
        ttk.Label(frame,textvariable=self.state,wraplength=720).pack(anchor='w',pady=12)
        self.log=tk.Text(frame,height=13,wrap='word',state='disabled');self.log.pack(fill='both',expand=True)
        buttons=ttk.Frame(frame);buttons.pack(fill='x',pady=(14,0))
        self.prepare_button=ttk.Button(buttons,text='검사하고 패치 생성',command=self.prepare);self.prepare_button.pack(side='left')
        self.apply_button=ttk.Button(buttons,text='백업 후 적용',command=self.install,state='disabled');self.apply_button.pack(side='left',padx=8)
        self.restore_button=ttk.Button(buttons,text='백업 복원',command=self.undo);self.restore_button.pack(side='right')
        self.game.trace_add('write',self.path_changed)
        root.after(100,self.poll)
    def choose(self):
        selected=filedialog.askdirectory(title='Genesis의 Game 폴더 선택')
        if selected:self.game.set(selected);self.stage=None;self.apply_button.configure(state='disabled')
    def path_changed(self,*args):
        if not self.busy:self.stage=None;self.apply_button.configure(state='disabled')
    def write(self,text):
        self.log.configure(state='normal');self.log.insert('end',text+'\n');self.log.see('end');self.log.configure(state='disabled')
    def run(self,kind,action):
        if self.busy:return
        self.busy=True
        for button in (self.browse,self.prepare_button,self.apply_button,self.restore_button):button.configure(state='disabled')
        self.entry.configure(state='disabled')
        def worker():
            try:self.events.put(('done',kind,action()))
            except Exception as e:self.events.put(('error',kind,str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def progress(self,text):self.events.put(('progress',text))
    def prepare(self):
        if not self.game.get():return
        game=self.game.get();base=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'GenesisKRPatcher'/'staging'
        self.stage=base/uuid.uuid4().hex;self.state.set('파일 검사 및 패치 생성 중…')
        self.run('prepare',lambda:generate(game,package_dir(),self.stage,progress=self.progress))
    def install(self):
        if self.stage is None:return
        self.state.set('백업 및 적용 중…')
        self.run('apply',lambda:apply(self.stage,progress=self.progress))
    def undo(self):
        base=Path(self.game.get())/'.genesis-kr-backups' if self.game.get() else None
        selected=filedialog.askopenfilename(title='복원할 백업의 journal.json 선택',initialdir=str(base) if base else None,filetypes=[('백업 기록','journal.json')])
        if selected:
            self.state.set('백업 복원 중…');self.run('restore',lambda:restore(Path(selected).parent,progress=self.progress))
    def poll(self):
        try:
            while True:
                event=self.events.get_nowait()
                if event[0]=='progress':self.write(event[1]);continue
                self.busy=False;kind=event[1]
                for button in (self.browse,self.prepare_button,self.restore_button):button.configure(state='normal')
                self.entry.configure(state='normal');self.apply_button.configure(state='disabled')
                if event[0]=='error':
                    self.state.set('작업이 중단됐습니다.');self.write(event[2]);messagebox.showerror('작업 중단',event[2]);continue
                if kind=='prepare':
                    n=sum(r['status']=='prepared' for r in event[2]['operations'])
                    self.state.set(f'{n}개 파일 준비 완료. 적용 버튼을 누르면 원본 백업 후 설치합니다.')
                    self.write('생성 위치: '+str(self.stage))
                    if n:self.apply_button.configure(state='normal')
                elif kind=='apply':
                    self.state.set('적용 완료. 메뉴와 대화창의 한글 출력을 확인해 주세요.');self.write('백업 위치: '+str(event[2]));self.stage=None
                else:self.state.set('원본 복원 완료.');self.stage=None
        except queue.Empty:pass
        self.root.after(100,self.poll)
    def close(self):
        if self.busy:
            messagebox.showinfo('작업 진행 중','백업·파일 작업이 끝난 뒤 창을 닫아 주세요.');return
        self.root.destroy()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-check');parser.add_argument('--generate-only',nargs=2,metavar=('GAME','STAGE'))
    args=parser.parse_args()
    if args.self_check:
        package=package_dir();manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8'))
        for r in manifest['operations']:
            for blob_id in [r['blob']]+[entry['blob'] for entry in r.get('upgrade_from',[])]:
                if sha(safe(package,'blobs/'+blob_id).read_bytes())!=blob_id:raise ValueError('Embedded data corrupted')
        Path(args.self_check).write_text(json.dumps({'operations':len(manifest['operations']),'embedded_payload_verified':True,'release_state':manifest['release_state']}),encoding='utf-8');return
    if args.generate_only:
        generate(args.generate_only[0],package_dir(),args.generate_only[1]);return
    root=tk.Tk();App(root);root.mainloop()
if __name__=='__main__':main()
