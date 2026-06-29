# SGCD — Diagnóstico de Rede e Servidor
import socket, subprocess, sys, os, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PORT = 3000
SEP  = '  ' + '─' * 54

def _cor(ok):
    # verde / amarelo / vermelho no terminal Windows
    return {True: '\033[92m✅', False: '\033[91m❌', None: '\033[93m⚠️ '}.get(ok, '')

def _reset(): return '\033[0m'

def titulo(txt):
    print(f'\n  \033[1m{txt}\033[0m')
    print(SEP)

def linha(label, status, detalhe='', fix=''):
    ic = _cor(status)
    print(f'  {ic}  {label}{_reset()}')
    if detalhe:
        print(f'       {detalhe}')
    if fix:
        print(f'       \033[93m→ {fix}\033[0m')

# ── 1. Informações da máquina ─────────────────────────────────────────────────
def info_maquina():
    titulo('1. Informações da máquina')

    hostname = socket.gethostname()
    linha('Nome do computador', True, hostname)

    # IP local (preferência pela interface de saída padrão)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip_local = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            ip_local = socket.gethostbyname(hostname)
        except Exception:
            ip_local = 'não detectado'

    linha('IP local (rede)', True, ip_local)
    if ip_local not in ('não detectado', '127.0.0.1'):
        print(f'       \033[96mEndereço para outros computadores: http://{ip_local}:{PORT}/SGCD.html\033[0m')

    # tipo de adaptador dominante
    try:
        out = subprocess.check_output(
            'netsh interface show interface', shell=True, text=True,
            stderr=subprocess.DEVNULL, encoding='cp850'
        )
        wifi     = 'wi-fi' in out.lower() or 'wireless' in out.lower()
        ethernet = 'ethernet' in out.lower() or 'local area' in out.lower()
        adaptador = ('Wi-Fi' if wifi else '') + (' + Ethernet' if ethernet and wifi else 'Ethernet' if ethernet else 'desconhecido')
        linha('Adaptador de rede', True, adaptador)
    except Exception:
        linha('Adaptador de rede', None, 'não foi possível detectar')

    return ip_local

# ── 2. Porta 3000 ─────────────────────────────────────────────────────────────
def checar_porta():
    titulo(f'2. Porta {PORT}')

    # verifica se algo está escutando na porta
    em_uso = False
    try:
        test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test.settimeout(1)
        result = test.connect_ex(('127.0.0.1', PORT))
        test.close()
        em_uso = (result == 0)
    except Exception:
        pass

    if em_uso:
        linha(f'Porta {PORT} em uso (servidor provavelmente ativo)', True)
    else:
        linha(f'Porta {PORT} livre — servidor não está rodando', None,
              'Inicie o servidor pelo Iniciar SGCD.bat antes de diagnosticar acesso externo.')

    # quem está usando a porta
    if em_uso:
        try:
            out = subprocess.check_output(
                f'netstat -ano | findstr :{PORT}', shell=True,
                text=True, stderr=subprocess.DEVNULL, encoding='cp850'
            )
            for ln in out.strip().splitlines():
                if f':{PORT}' in ln and 'LISTENING' in ln:
                    pid = ln.split()[-1]
                    try:
                        proc = subprocess.check_output(
                            f'tasklist /FI "PID eq {pid}" /FO CSV /NH',
                            shell=True, text=True, stderr=subprocess.DEVNULL,
                            encoding='cp850'
                        ).strip().strip('"').split('","')[0]
                        linha(f'Processo usando a porta', True, f'{proc} (PID {pid})')
                    except Exception:
                        linha(f'PID na porta', True, pid)
                    break
        except Exception:
            pass

    # testa acesso de loopback
    try:
        import urllib.request
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2)
        linha('Responde em localhost', True)
    except Exception as e:
        if em_uso:
            linha('Responde em localhost', False, str(e))
        else:
            linha('Responde em localhost', None, 'servidor não está ativo')

    return em_uso

# ── 3. Firewall do Windows ────────────────────────────────────────────────────
def checar_firewall():
    titulo('3. Firewall do Windows')

    # verifica se o firewall está ativo
    try:
        out = subprocess.check_output(
            'netsh advfirewall show allprofiles state',
            shell=True, text=True, stderr=subprocess.DEVNULL, encoding='cp850'
        )
        ativo = 'on' in out.lower()
        linha('Windows Defender Firewall', None if ativo else True,
              'Ativo — regras de entrada serão verificadas' if ativo else 'Desativado')
    except Exception:
        ativo = True
        linha('Windows Defender Firewall', None, 'não foi possível verificar o estado')

    # verifica regra de entrada para a porta 3000
    regra_encontrada = False
    regra_ativa      = False
    try:
        out = subprocess.check_output(
            f'netsh advfirewall firewall show rule name=all dir=in | findstr /i "3000"',
            shell=True, text=True, stderr=subprocess.DEVNULL, encoding='cp850'
        )
        if out.strip():
            regra_encontrada = True
            regra_ativa      = True
    except Exception:
        pass

    if regra_ativa:
        linha(f'Regra de entrada para porta {PORT}', True, 'Encontrada e ativa')
    else:
        cmd = (f'netsh advfirewall firewall add rule name="SGCD Servidor" '
               f'dir=in action=allow protocol=TCP localport={PORT}')
        linha(f'Regra de entrada para porta {PORT}', False,
              'Nenhuma regra encontrada — outros computadores podem não conseguir conectar.',
              f'Execute como Administrador:\n       {cmd}')
        print()
        print(f'  \033[96m  Ou execute o arquivo "Liberar Porta SGCD.bat" como Administrador.\033[0m')

    return regra_ativa

# ── 4. Teste de conectividade externa ─────────────────────────────────────────
def checar_conectividade(ip_local, servidor_ativo):
    titulo('4. Conectividade pela rede')

    if ip_local in ('não detectado', '127.0.0.1', ''):
        linha('IP de rede', False, 'IP não detectado — verifique se a placa de rede está ativa')
        return

    # tenta se conectar pelo IP local (simula outro computador)
    if servidor_ativo:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            r = s.connect_ex((ip_local, PORT))
            s.close()
            if r == 0:
                linha('Acesso pelo IP da rede', True,
                      f'http://{ip_local}:{PORT}/SGCD.html está acessível')
            else:
                linha('Acesso pelo IP da rede', False,
                      'Conexão recusada pelo IP local.',
                      'Verifique a regra de firewall e se o servidor está no modo Servidor (opção 2).')
        except Exception as e:
            linha('Acesso pelo IP da rede', False, str(e))
    else:
        linha('Acesso pelo IP da rede', None,
              'Inicie o servidor antes de testar acesso externo.')

    # instrução para testar de outro computador
    print()
    print(f'  \033[1mTeste de outro computador:\033[0m')
    print(f'  Abra o navegador em outro computador e acesse:')
    print(f'  \033[96m  http://{ip_local}:{PORT}/SGCD.html\033[0m')
    print(f'  Ou faça ping: ping {ip_local}')

# ── 5. Resumo ─────────────────────────────────────────────────────────────────
def resumo(ip, servidor_ativo, regra_fw):
    print()
    print('  ' + '═' * 54)
    print('  \033[1mRESUMO\033[0m')
    print('  ' + '═' * 54)

    problemas = []
    if not servidor_ativo:
        problemas.append('Servidor não está rodando — inicie pelo Iniciar SGCD.bat')
    if not regra_fw:
        problemas.append(f'Firewall bloqueando porta {PORT} — execute Liberar Porta SGCD.bat como Administrador')
    if ip in ('não detectado', '127.0.0.1'):
        problemas.append('IP de rede não detectado — verifique a conexão de rede')

    if not problemas:
        print(f'  \033[92m✅  Tudo certo! O sistema deve estar acessível em:\033[0m')
        print(f'  \033[96m    http://{ip}:{PORT}/SGCD.html\033[0m')
    else:
        print(f'  \033[91m❌  {len(problemas)} problema(s) encontrado(s):\033[0m')
        for i, p in enumerate(problemas, 1):
            print(f'  \033[93m  {i}. {p}\033[0m')

    print()

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    os.system('color')  # habilita ANSI no Windows
    print()
    print('  ╔══════════════════════════════════════════════════╗')
    print('  ║        SGCD — Diagnóstico de Rede e Servidor     ║')
    print('  ╚══════════════════════════════════════════════════╝')

    ip            = info_maquina()
    servidor_ativo = checar_porta()
    regra_fw      = checar_firewall()
    checar_conectividade(ip, servidor_ativo)
    resumo(ip, servidor_ativo, regra_fw)

    input('  Pressione Enter para fechar...')
