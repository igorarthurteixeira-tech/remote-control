from flask import Flask, request, jsonify, render_template, render_template_string
import pyautogui
import pyperclip
import socket
import threading
import subprocess
import sys
import os
import json
import ctypes


def _resource_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _data_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


_RSRC       = _resource_dir()
_DATA       = _data_dir()
_log_path   = None
_panel_root = None

INSTALL_DIR = os.path.join(
    os.environ.get('ProgramFiles', 'C:\\Program Files'), 'RemoteControl'
)
_EXE_NAME = 'RemoteControlServer.exe'


def _is_installed():
    if not getattr(sys, 'frozen', False):
        return True
    installed = os.path.normcase(os.path.join(INSTALL_DIR, _EXE_NAME))
    current   = os.path.normcase(os.path.abspath(sys.executable))
    return current == installed


def _do_install():
    import shutil, time
    print(f'Primeira execução — instalando em {INSTALL_DIR}...')

    # Encerra instância anterior (exclui o processo atual)
    subprocess.run(
        ['taskkill', '/F', '/FI', f'IMAGENAME eq {_EXE_NAME}', '/FI', f'PID ne {os.getpid()}'],
        capture_output=True
    )
    time.sleep(1)

    os.makedirs(INSTALL_DIR, exist_ok=True)
    for old in ['templates', 'static', '_internal', '_DATA']:
        p = os.path.join(INSTALL_DIR, old)
        if os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True)
    dst = os.path.join(INSTALL_DIR, _EXE_NAME)
    shutil.copy2(sys.executable, dst)
    print('Executável instalado.')

    # Atalho na área de trabalho
    desktop = os.path.join(
        os.environ.get('USERPROFILE', os.path.expanduser('~')), 'Desktop'
    )
    lnk = os.path.join(desktop, 'Remote Control.lnk')
    ps  = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$sc = $ws.CreateShortcut("{lnk}"); '
        f'$sc.TargetPath = "{dst}"; '
        f'$sc.IconLocation = "{dst},0"; '
        f'$sc.Description = "Remote Control Server"; '
        f'$sc.WorkingDirectory = "{INSTALL_DIR}"; '
        f'$sc.Save()'
    )
    subprocess.run(['powershell', '-Command', ps], capture_output=True)
    print('Atalho criado na área de trabalho.')

    subprocess.Popen([dst])
    sys.exit(0)

app = Flask(__name__,
            template_folder=os.path.join(_DATA, 'templates'),
            static_folder=os.path.join(_DATA, 'static'))
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

KEY_MAP = {
    'win':   'winleft',
    'esc':   'escape',
    'enter': 'return',
}


# ── Rotas principais ────────────────────────────────────────────────────────

def _force_show_cursor():
    try:
        user32 = ctypes.windll.user32
        for _ in range(10):
            if user32.ShowCursor(True) >= 0:
                break
    except Exception as e:
        print(f'Aviso ShowCursor: {e}')


@app.route('/')
def index():
    # "Ocultar ponteiro ao digitar" do Windows deixa o cursor sumido depois que
    # o celular conecta e manda teclas; força ele a reaparecer.
    _force_show_cursor()
    return render_template('index.html')


@app.route('/ping')
def ping():
    return jsonify(app='remote-control', ok=True)


@app.route('/qr')
def qr_page():
    ip         = get_local_ip()
    url        = f'http://{ip}:5000'
    static_dir = os.path.join(_DATA, 'static')
    has_apk_qr = os.path.exists(os.path.join(static_dir, 'qr_apk.png'))
    return render_template_string('''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>QR Code — Remote Control</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #111827; color: #f3f4f6;
      font-family: system-ui, sans-serif;
      min-height: 100dvh; display: flex; flex-direction: column;
      align-items: center; justify-content: center; gap: 32px; padding: 24px;
    }
    h1 { font-size: 18px; font-weight: 600; }
    .card { display: flex; flex-direction: column; align-items: center; gap: 10px; }
    .card-label {
      font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
      text-transform: uppercase; color: #6b7280;
    }
    .card-label.green { color: #059669; }
    img { border-radius: 12px; width: min(220px, 72vw); height: auto; }
    img.purple { border: 4px solid #7c3aed; }
    img.green  { border: 4px solid #059669; }
    p   { font-size: 13px; color: #9ca3af; letter-spacing: 0.03em; }
    .hint { font-size: 12px; color: #6b7280; text-align: center; max-width: 280px; line-height: 1.5; }
    .divider { width: 1px; height: 60px; background: #374151; }
    .row { display: flex; flex-direction: row; align-items: center; gap: 28px; flex-wrap: wrap; justify-content: center; }
  </style>
</head>
<body>
  <h1>Remote Control</h1>
  <div class="row">
    <div class="card">
      <span class="card-label">Controlar PC</span>
      <img class="purple" src="/static/qr.png" alt="QR Controle">
      <p>{{ url }}</p>
    </div>
    {% if has_apk_qr %}
    <div class="divider"></div>
    <div class="card">
      <span class="card-label green">Baixar APK Android</span>
      <img class="green" src="/static/qr_apk.png" alt="QR APK">
      <p>{{ url }}/app.apk</p>
    </div>
    {% endif %}
  </div>
  <span class="hint">Escaneie com a câmera do celular</span>
</body>
</html>''', url=url, has_apk_qr=has_apk_qr)


def _find_apk():
    import glob
    for d in [_RSRC, _DATA]:
        apks = glob.glob(os.path.join(d, '*.apk'))
        if apks:
            return apks[0]
    return None


@app.route('/favicon.ico')
def favicon():
    from flask import send_from_directory
    return send_from_directory(os.path.join(_DATA, 'static'), 'favicon.ico', mimetype='image/x-icon')


@app.route('/has-apk')
def has_apk():
    return jsonify(available=_find_apk() is not None)


@app.route('/app.apk')
def serve_apk():
    from flask import send_file
    path = _find_apk()
    if not path:
        return 'APK não encontrado', 404
    return send_file(path, as_attachment=True, download_name='RemoteControl.apk')


@app.route('/launch', methods=['POST'])
def launch():
    data    = request.json
    url     = data.get('url', '')
    browser = data.get('browser', 'default')
    if not url:
        return jsonify(ok=False)
    try:
        if browser == 'chrome':
            subprocess.Popen(f'start chrome "{url}"', shell=True)
        elif browser == 'edge':
            subprocess.Popen(f'start msedge "{url}"', shell=True)
        elif browser == 'firefox':
            subprocess.Popen(f'start firefox "{url}"', shell=True)
        else:
            subprocess.Popen(f'start "" "{url}"', shell=True)
        return jsonify(ok=True)
    except Exception as e:
        print(f'Erro launch: {e}')
        return jsonify(ok=False)


@app.route('/mouse/move', methods=['POST'])
def mouse_move():
    data = request.json
    pyautogui.moveRel(data.get('dx', 0), data.get('dy', 0))
    return jsonify(ok=True)


@app.route('/mouse/click', methods=['POST'])
def mouse_click():
    data   = request.json
    button = data.get('button', 'left')
    clicks = 2 if data.get('double') else 1
    pyautogui.click(button=button, clicks=clicks)
    return jsonify(ok=True)


@app.route('/mouse/down', methods=['POST'])
def mouse_down():
    button = request.json.get('button', 'left')
    pyautogui.mouseDown(button=button)
    return jsonify(ok=True)


@app.route('/mouse/up', methods=['POST'])
def mouse_up():
    button = request.json.get('button', 'left')
    pyautogui.mouseUp(button=button)
    _force_show_cursor()
    return jsonify(ok=True)


@app.route('/mouse/scroll', methods=['POST'])
def mouse_scroll():
    pyautogui.scroll(request.json.get('amount', 3))
    return jsonify(ok=True)


@app.route('/key', methods=['POST'])
def press_key():
    raw = request.json.get('key', '')
    if '+' in raw:
        parts = [KEY_MAP.get(p, p) for p in raw.split('+')]
        pyautogui.hotkey(*parts)
    else:
        pyautogui.press(KEY_MAP.get(raw, raw))
    return jsonify(ok=True)


@app.route('/type', methods=['POST'])
def type_text():
    text = request.json.get('text', '')
    if text:
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
    return jsonify(ok=True)


# ── Monitores (modo cinema) ─────────────────────────────────────────────────

MONITOR_SCRIPT = os.path.join(_RSRC, 'monitor_control.ps1')


def _run_monitor_script(args):
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', MONITOR_SCRIPT] + args,
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if not result.stdout.strip():
            return {'ok': False, 'error': result.stderr.strip() or 'sem saida do script'}
        return json.loads(result.stdout)
    except Exception as e:
        return {'ok': False, 'error': str(e)}


@app.route('/displays', methods=['GET'])
def list_displays():
    return jsonify(_run_monitor_script(['-Action', 'list']))


@app.route('/displays/set', methods=['POST'])
def set_display():
    data   = request.json or {}
    device = data.get('device', '')
    state  = data.get('state', '')
    if not device or state not in ('on', 'off'):
        return jsonify(ok=False, error='parametros "device" e "state" (on/off) sao obrigatorios'), 400
    return jsonify(_run_monitor_script(['-Action', 'set', '-Device', device, '-State', state]))


# ── Utilitários ─────────────────────────────────────────────────────────────

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


def make_app_icon(size):
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    s   = size / 64
    d.ellipse([int(2*s), int(2*s), int(62*s), int(62*s)], fill='#7c3aed')
    d.arc([int(14*s), int(10*s), int(50*s), int(46*s)], 210, 330, fill='white', width=max(3, int(5*s)))
    d.arc([int(22*s), int(18*s), int(42*s), int(38*s)], 210, 330, fill='white', width=max(2, int(4*s)))
    d.ellipse([int(28*s), int(34*s), int(36*s), int(42*s)], fill='white')
    return img


def generate_static_assets(ip, port):
    import shutil
    static_dir = os.path.join(_DATA, 'static')
    os.makedirs(static_dir, exist_ok=True)

    if getattr(sys, 'frozen', False):
        bundled_templates = os.path.join(_RSRC, 'templates')
        data_templates    = os.path.join(_DATA, 'templates')
        os.makedirs(data_templates, exist_ok=True)
        for fname in os.listdir(bundled_templates):
            dst_file = os.path.join(data_templates, fname)
            if not os.path.exists(dst_file):
                shutil.copy2(os.path.join(bundled_templates, fname), dst_file)

        bundled_static = os.path.join(_RSRC, 'static')
        for fname in ('manifest.json', 'sw.js'):
            src = os.path.join(bundled_static, fname)
            dst = os.path.join(static_dir, fname)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)

    src_icon = os.path.join(_RSRC, 'static', 'app-icon-src.png')
    for sz in [32, 192, 512]:
        path = os.path.join(static_dir, f'icon-{sz}.png')
        if not os.path.exists(path):
            if os.path.exists(src_icon):
                from PIL import Image
                Image.open(src_icon).resize((sz, sz), Image.LANCZOS).save(path)
            else:
                make_app_icon(sz).save(path)

    favicon = os.path.join(static_dir, 'favicon.ico')
    if not os.path.exists(favicon):
        if os.path.exists(src_icon):
            from PIL import Image
            Image.open(src_icon).resize((32, 32), Image.LANCZOS).save(favicon, format='ICO', sizes=[(32, 32)])
        else:
            make_app_icon(32).save(favicon, format='ICO', sizes=[(32, 32)])

    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(f'http://{ip}:{port}')
        qr.make(fit=True)
        qr.make_image(fill_color='black', back_color='white').save(
            os.path.join(static_dir, 'qr.png'))
    except Exception as e:
        print(f'Aviso QR: {e}')

    if _find_apk():
        try:
            import qrcode
            qr2 = qrcode.QRCode(version=1, box_size=8, border=2)
            qr2.add_data(f'http://{ip}:{port}/app.apk')
            qr2.make(fit=True)
            qr2.make_image(fill_color='black', back_color='white').save(
                os.path.join(static_dir, 'qr_apk.png'))
        except Exception as e:
            print(f'Aviso QR APK: {e}')


# ── Iniciar com o Windows ────────────────────────────────────────────────────

AUTOSTART_TASK_NAME = 'RemoteControlAutostart'


def is_autostart_enabled():
    result = subprocess.run(
        ['schtasks', '/query', '/tn', AUTOSTART_TASK_NAME],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return result.returncode == 0


def enable_autostart():
    exe = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
    subprocess.run(
        ['schtasks', '/create', '/tn', AUTOSTART_TASK_NAME,
         '/tr', f'"{exe}"', '/sc', 'onlogon', '/rl', 'highest', '/f'],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )


def disable_autostart():
    subprocess.run(
        ['schtasks', '/delete', '/tn', AUTOSTART_TASK_NAME, '/f'],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )


# ── Bandeja do sistema ───────────────────────────────────────────────────────

def run_tray(ip, port):
    import pystray

    def show_panel(icon, item):
        if _panel_root:
            _panel_root.deiconify()
            _panel_root.lift()
            _panel_root.focus_force()

    def show_ip(icon, item):
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, f'Abra no celular:\n\nhttp://{ip}:{port}', 'Remote Control', 0x40)

    def show_qr(icon, item):
        from PIL import Image
        qr_path = os.path.join(_DATA, 'static', 'qr.png')
        if os.path.exists(qr_path):
            Image.open(qr_path).show()

    def restart(icon, item):
        icon.stop()
        import time
        time.sleep(0.6)
        if getattr(sys, 'frozen', False):
            subprocess.Popen([sys.executable], cwd=os.path.dirname(sys.executable))
        else:
            subprocess.Popen([sys.executable, os.path.abspath(__file__)],
                             cwd=os.path.dirname(os.path.abspath(__file__)))
        os._exit(0)

    def stop(icon, item):
        icon.stop()
        os._exit(0)

    def toggle_autostart(icon, item):
        if is_autostart_enabled():
            disable_autostart()
        else:
            enable_autostart()
        icon.update_menu()

    def uninstall(icon, item):
        import ctypes, shutil, time
        resp = ctypes.windll.user32.MessageBoxW(
            0,
            'Deseja desinstalar o Remote Control?\n\nIsso removerá o programa e todos os arquivos.',
            'Desinstalar Remote Control',
            0x04 | 0x30  # MB_YESNO | MB_ICONWARNING
        )
        if resp != 6:  # IDYES
            return
        icon.stop()
        time.sleep(0.5)
        disable_autostart()
        desktop = os.path.join(os.environ.get('USERPROFILE', os.path.expanduser('~')), 'Desktop')
        lnk = os.path.join(desktop, 'Remote Control.lnk')
        if os.path.exists(lnk):
            os.remove(lnk)
        # Agenda remoção das pastas após o processo sair
        script = (
            f'Start-Sleep -Seconds 2; '
            f'Remove-Item -Recurse -Force "{INSTALL_DIR}" -ErrorAction SilentlyContinue; '
            f'Remove-Item -Recurse -Force "C:\\ProgramData\\RemoteControl" -ErrorAction SilentlyContinue'
        )
        subprocess.Popen(['powershell', '-WindowStyle', 'Hidden', '-Command', script])
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem(f'http://{ip}:{port}', show_ip, default=True),
        pystray.MenuItem('Abrir painel',      show_panel),
        pystray.MenuItem('Mostrar QR Code',   show_qr),
        pystray.MenuItem('Iniciar com o Windows', toggle_autostart,
                          checked=lambda item: is_autostart_enabled()),
        pystray.MenuItem('Reiniciar servidor', restart),
        pystray.MenuItem('Parar servidor',     stop),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Desinstalar',        uninstall),
    )

    icon = pystray.Icon('remote-control', make_app_icon(64), 'Remote Control', menu)
    icon.notify(f'Abra no celular: http://{ip}:{port}', 'Remote Control iniciado')
    icon.run_detached()


# ── Painel Windows (tkinter) ─────────────────────────────────────────────────

def run_panel(ip, port):
    global _panel_root
    import tkinter as tk
    from tkinter import scrolledtext
    import time as _t

    BG     = '#111827'
    BG2    = '#1f2937'
    BDR    = '#374151'
    FG     = '#f3f4f6'
    FGMUT  = '#6b7280'
    PURPLE = '#7c3aed'
    GREEN  = '#059669'

    root = tk.Tk()
    _panel_root = root
    root.title('Remote Control — Painel')
    root.geometry('900x560')
    root.minsize(700, 420)
    root.configure(bg=BG)

    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    # ── Cabeçalho ───────────────────────────────────────────
    hdr = tk.Frame(root, bg=BG2, pady=9, padx=14)
    hdr.pack(fill='x')
    tk.Label(hdr, text='●', font=('Segoe UI', 15), fg='#22c55e', bg=BG2).pack(side='left')
    tk.Label(hdr, text='  Remote Control',
             font=('Segoe UI', 13, 'bold'), fg=FG, bg=BG2).pack(side='left')
    tk.Label(hdr, text=f'  ·  http://{ip}:{port}',
             font=('Segoe UI', 11), fg=FGMUT, bg=BG2).pack(side='left')
    tk.Frame(root, bg=BDR, height=1).pack(fill='x')

    body = tk.Frame(root, bg=BG)
    body.pack(fill='both', expand=True)

    # ── Sidebar ──────────────────────────────────────────────
    left = tk.Frame(body, bg=BG2, width=240)
    left.pack(side='left', fill='y')
    left.pack_propagate(False)
    tk.Frame(body, bg=BDR, width=1).pack(side='left', fill='y')

    def sec(txt):
        tk.Label(left, text=txt, font=('Segoe UI', 8, 'bold'),
                 fg=FGMUT, bg=BG2, anchor='w', padx=12).pack(fill='x', pady=(12, 2))
        tk.Frame(left, bg=BDR, height=1).pack(fill='x', padx=12)

    # QR Codes
    sec('QR CODES')
    qr_box = tk.Frame(left, bg=BG2, padx=10, pady=8)
    qr_box.pack(fill='x')

    def load_qr(filename, label, color):
        path = os.path.join(_DATA, 'static', filename)
        if not os.path.exists(path):
            return
        try:
            from PIL import Image, ImageTk
            img = Image.open(path).resize((104, 104), Image.LANCZOS)
            brd = Image.new('RGB', (108, 108), color)
            brd.paste(img, (2, 2))
            photo = ImageTk.PhotoImage(brd)
            f = tk.Frame(qr_box, bg=BG2)
            f.pack(side='left', padx=3)
            tk.Label(f, text=label, font=('Segoe UI', 7), fg=FGMUT, bg=BG2).pack()
            lbl = tk.Label(f, image=photo, bg=BG2)
            lbl.image = photo
            lbl.pack()
        except Exception:
            pass

    load_qr('qr.png',     'Controle',   PURPLE)
    load_qr('qr_apk.png', 'Baixar APK', GREEN)

    # Ações
    sec('AÇÕES')
    btn_area = tk.Frame(left, bg=BG2, padx=12, pady=8)
    btn_area.pack(fill='x')

    terminal_ref = [None]

    def log(msg):
        w = terminal_ref[0]
        if not w:
            return
        w.configure(state='normal')
        w.insert('end', msg)
        w.see('end')
        w.configure(state='disabled')

    def mk(txt, col, cmd):
        btn = tk.Button(btn_area, text=txt, font=('Segoe UI', 10),
                         bg=col, fg=FG, relief='flat', bd=0,
                         activebackground=col, activeforeground=FG,
                         cursor='hand2', pady=7, anchor='w', padx=10,
                         command=cmd)
        btn.pack(fill='x', pady=2)
        return btn

    def do_restart():
        def _go():
            _t.sleep(0.4)
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable], cwd=os.path.dirname(sys.executable))
            else:
                subprocess.Popen([sys.executable, os.path.abspath(__file__)],
                                 cwd=os.path.dirname(os.path.abspath(__file__)))
            os._exit(0)
        threading.Thread(target=_go, daemon=True).start()

    def do_refresh():
        def _go():
            try:
                generate_static_assets(ip, port)
                def _update():
                    for w in qr_box.winfo_children():
                        w.destroy()
                    load_qr('qr.png',     'Controle',   PURPLE)
                    load_qr('qr_apk.png', 'Baixar APK', GREEN)
                    log('✓ Assets e QR codes atualizados.\n')
                root.after(0, _update)
            except Exception as e:
                root.after(0, lambda: log(f'Erro ao atualizar: {e}\n'))
        threading.Thread(target=_go, daemon=True).start()

    def autostart_label():
        return ('✓  Iniciar com o Windows' if is_autostart_enabled()
                else '☐  Iniciar com o Windows')

    def do_toggle_autostart():
        if is_autostart_enabled():
            disable_autostart()
        else:
            enable_autostart()
        autostart_btn.configure(text=autostart_label())
        log('✓ Preferência de início com o Windows atualizada.\n')

    mk('↺  Reiniciar servidor', '#1e3a5f', do_restart)
    mk('⟳  Atualizar assets',   '#14532d', do_refresh)
    autostart_btn = mk(autostart_label(), '#374151', do_toggle_autostart)
    mk('✕  Parar servidor',      '#450a0a', lambda: os._exit(0))

    # ── Terminal ─────────────────────────────────────────────
    right = tk.Frame(body, bg=BG)
    right.pack(side='left', fill='both', expand=True)

    tk.Label(right, text='Terminal', font=('Segoe UI', 8, 'bold'),
             fg=FGMUT, bg=BG, anchor='w', padx=14, pady=6).pack(fill='x')
    tk.Frame(right, bg=BDR, height=1).pack(fill='x')

    term = scrolledtext.ScrolledText(
        right, bg='#0d1117', fg='#c9d1d9',
        font=('Consolas', 9), relief='flat',
        state='disabled', wrap='word',
        padx=10, pady=10,
    )
    term.pack(fill='both', expand=True)
    terminal_ref[0] = term

    def tail():
        if not _log_path or not os.path.exists(_log_path):
            root.after(0, lambda: log('(sem log disponível)\n'))
            return
        try:
            with open(_log_path, 'r', encoding='utf-8', errors='replace') as f:
                existing = f.read()
                if existing:
                    root.after(0, lambda t=existing: log(t))
                while True:
                    line = f.readline()
                    if line:
                        root.after(0, lambda l=line: log(l))
                    else:
                        _t.sleep(0.25)
        except Exception as e:
            root.after(0, lambda: log(f'Erro ao ler log: {e}\n'))

    threading.Thread(target=tail, daemon=True).start()

    root.protocol('WM_DELETE_WINDOW', root.withdraw)
    root.mainloop()


# ── Entrada ──────────────────────────────────────────────────────────────────

def ensure_firewall(port):
    rule = f'Remote Control Server ({port})'
    check = subprocess.run(
        ['netsh', 'advfirewall', 'firewall', 'show', 'rule', f'name={rule}'],
        capture_output=True, text=True
    )
    if 'No rules match' in check.stdout or check.returncode != 0:
        subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'add', 'rule',
             f'name={rule}', 'dir=in', 'action=allow',
             'protocol=TCP', f'localport={port}'],
            capture_output=True
        )
        print(f'Regra de firewall criada para porta {port}.')
    else:
        print(f'Firewall: regra já existe.')


if __name__ == '__main__':
    if not _is_installed():
        _do_install()

    ip   = get_local_ip()
    port = 5000
    _log_path = os.path.join(_DATA, 'server.log')

    try:
        log_file   = open(_log_path, 'w', buffering=1, encoding='utf-8')
        sys.stdout = log_file
        sys.stderr = log_file
    except Exception:
        _log_path = None

    print(f'Iniciando Remote Control — http://{ip}:{port}')

    try:
        ensure_firewall(port)
    except Exception as e:
        print(f'Aviso firewall: {e}')

    try:
        generate_static_assets(ip, port)
        print('Assets gerados.')
    except Exception as e:
        print(f'Aviso assets: {e}')

    def run_flask():
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        try:
            app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
        except Exception as e:
            print(f'Erro Flask: {e}')

    threading.Thread(target=run_flask, daemon=True).start()
    run_tray(ip, port)
    run_panel(ip, port)
